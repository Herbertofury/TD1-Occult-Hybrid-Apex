//! Explicit diagnostic RGBA layering. This is not EA TONE/color-space parity.
//! Callers resolve CASP resources and order; no unknown layer is silently skipped.
use super::texture::OwnedOpaqueTexture;
pub enum Mode {
    SourceOver,
    Multiply,
}
pub struct Layer<'a> {
    pub rgba: &'a [u8],
    pub mode: Mode,
}
pub fn compose(
    width: usize,
    height: usize,
    base: [u8; 3],
    layers: &[Layer<'_>],
) -> Result<OwnedOpaqueTexture, &'static str> {
    if width == 0 || height == 0 || width > 4096 || height > 4096 || layers.len() > 64 {
        return Err("layer bounds");
    }
    let extent = width
        .checked_mul(height)
        .and_then(|x| x.checked_mul(4))
        .ok_or("layer extent")?;
    // Validate every input before allocating or producing any output.
    if layers.iter().any(|l| l.rgba.len() != extent) {
        return Err("incomplete layer");
    }
    let mut out = vec![0u8; extent];
    for pixel in out.as_chunks_mut::<4>().0 {
        pixel[..3].copy_from_slice(&base);
        pixel[3] = 255;
    }
    apply_layers(&mut out, layers);
    OwnedOpaqueTexture::new(width, height, out)
}
/// Recompose changed upper layers over a fully validated opaque lower stack.
/// The caller must rebuild the lower stack when any of its source inputs changes.
/// This preserves the exact integer rounding/order used by full composition.
pub fn compose_over(
    base: super::texture::OpaqueTexture<'_>,
    layers: &[Layer<'_>],
) -> Result<OwnedOpaqueTexture, &'static str> {
    if layers.len() > 64 || layers.iter().any(|l| l.rgba.len() != base.bytes().len()) {
        return Err("incomplete or excessive layers");
    }
    let mut out = base.bytes().to_vec();
    apply_layers(&mut out, layers);
    OwnedOpaqueTexture::new(base.dimensions()[0], base.dimensions()[1], out)
}
fn apply_layers(out: &mut [u8], layers: &[Layer<'_>]) {
    for layer in layers {
        for (dst, src) in out
            .as_chunks_mut::<4>()
            .0
            .iter_mut()
            .zip(layer.rgba.as_chunks::<4>().0)
        {
            let alpha = u32::from(src[3]);
            for k in 0..3 {
                let old = u32::from(dst[k]);
                let color = match layer.mode {
                    Mode::SourceOver => u32::from(src[k]),
                    Mode::Multiply => (old * u32::from(src[k]) + 127) / 255,
                };
                dst[k] = ((color * alpha + old * (255 - alpha) + 127) / 255) as u8;
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn transparent_rgb_does_not_leak() {
        let a = [0, 255, 0, 0];
        assert_eq!(
            compose(
                1,
                1,
                [180, 120, 90],
                &[Layer {
                    rgba: &a,
                    mode: Mode::SourceOver
                }]
            )
            .unwrap()
            .view()
            .bytes(),
            [180, 120, 90, 255]
        );
    }
    #[test]
    fn opaque_and_partial_layers_preserve_order() {
        let a = [10, 20, 30, 255];
        let b = [110, 120, 130, 128];
        assert_eq!(
            compose(
                1,
                1,
                [0; 3],
                &[
                    Layer {
                        rgba: &a,
                        mode: Mode::SourceOver
                    },
                    Layer {
                        rgba: &b,
                        mode: Mode::SourceOver
                    }
                ]
            )
            .unwrap()
            .view()
            .bytes(),
            [60, 70, 80, 255]
        );
    }
    #[test]
    fn complete_layers_required() {
        assert!(
            compose(
                1,
                1,
                [0; 3],
                &[Layer {
                    rgba: &[0; 3],
                    mode: Mode::Multiply
                }]
            )
            .is_err()
        );
        assert!(compose(4097, 1, [0; 3], &[]).is_err());
    }
    #[test]
    fn full_alpha_multiply_identity() {
        assert_eq!(
            compose(
                1,
                1,
                [9, 70, 251],
                &[Layer {
                    rgba: &[255; 4],
                    mode: Mode::Multiply
                }]
            )
            .unwrap()
            .view()
            .bytes(),
            [9, 70, 251, 255]
        );
    }
}

#[cfg(test)]
mod incremental_tests {
    use super::*;
    #[test]
    fn exact_all_split_points_and_modes() {
        let arrays: Vec<Vec<u8>> = (0..8)
            .map(|i| {
                (0..256)
                    .flat_map(|j| {
                        [
                            j as u8,
                            (j * 17 + i) as u8,
                            (j * 31 + i * 7) as u8,
                            (j + i * 19) as u8,
                        ]
                    })
                    .collect()
            })
            .collect();
        let layers: Vec<_> = arrays
            .iter()
            .enumerate()
            .map(|(i, a)| Layer {
                rgba: a,
                mode: if i % 2 == 0 {
                    Mode::SourceOver
                } else {
                    Mode::Multiply
                },
            })
            .collect();
        let full = compose(16, 16, [180, 120, 90], &layers).unwrap();
        for split in 0..=layers.len() {
            let base = compose(16, 16, [180, 120, 90], &layers[..split]).unwrap();
            let result = compose_over(base.view(), &layers[split..]).unwrap();
            assert_eq!(full.view().bytes(), result.view().bytes());
        }
    }
    #[test]
    fn failure_keeps_last_good_base() {
        let base = compose(1, 1, [180, 120, 90], &[]).unwrap();
        assert!(
            compose_over(
                base.view(),
                &[Layer {
                    rgba: &[0; 3],
                    mode: Mode::SourceOver
                }]
            )
            .is_err()
        );
        assert_eq!(base.view().bytes(), [180, 120, 90, 255]);
    }
}
