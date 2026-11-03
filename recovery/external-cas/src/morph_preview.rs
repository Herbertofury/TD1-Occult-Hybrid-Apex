//! Bounded, source-bound preview deltas. Resource interpretation belongs to the
//! separately licensed upstream adapter; this generic layer never edits a Sim.
use crate::mesh::{STRIDE, SceneBudget};
use std::sync::Arc;
pub struct MorphPlan {
    source: Arc<[u8]>,
    deltas: Vec<[f32; 6]>,
    bones: usize,
}
impl MorphPlan {
    pub fn new(source: &[u8], deltas: Vec<[f32; 6]>, bones: usize) -> Result<Self, &'static str> {
        let mesh = SceneBudget::default().validate(source, bones)?;
        if deltas.len() != mesh.vertex_count as usize
            || deltas.iter().flatten().any(|x| !x.is_finite())
        {
            return Err("morph delta count/numeric bound");
        }
        Ok(Self {
            source: Arc::from(source),
            deltas,
            bones,
        })
    }
    pub fn apply(&self, current_source: &[u8], weight: f32) -> Result<Vec<u8>, &'static str> {
        if current_source != self.source.as_ref() {
            return Err("morph source changed");
        }
        if !weight.is_finite() || !(0.0..=1.0).contains(&weight) {
            return Err("diagnostic morph weight");
        }
        let mut output = self.source.to_vec();
        if weight == 0. {
            return Ok(output);
        }
        for (i, delta) in self.deltas.iter().enumerate() {
            for (k, d) in delta.iter().enumerate() {
                if *d == 0. {
                    continue;
                }
                let at = 16 + i * STRIDE + k * 4;
                let original = f32::from_le_bytes(output[at..at + 4].try_into().unwrap());
                output[at..at + 4].copy_from_slice(&(original + *d * weight).to_le_bytes());
            }
        }
        SceneBudget::default().validate(&output, self.bones)?;
        Ok(output)
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    fn mesh() -> Vec<u8> {
        let mut b = b"APXMESH1".to_vec();
        b.extend(3u32.to_le_bytes());
        b.extend(3u32.to_le_bytes());
        for p in [[0f32, 0., 0.], [1., 0., 0.], [0., 1., 0.]] {
            for x in p.into_iter().chain([0., 0., 1., 0., 0.]) {
                b.extend(x.to_le_bytes());
            }
            b.extend([0u8; 8]);
            for x in [1f32, 0., 0., 0.] {
                b.extend(x.to_le_bytes());
            }
        }
        for i in [0u32, 1, 2] {
            b.extend(i.to_le_bytes());
        }
        b
    }
    #[test]
    fn zero_is_byte_exact() {
        let b = mesh();
        let p = MorphPlan::new(&b, vec![[1.; 6]; 3], 1).unwrap();
        assert_eq!(p.apply(&b, 0.).unwrap(), b);
    }
    #[test]
    fn half_and_full_preserve_other_bytes() {
        let b = mesh();
        let p = MorphPlan::new(&b, vec![[1., 0., 0., 0., 0., 0.]; 3], 1).unwrap();
        for w in [0.5, 1.] {
            let out = p.apply(&b, w).unwrap();
            assert_eq!(f32::from_le_bytes(out[16..20].try_into().unwrap()), w);
            for i in 0..3 {
                let at = 16 + i * 56;
                assert_eq!(&out[at + 4..at + 56], &b[at + 4..at + 56]);
            }
            assert_eq!(&out[184..], &b[184..]);
        }
    }
    #[test]
    fn same_count_different_source_refuses() {
        let b = mesh();
        let p = MorphPlan::new(&b, vec![[0.; 6]; 3], 1).unwrap();
        let mut changed = b.clone();
        changed[16] = 1;
        assert_eq!(p.apply(&changed, 1.).unwrap_err(), "morph source changed");
    }
    #[test]
    fn bad_delta_and_weights_refuse() {
        let b = mesh();
        assert!(MorphPlan::new(&b, vec![[0.; 6]; 2], 1).is_err());
        assert!(MorphPlan::new(&b, vec![[f32::NAN; 6]; 3], 1).is_err());
        let p = MorphPlan::new(&b, vec![[0.; 6]; 3], 1).unwrap();
        for w in [-1., 1.1, f32::NAN] {
            assert!(p.apply(&b, w).is_err());
        }
    }
    #[test]
    fn invalid_result_refuses_original_untouched() {
        let b = mesh();
        let old = b.clone();
        let p = MorphPlan::new(&b, vec![[200.; 6]; 3], 1).unwrap();
        assert!(p.apply(&b, 1.).is_err());
        assert_eq!(b, old);
    }
}
