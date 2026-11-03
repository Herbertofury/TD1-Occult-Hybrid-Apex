#![allow(dead_code)]
// Frozen ad7edf6 opaque renderer; only module paths adjusted, tests omitted.
//! Bounded CPU diagnostic preview of validated APXMESH1 rest-pose geometry.
//! Optional opaque diffuse sampling; posing/morphing remain caller operations.
//! Not native CAS, layered/transparent materials, or game Sim authority.
use apex_external_cas_draft_research::mesh::{STRIDE, SceneBudget};
use apex_external_cas_draft_research::preview::texture;

#[derive(Debug)]
pub struct Frame {
    pub width: usize,
    pub height: usize,
    pub rgb: Vec<u8>,
    pub covered_pixels: usize,
    pub triangles: usize,
}
fn f32_at(v: &[u8], i: usize) -> f32 {
    f32::from_le_bytes(v[i..i + 4].try_into().unwrap())
}
fn edge(a: [f32; 3], b: [f32; 3], x: f32, y: f32) -> f32 {
    (b[0] - a[0]) * (y - a[1]) - (b[1] - a[1]) * (x - a[0])
}
fn rotate(p: [f32; 3], cos: f32, sin: f32) -> [f32; 3] {
    [cos * p[0] + sin * p[2], p[1], -sin * p[0] + cos * p[2]]
}
pub fn render(
    inputs: &[(&[u8], usize)],
    width: usize,
    height: usize,
    yaw: f32,
) -> Result<Frame, &'static str> {
    render_impl::<false>(inputs, width, height, yaw, &[], &[])
}
pub fn render_textured(
    inputs: &[(&[u8], usize)],
    width: usize,
    height: usize,
    yaw: f32,
    textures: &[texture::OpaqueTexture<'_>],
    materials: &[usize],
) -> Result<Frame, &'static str> {
    if textures.is_empty()
        || textures.len() > 3
        || materials.len() != inputs.len()
        || materials.iter().any(|i| *i >= textures.len())
    {
        return Err("preview material mapping bounds");
    }
    render_impl::<true>(inputs, width, height, yaw, textures, materials)
}
fn render_impl<const TEXTURED: bool>(
    inputs: &[(&[u8], usize)],
    width: usize,
    height: usize,
    yaw: f32,
    textures: &[texture::OpaqueTexture<'_>],
    materials: &[usize],
) -> Result<Frame, &'static str> {
    if !(16..=1024).contains(&width)
        || !(16..=1024).contains(&height)
        || !yaw.is_finite()
        || inputs.is_empty()
        || inputs.len() > 64
    {
        return Err("preview input bounds");
    }
    let mut budget = SceneBudget::default();
    let meshes: Vec<_> = inputs
        .iter()
        .map(|(bytes, bones)| budget.validate(bytes, *bones))
        .collect::<Result<_, _>>()?;
    let (sin, cos) = yaw.sin_cos();
    let mut lo = [f32::INFINITY; 3];
    let mut hi = [f32::NEG_INFINITY; 3];
    for mesh in &meshes {
        for v in mesh.vertices.as_chunks::<STRIDE>().0 {
            let p = rotate([f32_at(v, 0), f32_at(v, 4), f32_at(v, 8)], cos, sin);
            for k in 0..3 {
                lo[k] = lo[k].min(p[k]);
                hi[k] = hi[k].max(p[k]);
            }
        }
    }
    let span_x = (hi[0] - lo[0]).max(1e-6);
    let span_y = (hi[1] - lo[1]).max(1e-6);
    let scale = ((width as f32 * 0.9) / span_x).min((height as f32 * 0.9) / span_y);
    let center = [(lo[0] + hi[0]) * 0.5, (lo[1] + hi[1]) * 0.5];
    let pixels = width * height;
    let mut frame = Frame {
        width,
        height,
        rgb: vec![24; pixels * 3],
        covered_pixels: 0,
        triangles: 0,
    };
    let mut depth = vec![f32::NEG_INFINITY; pixels];
    let mut pixel_visits = 0usize;
    for (mesh_index, mesh) in meshes.iter().enumerate() {
        let projected: Vec<_> = mesh
            .vertices
            .as_chunks::<STRIDE>()
            .0
            .iter()
            .map(|v| {
                let p = rotate([f32_at(v, 0), f32_at(v, 4), f32_at(v, 8)], cos, sin);
                let normal = rotate([f32_at(v, 12), f32_at(v, 16), f32_at(v, 20)], cos, sin);
                (
                    [
                        (p[0] - center[0]) * scale + width as f32 * 0.5,
                        height as f32 * 0.5 - (p[1] - center[1]) * scale,
                        p[2],
                    ],
                    normal,
                )
            })
            .collect();
        for triangle in mesh.indices.as_chunks::<12>().0 {
            let ids: [usize; 3] = std::array::from_fn(|i| {
                u32::from_le_bytes(triangle[i * 4..i * 4 + 4].try_into().unwrap()) as usize
            });
            let [a, b, c] = [
                projected[ids[0]].0,
                projected[ids[1]].0,
                projected[ids[2]].0,
            ];
            let area = edge(a, b, c[0], c[1]);
            if area.abs() < 1e-8 {
                continue;
            }
            frame.triangles += 1;
            let min_x = a[0].min(b[0]).min(c[0]).floor().max(0.) as usize;
            let max_x = (a[0].max(b[0]).max(c[0]).ceil() as usize).min(width - 1);
            let min_y = a[1].min(b[1]).min(c[1]).floor().max(0.) as usize;
            let max_y = (a[1].max(b[1]).max(c[1]).ceil() as usize).min(height - 1);
            let visits = (max_x - min_x + 1) * (max_y - min_y + 1);
            pixel_visits = pixel_visits
                .checked_add(visits)
                .ok_or("preview work overflow")?;
            if pixel_visits > 64 * 1024 * 1024 {
                return Err("preview raster work budget");
            }
            for y in min_y..=max_y {
                for x in min_x..=max_x {
                    let weights = [
                        edge(b, c, x as f32 + 0.5, y as f32 + 0.5) / area,
                        edge(c, a, x as f32 + 0.5, y as f32 + 0.5) / area,
                        edge(a, b, x as f32 + 0.5, y as f32 + 0.5) / area,
                    ];
                    if weights.iter().any(|w| *w < -1e-6) {
                        continue;
                    }
                    let z = weights[0] * a[2] + weights[1] * b[2] + weights[2] * c[2];
                    let at = y * width + x;
                    if z <= depth[at] {
                        continue;
                    }
                    if !depth[at].is_finite() {
                        frame.covered_pixels += 1;
                    }
                    depth[at] = z;
                    let mut n = [0f64; 3];
                    for (k, component) in n.iter_mut().enumerate() {
                        for j in 0..3 {
                            *component += f64::from(weights[j]) * f64::from(projected[ids[j]].1[k]);
                        }
                    }
                    let length = (n[0] * n[0] + n[1] * n[1] + n[2] * n[2]).sqrt();
                    let diffuse = if length > 1e-8 {
                        ((n[0] * 0.3 + n[1] * 0.7 + n[2] * 0.65) / length).clamp(0., 1.)
                    } else {
                        0.
                    };
                    let shade = (55. + 185. * diffuse) as u8;
                    if TEXTURED {
                        let mut uv = [0f64; 2];
                        for (j, id) in ids.iter().enumerate() {
                            let vertex = &mesh.vertices[id * STRIDE..(id + 1) * STRIDE];
                            for (k, component) in uv.iter_mut().enumerate() {
                                *component +=
                                    f64::from(weights[j]) * f64::from(f32_at(vertex, 24 + k * 4));
                            }
                        }
                        let color = textures[materials[mesh_index]].sample(uv)?;
                        for (k, value) in color.iter().enumerate() {
                            frame.rgb[at * 3 + k] =
                                (value * f64::from(shade) / 255.).round().clamp(0., 255.) as u8;
                        }
                    } else {
                        frame.rgb[at * 3..at * 3 + 3].fill(shade);
                    }
                }
            }
        }
    }
    Ok(frame)
}
