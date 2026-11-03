//! Isolated linear-blend rigid-pose diagnostic. Caller supplies verified
//! bind-to-posed matrices; this module does not infer a Sim's rig or animation.
use crate::mesh::{STRIDE, SceneBudget};
pub const IDENTITY: [f32; 12] = [1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1., 0.];
fn read(v: &[u8], at: usize) -> f64 {
    f64::from(f32::from_le_bytes(v[at..at + 4].try_into().unwrap()))
}
pub fn pose_rigid(raw: &[u8], matrices: &[[f32; 12]]) -> Result<Vec<u8>, &'static str> {
    let mesh = SceneBudget::default().validate(raw, matrices.len())?;
    for m in matrices {
        if m.iter().any(|v| !v.is_finite()) {
            return Err("nonfinite pose");
        }
        for i in 0..3 {
            for j in 0..3 {
                let dot = (0..3)
                    .map(|k| f64::from(m[i * 4 + k]) * f64::from(m[j * 4 + k]))
                    .sum::<f64>();
                if (dot - if i == j { 1. } else { 0. }).abs() > 1e-4 {
                    return Err("non-rigid pose");
                }
            }
        }
        let determinant = f64::from(m[0])
            * (f64::from(m[5]) * f64::from(m[10]) - f64::from(m[6]) * f64::from(m[9]))
            - f64::from(m[1])
                * (f64::from(m[4]) * f64::from(m[10]) - f64::from(m[6]) * f64::from(m[8]))
            + f64::from(m[2])
                * (f64::from(m[4]) * f64::from(m[9]) - f64::from(m[5]) * f64::from(m[8]));
        if (determinant - 1.).abs() > 1e-4 {
            return Err("pose reflection");
        }
    }
    let mut output = raw.to_vec();
    for (i, v) in mesh.vertices.as_chunks::<STRIDE>().0.iter().enumerate() {
        let mut position = [0f64; 3];
        let mut normal = [0f64; 3];
        let mut total = 0.;
        for influence in 0..4 {
            let weight = read(v, 40 + influence * 4);
            if weight == 0. {
                continue;
            }
            total += weight;
            let joint = u16::from_le_bytes(
                v[32 + influence * 2..34 + influence * 2]
                    .try_into()
                    .unwrap(),
            ) as usize;
            let m = &matrices[joint];
            for k in 0..3 {
                position[k] += weight
                    * ((0..3)
                        .map(|j| f64::from(m[k * 4 + j]) * read(v, j * 4))
                        .sum::<f64>()
                        + f64::from(m[k * 4 + 3]));
                normal[k] += weight
                    * (0..3)
                        .map(|j| f64::from(m[k * 4 + j]) * read(v, 12 + j * 4))
                        .sum::<f64>();
            }
        }
        let length = normal.iter().map(|x| x * x).sum::<f64>().sqrt();
        for k in 0..3 {
            let p = (position[k] / total) as f32;
            let n = if length > 1e-15 {
                (normal[k] / length) as f32
            } else {
                0.
            };
            let at = 16 + i * STRIDE;
            output[at + k * 4..at + k * 4 + 4].copy_from_slice(&p.to_le_bytes());
            output[at + 12 + k * 4..at + 16 + k * 4].copy_from_slice(&n.to_le_bytes());
        }
    }
    SceneBudget::default().validate(&output, matrices.len())?;
    Ok(output)
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
            for w in [1f32, 0., 0., 0.] {
                b.extend(w.to_le_bytes());
            }
        }
        for i in [0u32, 1, 2] {
            b.extend(i.to_le_bytes());
        }
        b
    }
    #[test]
    fn identity_byte_exact_and_input_untouched() {
        let b = mesh();
        let old = b.clone();
        assert_eq!(pose_rigid(&b, &[IDENTITY]).unwrap(), b);
        assert_eq!(b, old);
    }
    #[test]
    fn translation_moves_positions_only() {
        let b = mesh();
        let mut m = IDENTITY;
        m[3] = 2.;
        m[7] = 3.;
        let out = pose_rigid(&b, &[m]).unwrap();
        assert_eq!(read(&out, 16), 2.);
        assert_eq!(read(&out, 20), 3.);
        for i in 0..3 {
            let at = 16 + i * STRIDE;
            assert_eq!(&out[at + 12..at + STRIDE], &b[at + 12..at + STRIDE]);
        }
        assert_eq!(&out[184..], &b[184..]);
    }
    #[test]
    fn quarter_turn_rotates_positions() {
        let b = mesh();
        let m = [0., -1., 0., 0., 1., 0., 0., 0., 0., 0., 1., 0.];
        let out = pose_rigid(&b, &[m]).unwrap();
        assert_eq!(read(&out, 16 + 56), 0.);
        assert_eq!(read(&out, 20 + 56), 1.);
    }
    #[test]
    fn invalid_transform_refuses() {
        let b = mesh();
        let mut m = IDENTITY;
        m[0] = 2.;
        assert!(pose_rigid(&b, &[m]).is_err());
        m = IDENTITY;
        m[0] = -1.;
        assert!(pose_rigid(&b, &[m]).is_err());
        m = IDENTITY;
        m[3] = f32::NAN;
        assert!(pose_rigid(&b, &[m]).is_err());
        m = IDENTITY;
        m[3] = 200.;
        assert!(pose_rigid(&b, &[m]).is_err());
    }
    #[test]
    fn missing_rig_refuses() {
        assert!(pose_rigid(&mesh(), &[]).is_err());
    }
}
