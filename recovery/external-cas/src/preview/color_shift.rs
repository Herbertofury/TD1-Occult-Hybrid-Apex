//! CAS Q14 color-lane preview. Independent HSV implementation.
//! Callers must enforce selected CASP edit bounds; stored bits are not rewritten.
/// A lane in the game's packed color value. Unedited lanes remain bit-exact.
#[derive(Clone, Copy, Debug)]
#[repr(u8)]
pub enum Channel {
    Brightness,
    Saturation,
    Hue,
    Opacity,
}
/// Effective selected-CASP metadata, not a global default slider range.
#[derive(Clone, Copy, Debug)]
pub struct EditRange {
    pub enabled: bool,
    pub min: f64,
    pub max: f64,
}
/// Apply explicit draft edits using Apex's existing signed-Q14 rounding contract.
/// No game writes, snapping to UI step, or normalization of unedited lanes.
/// Callers must bind these ranges to the selected CASP resource identity.
pub fn replace_lanes(raw: u64, edits: &[(Channel, f64, EditRange)]) -> Result<u64, &'static str> {
    if edits.is_empty() || edits.len() > 4 {
        return Err("expected one to four explicit lane edits");
    }
    let mut result = raw;
    let mut seen = 0u8;
    for &(channel, value, bounds) in edits {
        let index = channel as u8;
        if seen & (1 << index) != 0 {
            return Err("duplicate lane edit");
        }
        seen |= 1 << index;
        if !bounds.enabled {
            return Err("lane disabled by selected CASP");
        }
        if !value.is_finite()
            || !bounds.min.is_finite()
            || !bounds.max.is_finite()
            || bounds.min > bounds.max
        {
            return Err("invalid lane value or CASP bounds");
        }
        if value < bounds.min || value > bounds.max {
            return Err("value outside selected CASP range");
        }
        let rounded = (value * 16384.).round();
        if !(-32768. ..=32767.).contains(&rounded) {
            return Err("value outside signed Q14 range");
        }
        let quantized = rounded / 16384.;
        if quantized < bounds.min - 0.5 / 16384. || quantized > bounds.max + 0.5 / 16384. {
            return Err("quantized value outside selected CASP range");
        }
        let shift = u32::from(index) * 16;
        result = (result & !(65535u64 << shift)) | (u64::from(rounded as i16 as u16) << shift);
    }
    Ok(result)
}
#[derive(Clone, Copy, Debug)]
pub struct ColorShift {
    brightness: f64,
    saturation: f64,
    hue: f64,
    opacity: f64,
}
impl ColorShift {
    pub fn decode(bits: u64) -> Result<Self, &'static str> {
        let lane = |i| f64::from(((bits >> (i * 16)) as u16) as i16) / 16384.;
        let result = Self {
            brightness: lane(0),
            saturation: lane(1),
            hue: lane(2),
            opacity: lane(3),
        };
        if !(0.0..=1.0).contains(&result.opacity) {
            return Err("stored opacity outside supported range");
        }
        Ok(result)
    }
    pub fn apply(self, rgba: &[u8]) -> Result<Vec<u8>, &'static str> {
        if !rgba.len().is_multiple_of(4) || rgba.len() > 64 * 1024 * 1024 {
            return Err("color texture extent");
        }
        self.validate()?;
        let mut output = rgba.to_vec();
        for pixel in output.as_chunks_mut::<4>().0 {
            self.apply_pixel(pixel);
        }
        Ok(output)
    }
    fn validate(self) -> Result<(), &'static str> {
        if ![self.brightness, self.saturation, self.hue, self.opacity]
            .iter()
            .all(|x| x.is_finite())
            || !(0.0..=1.0).contains(&self.opacity)
        {
            return Err("color shift numeric range");
        }
        Ok(())
    }
    fn apply_pixel(self, pixel: &mut [u8; 4]) {
        if pixel[3] == 0 {
            return;
        }
        let [r, g, b] = [
            f64::from(pixel[0]) / 255.,
            f64::from(pixel[1]) / 255.,
            f64::from(pixel[2]) / 255.,
        ];
        let max = r.max(g).max(b);
        let min = r.min(g).min(b);
        let delta = max - min;
        let hue = if delta == 0. {
            0.
        } else if max == r {
            (((g - b) / delta + 6.) % 6.) / 6.
        } else if max == g {
            ((b - r) / delta + 2.) / 6.
        } else {
            ((r - g) / delta + 4.) / 6.
        };
        let h = (((hue + self.hue) % 1.) + 1.) % 1.;
        let saturation =
            ((if max > 0. { delta / max } else { 0. }) + self.saturation).clamp(0., 1.);
        let value = (max + self.brightness).clamp(0., 1.);
        // Triangular-wave HSV conversion. Keep this arithmetic order:
        // algebraically equivalent sector conversion differs at byte-rounding ties.
        for (channel, phase) in [5., 3., 1.].into_iter().enumerate() {
            let k = (phase + h * 6.) % 6.;
            let wave = k.min(4. - k).clamp(0., 1.);
            pixel[channel] = ((value - value * saturation * wave) * 255.).round() as u8;
        }
        pixel[3] = (f64::from(pixel[3]) * self.opacity).round() as u8;
    }
    /// One full output allocation, preserving separate shift-then-source-over rounding.
    /// No transformed intermediate atlas is allocated.
    pub fn compose_over(
        self,
        base: super::texture::OpaqueTexture<'_>,
        rgba: &[u8],
    ) -> Result<super::texture::OwnedOpaqueTexture, &'static str> {
        self.validate()?;
        if rgba.len() != base.bytes().len() {
            return Err("incomplete color layer");
        }
        let mut output = base.bytes().to_vec();
        for (dst, src) in output
            .as_chunks_mut::<4>()
            .0
            .iter_mut()
            .zip(rgba.as_chunks::<4>().0)
        {
            if src[3] == 0 {
                continue;
            }
            let mut pixel = *src;
            self.apply_pixel(&mut pixel);
            let alpha = u32::from(pixel[3]);
            for k in 0..3 {
                dst[k] = ((u32::from(pixel[k]) * alpha + u32::from(dst[k]) * (255 - alpha) + 127)
                    / 255) as u8;
            }
        }
        super::texture::OwnedOpaqueTexture::new(base.dimensions()[0], base.dimensions()[1], output)
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn fused_layer_exactly_matches_separate_shift_and_composition() {
        use crate::preview::{
            layers::{Layer, Mode, compose_over},
            texture::OpaqueTexture,
        };
        let mut source = Vec::new();
        let mut base = Vec::new();
        let mut seed = 7u32;
        for i in 0..4096 {
            let mut bytes = [0; 6];
            for b in &mut bytes {
                seed = seed.wrapping_mul(1664525).wrapping_add(1013904223);
                *b = (seed >> 24) as u8;
            }
            source.extend([bytes[0], bytes[1], bytes[2], (i % 256) as u8]);
            base.extend([bytes[3], bytes[4], bytes[5], 255]);
        }
        let original = source.clone();
        for bits in [
            0x4000000000000000,
            0x20002000e0001000,
            0x4000e0002000e000,
            0x0000200020002000,
            0x4000000100010001,
            0x0ccde0011fff0000,
        ] {
            let shift = ColorShift::decode(bits).unwrap();
            let transformed = shift.apply(&source).unwrap();
            let reference = compose_over(
                OpaqueTexture::new(64, 64, &base).unwrap(),
                &[Layer {
                    rgba: &transformed,
                    mode: Mode::SourceOver,
                }],
            )
            .unwrap();
            let fused = shift
                .compose_over(OpaqueTexture::new(64, 64, &base).unwrap(), &source)
                .unwrap();
            assert_eq!(reference.view().bytes(), fused.view().bytes());
        }
        assert_eq!(source, original);
        assert!(
            ColorShift::decode(0x4000000000000000)
                .unwrap()
                .compose_over(
                    OpaqueTexture::new(64, 64, &base).unwrap(),
                    &source[..source.len() - 1]
                )
                .is_err()
        );
    }
    #[test]
    fn lanes_and_unedited_bits() {
        let v = ColorShift::decode(0x40002000e0001000).unwrap();
        assert_eq!(
            (v.opacity, v.hue, v.saturation, v.brightness),
            (1., 0.5, -0.5, 0.25)
        );
    }
    #[test]
    fn neutral_exact_all_channels() {
        let mut input = Vec::new();
        for i in 0..=255u8 {
            input.extend([i, i.wrapping_mul(13), i.wrapping_mul(71), i]);
        }
        assert_eq!(
            ColorShift::decode(0x4000000000000000)
                .unwrap()
                .apply(&input)
                .unwrap(),
            input
        );
    }
    #[test]
    fn transparent_hidden_rgb_preserved() {
        assert_eq!(
            ColorShift::decode(0x2000200020002000)
                .unwrap()
                .apply(&[12, 77, 235, 0])
                .unwrap(),
            [12, 77, 235, 0]
        );
    }
    #[test]
    fn hue_wrap_and_alpha() {
        assert_eq!(
            ColorShift {
                brightness: 0.,
                saturation: 0.,
                hue: 1. / 3.,
                opacity: 0.5
            }
            .apply(&[255, 0, 0, 255])
            .unwrap(),
            [0, 255, 0, 128]
        );
    }
    #[test]
    fn invalid_refuses_without_mutation() {
        let b = [1, 2, 3];
        assert!(
            ColorShift::decode(0x4000000000000000)
                .unwrap()
                .apply(&b)
                .is_err()
        );
        assert!(ColorShift::decode(0x8000000000000000).is_err());
        assert_eq!(b, [1, 2, 3]);
    }
}

#[cfg(test)]
mod edit_tests {
    use super::*;
    const RANGE: EditRange = EditRange {
        enabled: true,
        min: -0.5,
        max: 0.5,
    };
    #[test]
    fn preserves_all_unedited_bits() {
        let raw = 0x7fff8000ffff1234;
        assert_eq!(
            replace_lanes(raw, &[(Channel::Hue, 0.25, RANGE)]).unwrap(),
            0x7fff1000ffff1234
        );
        assert_eq!(raw, 0x7fff8000ffff1234);
    }
    #[test]
    fn rounding_ties_away_from_zero() {
        for (v, expected) in [(0.5 / 16384., 1u64), (-0.5 / 16384., 65535u64)] {
            assert_eq!(
                replace_lanes(0, &[(Channel::Brightness, v, RANGE)]).unwrap(),
                expected
            );
        }
    }
    #[test]
    fn effective_bounds_and_atomic_failure() {
        let raw = 0x4000000000000000;
        assert!(
            replace_lanes(
                raw,
                &[
                    (Channel::Hue, 0.25, RANGE),
                    (
                        Channel::Opacity,
                        0.1,
                        EditRange {
                            enabled: true,
                            min: 0.2,
                            max: 1.
                        }
                    )
                ]
            )
            .is_err()
        );
        assert_eq!(raw, 0x4000000000000000);
        for value in [f64::NAN, f64::INFINITY, f64::NEG_INFINITY, 0.5001, -0.5001] {
            assert!(replace_lanes(raw, &[(Channel::Hue, value, RANGE)]).is_err());
        }
        for bounds in [
            EditRange {
                enabled: false,
                ..RANGE
            },
            EditRange {
                min: 1.,
                max: 0.,
                ..RANGE
            },
            EditRange {
                min: f64::NAN,
                ..RANGE
            },
            EditRange {
                max: f64::INFINITY,
                ..RANGE
            },
        ] {
            assert!(replace_lanes(raw, &[(Channel::Hue, 0., bounds)]).is_err());
        }
        assert!(replace_lanes(raw, &[]).is_err());
        assert!(
            replace_lanes(raw, &[(Channel::Hue, 0., RANGE), (Channel::Hue, 0., RANGE)]).is_err()
        );
        assert!(
            replace_lanes(
                raw,
                &[(
                    Channel::Hue,
                    2.,
                    EditRange {
                        enabled: true,
                        min: -2.,
                        max: 2.
                    }
                )]
            )
            .is_err()
        );
    }
}

/// Isolated candidate for repeated edits to a single immutable selected texture.
/// Bounded to 65,536 distinct RGBA values. Dense inputs return an explicit error;
/// callers can retain the ordinary per-pixel path, never a partial texture.
pub struct PreparedColors {
    palette: Vec<u8>,
    indices: Vec<u16>,
    active_runs: Option<Vec<std::ops::Range<usize>>>,
}
impl PreparedColors {
    pub fn new(rgba: &[u8]) -> Result<Self, &'static str> {
        if rgba.is_empty() || !rgba.len().is_multiple_of(4) || rgba.len() > 64 * 1024 * 1024 {
            return Err("prepared color texture extent");
        }
        let mut table = std::collections::HashMap::<[u8; 4], u16>::new();
        let mut palette = Vec::new();
        let mut indices = Vec::with_capacity(rgba.len() / 4);
        for &pixel in rgba.as_chunks::<4>().0 {
            let index = match table.get(&pixel) {
                Some(&index) => index,
                None => {
                    let index = u16::try_from(palette.len() / 4)
                        .map_err(|_| "texture exceeds prepared palette budget")?;
                    table.insert(pixel, index);
                    palette.extend_from_slice(&pixel);
                    index
                }
            };
            indices.push(index);
        }
        Ok(Self { palette, indices, active_runs: bounded_alpha_runs(rgba) })
    }
    pub fn distinct_colors(&self) -> usize {
        self.palette.len() / 4
    }
    pub fn retained_bytes(&self) -> usize {
        self.palette.capacity() + self.indices.capacity() * 2 + self.active_runs.as_ref().map_or(0, |runs| runs.capacity() * std::mem::size_of::<std::ops::Range<usize>>())
    }
    pub fn apply(&self, shift: ColorShift) -> Result<Vec<u8>, &'static str> {
        let palette = shift.apply(&self.palette)?;
        let pixels = palette.as_chunks::<4>().0;
        let mut result = Vec::with_capacity(self.indices.len() * 4);
        for &index in &self.indices {
            result.extend_from_slice(&pixels[usize::from(index)]);
        }
        Ok(result)
    }
}
#[cfg(test)]
mod prepared_color_tests {
    use super::*;
    #[test]
    fn exact_hidden_rgb_alpha_and_rounding() {
        let data: Vec<_> = (0..=255u8)
            .flat_map(|v| [v, v.wrapping_mul(13), v.wrapping_mul(71), v])
            .collect();
        let prepared = PreparedColors::new(&data).unwrap();
        for bits in [
            0x4000000000000000,
            0x3000e00010000800,
            0x2000200020002000,
            0x4000100000000000,
        ] {
            let shift = ColorShift::decode(bits).unwrap();
            assert_eq!(prepared.apply(shift).unwrap(), shift.apply(&data).unwrap());
        }
    }
    #[test]
    fn bounded_dense_and_incomplete_input() {
        assert!(PreparedColors::new(&[]).is_err());
        assert!(PreparedColors::new(&[0; 3]).is_err());
        let dense: Vec<_> = (0..65537u32).flat_map(u32::to_le_bytes).collect();
        assert!(PreparedColors::new(&dense).is_err());
        let edge = PreparedColors::new(&dense[..65536 * 4]).unwrap();
        assert_eq!(edge.distinct_colors(), 65536);
        assert_eq!(
            edge.apply(ColorShift::decode(0x4000000000000000).unwrap())
                .unwrap(),
            dense[..65536 * 4]
        );
    }
}

impl PreparedColors {
    /// Exact palette transform fused with complete source-over reconstruction.
    /// Reuses the retained palette candidate; no full shifted RGBA intermediate.
    pub fn compose_over(&self, shift: ColorShift, base: super::texture::OpaqueTexture<'_>) -> Result<super::texture::OwnedOpaqueTexture, &'static str> {
        if base.bytes().len() != self.indices.len() * 4 { return Err("incomplete prepared color layer"); }
        let palette = shift.apply(&self.palette)?;
        let pixels = palette.as_chunks::<4>().0;
        let mut output = base.bytes().to_vec();
        let mut blend = |start: usize, end: usize| {
        for (dst, &index) in output[start*4..end*4].as_chunks_mut::<4>().0.iter_mut().zip(&self.indices[start..end]) {
            let pixel = pixels[usize::from(index)];
            let alpha = u32::from(pixel[3]);
            if alpha == 0 { continue; }
            for k in 0..3 {
                dst[k] = ((u32::from(pixel[k]) * alpha + u32::from(dst[k]) * (255-alpha) + 127) / 255) as u8;
            }
        }
        };
        match &self.active_runs {
            Some(runs) => { for run in runs { blend(run.start, run.end); } },
            None => blend(0,self.indices.len()),
        }
        super::texture::OwnedOpaqueTexture::new(base.dimensions()[0],base.dimensions()[1],output)
    }
}
#[cfg(test)]
mod fused_palette_tests {
    use super::*;
    use crate::preview::texture::OpaqueTexture;
    #[test]
    fn every_alpha_and_color_edits_match_current_fused_reference() {
        let source: Vec<_> = (0..4096u32).flat_map(|i|[(i%256) as u8,((i*13)%256) as u8,((i*71)%256) as u8,(i%256) as u8]).collect();
        let base: Vec<_> = (0..4096u32).flat_map(|i|[((i*17)%256) as u8,((i*29)%256) as u8,((i*43)%256) as u8,255]).collect();
        let prepared=PreparedColors::new(&source).unwrap();let original=source.clone();
        for bits in [0x4000000000000000,0x20002000e0001000,0x4000e0002000e000,0x0000200020002000,0x4000000100010001,0x0ccde0011fff0000] {
            let shift=ColorShift::decode(bits).unwrap();
            let view=OpaqueTexture::new(64,64,&base).unwrap();
            assert_eq!(prepared.compose_over(shift,view).unwrap().view().bytes(),shift.compose_over(OpaqueTexture::new(64,64,&base).unwrap(),&source).unwrap().view().bytes());
        }
        assert_eq!(source,original);
        assert!(prepared.compose_over(ColorShift::decode(0x4000000000000000).unwrap(),OpaqueTexture::new(1,1,&[0,0,0,255]).unwrap()).is_err());
    }
}

/// Own one complete immutable representation, never both the RGBA atlas and its
/// lossless palette/index representation. Dense inputs keep the complete atlas.
pub struct PreparedColorLayer { source: ColorLayerSource }
enum ColorLayerSource { Palette(PreparedColors), Direct(Vec<u8>) }
impl PreparedColorLayer {
    pub fn new(rgba: Vec<u8>) -> Result<Self, &'static str> {
        let source = match PreparedColors::new(&rgba) {
            Ok(palette) => ColorLayerSource::Palette(palette),
            Err("texture exceeds prepared palette budget") => ColorLayerSource::Direct(rgba),
            Err(error) => return Err(error),
        };
        Ok(Self { source })
    }
    pub fn mode(&self) -> &'static str { match self.source { ColorLayerSource::Palette(_) => "exact-palette", ColorLayerSource::Direct(_) => "complete-rgba-fallback" } }
    pub fn retained_bytes(&self) -> usize { match &self.source { ColorLayerSource::Palette(p) => p.retained_bytes(), ColorLayerSource::Direct(v) => v.capacity() } }
    pub fn compose_over(&self, shift: ColorShift, base: super::texture::OpaqueTexture<'_>) -> Result<super::texture::OwnedOpaqueTexture, &'static str> {
        match &self.source { ColorLayerSource::Palette(p) => p.compose_over(shift,base), ColorLayerSource::Direct(v) => shift.compose_over(base,v) }
    }
}
#[cfg(test)]
mod color_owner_tests {
    use super::*;
    use crate::preview::texture::OpaqueTexture;
    #[test]
    fn dense_fallback_retains_every_pixel_and_exact_output() {
        let input:Vec<_>=(0..131072u32).flat_map(|n|[n as u8,(n>>8) as u8,(n>>16) as u8,255]).collect();
        let base=vec![255;input.len()];let owner=PreparedColorLayer::new(input.clone()).unwrap();assert_eq!(owner.mode(),"complete-rgba-fallback");
        let shift=ColorShift::decode(0x20002000e0001000).unwrap();
        assert_eq!(owner.compose_over(shift,OpaqueTexture::new(256,512,&base).unwrap()).unwrap().view().bytes(),shift.compose_over(OpaqueTexture::new(256,512,&base).unwrap(),&input).unwrap().view().bytes());
    }
    #[test]
    fn palette_owners_do_not_reuse_another_source_and_reject_bad_extent() {
        assert!(PreparedColorLayer::new(vec![1,2,3]).is_err());
        let first=PreparedColorLayer::new(vec![255,0,0,255]).unwrap();let second=PreparedColorLayer::new(vec![0,255,0,255]).unwrap();assert_eq!(first.mode(),"exact-palette");let shift=ColorShift::decode(0x4000000000000000).unwrap();
        assert_ne!(first.compose_over(shift,OpaqueTexture::new(1,1,&[0,0,0,255]).unwrap()).unwrap().view().bytes(),second.compose_over(shift,OpaqueTexture::new(1,1,&[0,0,0,255]).unwrap()).unwrap().view().bytes());
    }
}

// Complete lossless source remains retained. Only known zero-alpha work is
// omitted from source-over; every output pixel still comes from the full base.
fn bounded_alpha_runs(rgba: &[u8]) -> Option<Vec<std::ops::Range<usize>>> {
    let mut runs = Vec::new(); let mut start = None;
    for (i,pixel) in rgba.as_chunks::<4>().0.iter().enumerate() {
        if pixel[3] != 0 { if start.is_none() { start = Some(i); } }
        else if let Some(begin) = start.take() { if runs.len() == 65536 { return None; } runs.push(begin..i); }
    }
    if let Some(begin) = start { if runs.len() == 65536 { return None; } runs.push(begin..rgba.len()/4); }
    Some(runs)
}
#[cfg(test)]
mod alpha_run_tests {
    use super::*; use crate::preview::texture::OpaqueTexture;
    #[test]
    fn transparent_runs_and_edge_pixels_preserve_full_output() {
        for count in [1,2,3,256] { for offset in 0..3 { let source:Vec<_>=(0..count).flat_map(|i|[17,93,201,if (i+offset)%3==0 {0} else {127}]).collect();let base=vec![255;count*4];let p=PreparedColors::new(&source).unwrap();for bits in [0x4000000000000000,0x0000200020002000,0x2000e00010000800] {let shift=ColorShift::decode(bits).unwrap();assert_eq!(p.compose_over(shift,OpaqueTexture::new(count,1,&base).unwrap()).unwrap().view().bytes(),shift.compose_over(OpaqueTexture::new(count,1,&base).unwrap(),&source).unwrap().view().bytes());}} }
    }
    #[test]
    fn fragmented_run_budget_falls_back_without_losing_source() {
        let source:Vec<_>=(0..262144).flat_map(|i|[17,93,201,if i%2==0 {255} else {0}]).collect();let p=PreparedColors::new(&source).unwrap();assert!(p.active_runs.is_none());let base=vec![255;source.len()];let shift=ColorShift::decode(0x20002000e0001000).unwrap();assert_eq!(p.compose_over(shift,OpaqueTexture::new(512,512,&base).unwrap()).unwrap().view().bytes(),shift.compose_over(OpaqueTexture::new(512,512,&base).unwrap(),&source).unwrap().view().bytes());assert_eq!(p.apply(shift).unwrap(),shift.apply(&source).unwrap());
    }
}
