//! Bounded standard soft-light / overlay skin-detail preview.
//! Uses actual tone pixels and explicit overlay opacity. This narrow mode has no
//! sculpt layers, tan masks, hue wash, or native game shader equivalence claim.
use super::texture::OwnedOpaqueTexture;
pub fn blend(
    width: usize,
    height: usize,
    tone: &[u8],
    detail: &[u8],
    opacity: f64,
    value_shift: f64,
) -> Result<OwnedOpaqueTexture, &'static str> {
    if width == 0
        || height == 0
        || width > 4096
        || height > 4096
        || !opacity.is_finite()
        || !(0.0..=1.0).contains(&opacity)
        || !value_shift.is_finite()
        || !(-1.0..=1.0).contains(&value_shift)
    {
        return Err("skin blend bounds");
    }
    let size = width * height * 4;
    if tone.len() != size
        || detail.len() != size
        || tone.as_chunks::<4>().0.iter().any(|p| p[3] != 255)
    {
        return Err("skin blend incomplete/transparent tone");
    }
    let mut result = vec![255; size];
    for ((out, base), shade) in result
        .as_chunks_mut::<4>()
        .0
        .iter_mut()
        .zip(tone.as_chunks::<4>().0)
        .zip(detail.as_chunks::<4>().0)
    {
        for k in 0..3 {
            let d = if shade[3] == 0 {
                0.
            } else {
                f64::from(shade[k])
            };
            let color = (f64::from(base[k]) + value_shift * 255.).clamp(0., 255.);
            let dn = d / 255.;
            let cn = color / 255.;
            // Soft-light detail over color, followed by overlay at the tone's explicit opacity.
            let first = (((1. - 2. * dn) * cn * cn + 2. * dn * cn) * 255. * 1.2).min(255.);
            let second = if first > 128. {
                255. - (255. - 2. * (d - 128.)) * (255. - first) / 256.
            } else {
                2. * d * first / 256.
            };
            let mixed = second * opacity + first * (1. - opacity);
            let contrasted = (((mixed / 255. - 0.75) * 1.1 + 0.75) * 255.).clamp(0., 255.);
            // The comparison pipeline stores its working image as float32 before output.
            out[k] = (contrasted as f32).round() as u8;
        }
    }
    OwnedOpaqueTexture::new(width, height, result)
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn refuses_missing_or_invalid_layers() {
        assert!(blend(1, 1, &[0; 4], &[0; 4], 0.5, 0.).is_err());
        assert!(blend(1, 1, &[255; 4], &[0; 3], 0.5, 0.).is_err());
        assert!(blend(1, 1, &[255; 4], &[0; 4], f64::NAN, 0.).is_err());
    }
    #[test]
    fn output_is_opaque_and_inputs_unchanged() {
        let tone = [90, 60, 40, 255];
        let detail = [180, 180, 180, 255];
        let image = blend(1, 1, &tone, &detail, 0.35, 0.).unwrap();
        assert_eq!(image.view().bytes()[3], 255);
        assert_eq!(tone, [90, 60, 40, 255]);
        assert_eq!(detail, [180, 180, 180, 255]);
    }
}
