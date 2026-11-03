//! Borrowed APXMESH1 validation for reuse of Apex's existing preview assembler.
//! It does not authenticate asset SHA256, load textures, skin, or render a Sim.
//! Limits mirror the inspected native reader; scene totals are enforced separately.
pub const STRIDE: usize = 56;
const MAX_ASSET: usize = 32 * 1024 * 1024;
#[derive(Default, Debug, Clone, Copy)]
pub struct SceneBudget {
    vertices: u32,
    indices: u32,
}
pub struct MeshView<'a> {
    pub vertices: &'a [u8],
    pub indices: &'a [u8],
    pub vertex_count: u32,
    pub index_count: u32,
    pub minimum: [f32; 3],
    pub maximum: [f32; 3],
}
fn u32le(raw: &[u8], at: usize) -> u32 {
    u32::from_le_bytes(raw[at..at + 4].try_into().unwrap())
}
fn float(raw: &[u8], at: usize) -> f32 {
    f32::from_bits(u32le(raw, at))
}
impl SceneBudget {
    pub fn totals(&self) -> (u32, u32) {
        (self.vertices, self.indices)
    }
    pub fn validate<'a>(
        &mut self,
        raw: &'a [u8],
        bone_count: usize,
    ) -> Result<MeshView<'a>, &'static str> {
        if raw.len() < 16 || raw.len() > MAX_ASSET || &raw[..8] != b"APXMESH1" {
            return Err("mesh header/bound");
        }
        if bone_count == 0 || bone_count > 256 {
            return Err("bone count");
        }
        let n = u32le(raw, 8);
        let m = u32le(raw, 12);
        let total_n = self.vertices.checked_add(n).ok_or("scene count overflow")?;
        let total_m = self.indices.checked_add(m).ok_or("scene count overflow")?;
        if n == 0 || m == 0 || !m.is_multiple_of(3) || total_n > 1000000 || total_m > 6000000 {
            return Err("mesh scene counts");
        }
        let extent = 16u64 + u64::from(n) * STRIDE as u64 + u64::from(m) * 4;
        if extent != raw.len() as u64 {
            return Err("mesh exact extent");
        }
        let split = 16 + n as usize * STRIDE;
        let vertices = &raw[16..split];
        let indices = &raw[split..];
        let mut minimum = [f32::INFINITY; 3];
        let mut maximum = [f32::NEG_INFINITY; 3];
        for v in vertices.as_chunks::<STRIDE>().0 {
            for k in 0..3 {
                let p = float(v, k * 4);
                let normal = float(v, 12 + k * 4);
                if !p.is_finite() || p.abs() > 100.0 || !normal.is_finite() {
                    return Err("vertex numeric bounds");
                }
                minimum[k] = minimum[k].min(p);
                maximum[k] = maximum[k].max(p);
            }
            for k in 0..2 {
                let uv = float(v, 24 + k * 4);
                if !uv.is_finite() || uv.abs() > 100.0 {
                    return Err("UV numeric bounds");
                }
            }
            let mut sum = 0.0f32;
            for k in 0..4 {
                let joint =
                    u16::from_le_bytes(v[32 + k * 2..34 + k * 2].try_into().unwrap()) as usize;
                let weight = float(v, 40 + k * 4);
                if joint >= bone_count || !weight.is_finite() || !(0.0..=1.0).contains(&weight) {
                    return Err("skin weights/joints");
                }
                sum += weight;
            }
            if (sum - 1.0).abs() > 0.002 {
                return Err("weight sum");
            }
        }
        for i in indices.as_chunks::<4>().0 {
            if u32::from_le_bytes(*i) >= n {
                return Err("mesh index outside vertices");
            }
        }
        // Commit budget only after full validation; a rejected part consumes nothing.
        self.vertices = total_n;
        self.indices = total_m;
        Ok(MeshView {
            vertices,
            indices,
            vertex_count: n,
            index_count: m,
            minimum,
            maximum,
        })
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    fn fixture() -> Vec<u8> {
        let mut r = b"APXMESH1".to_vec();
        r.extend(3u32.to_le_bytes());
        r.extend(3u32.to_le_bytes());
        for p in [[0.0f32, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]] {
            for f in p.into_iter().chain([0.0, 0.0, 1.0, 0.0, 0.0]) {
                r.extend(f.to_le_bytes())
            }
            r.extend([0u8; 8]);
            for w in [1.0f32, 0.0, 0.0, 0.0] {
                r.extend(w.to_le_bytes())
            }
        }
        for i in [0u32, 1, 2] {
            r.extend(i.to_le_bytes())
        }
        r
    }
    #[test]
    fn borrowed_views_no_vertex_or_index_copy() {
        let raw = fixture();
        let mut budget = SceneBudget::default();
        let m = budget.validate(&raw, 1).unwrap();
        assert_eq!(m.vertices.as_ptr(), raw[16..].as_ptr());
        assert_eq!(m.indices.as_ptr(), raw[184..].as_ptr());
        assert_eq!(m.minimum, [0.0; 3]);
        assert_eq!(m.maximum, [1.0, 1.0, 0.0]);
        assert_eq!(budget.totals(), (3, 3));
    }
    #[test]
    fn all_truncations_and_trailing_byte_refuse_without_budget_use() {
        let raw = fixture();
        for n in 0..raw.len() {
            let mut b = SceneBudget::default();
            assert!(b.validate(&raw[..n], 1).is_err());
            assert_eq!(b.totals(), (0, 0));
        }
        let mut raw = raw;
        raw.push(0);
        assert!(SceneBudget::default().validate(&raw, 1).is_err());
    }
    #[test]
    fn invalid_numeric_joint_weight_and_index_cases() {
        let original = fixture();
        for (at, bytes) in [
            (16, f32::NAN.to_le_bytes().to_vec()),
            (16, 101f32.to_le_bytes().to_vec()),
            (28, f32::INFINITY.to_le_bytes().to_vec()),
            (40, 101f32.to_le_bytes().to_vec()),
            (48, 1u16.to_le_bytes().to_vec()),
            (56, (-0.1f32).to_le_bytes().to_vec()),
            (56, 0.4f32.to_le_bytes().to_vec()),
            (184, 3u32.to_le_bytes().to_vec()),
        ] {
            let mut raw = original.clone();
            raw[at..at + bytes.len()].copy_from_slice(&bytes);
            let mut b = SceneBudget::default();
            assert!(b.validate(&raw, 1).is_err(), "at{at}");
            assert_eq!(b.totals(), (0, 0));
        }
    }
    #[test]
    fn invalid_counts_and_bones_refuse() {
        let raw = fixture();
        for n in [0, u32::MAX, 1000001] {
            let mut r = raw.clone();
            r[8..12].copy_from_slice(&n.to_le_bytes());
            assert!(SceneBudget::default().validate(&r, 1).is_err())
        }
        for n in [0, 2, u32::MAX] {
            let mut r = raw.clone();
            r[12..16].copy_from_slice(&n.to_le_bytes());
            assert!(SceneBudget::default().validate(&r, 1).is_err())
        }
        assert!(SceneBudget::default().validate(&raw, 0).is_err());
        assert!(SceneBudget::default().validate(&raw, 257).is_err());
    }
    #[test]
    fn aggregate_scene_limit_is_not_per_mesh_only() {
        let raw = fixture();
        let mut b = SceneBudget {
            vertices: 999999,
            indices: 0,
        };
        assert!(b.validate(&raw, 1).is_err());
        assert_eq!(b.totals(), (999999, 0));
        let mut b = SceneBudget {
            vertices: 0,
            indices: 5999999,
        };
        assert!(b.validate(&raw, 1).is_err());
        assert_eq!(b.totals(), (0, 5999999));
    }
}
