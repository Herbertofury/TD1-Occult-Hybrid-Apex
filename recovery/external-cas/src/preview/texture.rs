//! Borrowed, fully validated opaque RGBA8 input. PNG decoding stays upstream.
//! Linear WRAP addressing reference, not native GPU/material-composition parity.
#[derive(Debug)]
pub struct OpaqueTexture<'a> {
    width: usize,
    height: usize,
    rgba: &'a [u8],
}
impl<'a> OpaqueTexture<'a> {
    pub fn new(width: usize, height: usize, rgba: &'a [u8]) -> Result<Self, &'static str> {
        if width == 0 || height == 0 || width > 4096 || height > 4096 {
            return Err("texture dimensions");
        }
        let bytes = width
            .checked_mul(height)
            .and_then(|n| n.checked_mul(4))
            .ok_or("texture extent overflow")?;
        if rgba.len() != bytes {
            return Err("texture exact extent");
        }
        if rgba.as_chunks::<4>().0.iter().any(|p| p[3] != 255) {
            return Err("transparent texture needs a separate material pipeline");
        }
        Ok(Self {
            width,
            height,
            rgba,
        })
    }
    pub fn dimensions(&self) -> [usize; 2] {
        [self.width, self.height]
    }
    pub fn bytes(&self) -> &'a [u8] {
        self.rgba
    }
    pub fn sample(&self, uv: [f64; 2]) -> Result<[f64; 3], &'static str> {
        if uv.iter().any(|v| !v.is_finite() || v.abs() > 101.) {
            return Err("texture UV bounds");
        }
        // Pixel centers are half a texel from the origin. WRAP applies independently
        // to both taps, including negative coordinates and the seam at UV zero.
        let p = [
            uv[0] * self.width as f64 - 0.5,
            uv[1] * self.height as f64 - 0.5,
        ];
        let base = [p[0].floor() as i64, p[1].floor() as i64];
        let blend = [p[0] - p[0].floor(), p[1] - p[1].floor()];
        let mut out = [0.; 3];
        for y in 0..2 {
            for x in 0..2 {
                let ix = (base[0] + x).rem_euclid(self.width as i64) as usize;
                let iy = (base[1] + y).rem_euclid(self.height as i64) as usize;
                let w = if x == 0 { 1. - blend[0] } else { blend[0] }
                    * if y == 0 { 1. - blend[1] } else { blend[1] };
                for (k, v) in out.iter_mut().enumerate() {
                    *v += f64::from(self.rgba[(iy * self.width + ix) * 4 + k]) * w;
                }
            }
        }
        Ok(out)
    }
}
/// Owned immutable storage for a long-lived renderer. Validation occurs once;
/// the borrowed view cannot outlive or mutate its backing bytes.
#[derive(Debug)]
pub struct OwnedOpaqueTexture {
    width: usize,
    height: usize,
    rgba: Vec<u8>,
}
impl OwnedOpaqueTexture {
    pub fn new(width: usize, height: usize, rgba: Vec<u8>) -> Result<Self, &'static str> {
        OpaqueTexture::new(width, height, &rgba)?;
        Ok(Self {
            width,
            height,
            rgba,
        })
    }
    pub fn view(&self) -> OpaqueTexture<'_> {
        OpaqueTexture {
            width: self.width,
            height: self.height,
            rgba: &self.rgba,
        }
    }
}
/// Validated full RGBA mask, borrowed without copying. Bilinear WRAP alpha.
pub struct AlphaMask<'a> {
    width: usize,
    height: usize,
    rgba: &'a [u8],
    threshold: u8,
}
impl<'a> AlphaMask<'a> {
    pub fn new(
        width: usize,
        height: usize,
        rgba: &'a [u8],
        threshold: u8,
    ) -> Result<Self, &'static str> {
        if width == 0
            || height == 0
            || width > 4096
            || height > 4096
            || rgba.len() != width * height * 4
        {
            return Err("cutout mask extent");
        }
        Ok(Self {
            width,
            height,
            rgba,
            threshold,
        })
    }
    pub fn dimensions(&self) -> [usize; 2] {
        [self.width, self.height]
    }
    pub fn visible(&self, uv: [f64; 2]) -> Result<bool, &'static str> {
        if uv.iter().any(|v| !v.is_finite() || v.abs() > 101.) {
            return Err("texture UV bounds");
        }
        let p = [
            uv[0] * self.width as f64 - 0.5,
            uv[1] * self.height as f64 - 0.5,
        ];
        let base = [p[0].floor() as i64, p[1].floor() as i64];
        let t = [p[0] - p[0].floor(), p[1] - p[1].floor()];
        let mut alpha = 0.;
        for y in 0..2 {
            for x in 0..2 {
                let ix = (base[0] + x).rem_euclid(self.width as i64) as usize;
                let iy = (base[1] + y).rem_euclid(self.height as i64) as usize;
                let w =
                    if x == 0 { 1. - t[0] } else { t[0] } * if y == 0 { 1. - t[1] } else { t[1] };
                alpha += f64::from(self.rgba[(iy * self.width + ix) * 4 + 3]) * w;
            }
        }
        Ok(alpha >= f64::from(self.threshold))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn exact_centers_and_wrap() {
        let b = [
            255, 0, 0, 255, 0, 255, 0, 255, 0, 0, 255, 255, 255, 255, 255, 255,
        ];
        let t = OpaqueTexture::new(2, 2, &b).unwrap();
        assert_eq!(t.sample([0.25, 0.25]).unwrap(), [255., 0., 0.]);
        assert_eq!(t.sample([0.75, 0.25]).unwrap(), [0., 255., 0.]);
        assert_eq!(t.sample([-0.25, 0.25]).unwrap(), [0., 255., 0.]);
        assert_eq!(t.sample([1.25, 0.25]).unwrap(), [255., 0., 0.]);
        assert_eq!(t.sample([0., 0.]).unwrap(), [127.5; 3]);
    }
    #[test]
    fn one_texel_is_constant() {
        let b = [9, 71, 253, 255];
        let t = OpaqueTexture::new(1, 1, &b).unwrap();
        for uv in [[0., 0.], [0.5, 0.5], [-100., 100.], [100.7, -1.3]] {
            let c = t.sample(uv).unwrap();
            for k in 0..3 {
                assert!((c[k] - f64::from(b[k])).abs() < 1e-10);
            }
        }
    }
    #[test]
    fn refuses_incomplete_alpha_dimensions_and_uv() {
        for b in [
            &[1u8, 2, 3][..],
            &[1, 2, 3, 254][..],
            &[1, 2, 3, 255, 0][..],
        ] {
            assert!(OpaqueTexture::new(1, 1, b).is_err());
        }
        assert!(OpaqueTexture::new(0, 1, &[]).is_err());
        assert!(OpaqueTexture::new(4097, 1, &[]).is_err());
        let b = [0, 0, 0, 255];
        let t = OpaqueTexture::new(1, 1, &b).unwrap();
        for v in [f64::NAN, f64::INFINITY, 102.] {
            assert!(t.sample([v, 0.]).is_err());
        }
    }
    #[test]
    fn owned_storage_is_validated_once_without_a_second_payload_copy() {
        let bytes = vec![3, 7, 11, 255];
        let ptr = bytes.as_ptr();
        let owned = OwnedOpaqueTexture::new(1, 1, bytes).unwrap();
        assert_eq!(owned.view().bytes().as_ptr(), ptr);
        assert_eq!(owned.view().sample([0.5, 0.5]).unwrap(), [3., 7., 11.]);
        assert!(OwnedOpaqueTexture::new(1, 1, vec![3, 7, 11, 0]).is_err());
    }
}
