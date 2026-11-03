//! Isolated row-band raster candidate. Same complete pixels, no triangle reordering.
//! Extra projected-scene retention and per-frame thread startup remain measured costs.
use super::{Frame, edge, f32_at, rotate};
use crate::mesh::{STRIDE, SceneBudget};
struct Projected<'a> {
    vertices: Vec<([f32; 3], [f32; 3])>,
    indices: &'a [u8],
}
fn triangle_ids(bytes: &[u8; 12]) -> [usize; 3] {
    std::array::from_fn(|i| {
        u32::from_le_bytes(bytes[i * 4..i * 4 + 4].try_into().unwrap()) as usize
    })
}
fn bounds(a: [f32; 3], b: [f32; 3], c: [f32; 3], w: usize, h: usize) -> [usize; 4] {
    [
        a[0].min(b[0]).min(c[0]).floor().max(0.) as usize,
        (a[0].max(b[0]).max(c[0]).ceil() as usize).min(w - 1),
        a[1].min(b[1]).min(c[1]).floor().max(0.) as usize,
        (a[1].max(b[1]).max(c[1]).ceil() as usize).min(h - 1),
    ]
}
fn band(
    meshes: &[Projected<'_>],
    rgb: &mut [u8],
    width: usize,
    height: usize,
    start: usize,
) -> usize {
    let rows = rgb.len() / (width * 3);
    let mut depth = vec![f32::NEG_INFINITY; rows * width];
    let mut covered = 0;
    for mesh in meshes {
        for triangle in mesh.indices.as_chunks::<12>().0 {
            let ids = triangle_ids(triangle);
            let [a, b, c] = [
                mesh.vertices[ids[0]].0,
                mesh.vertices[ids[1]].0,
                mesh.vertices[ids[2]].0,
            ];
            let area = edge(a, b, c[0], c[1]);
            if area.abs() < 1e-8 {
                continue;
            }
            let [min_x, max_x, min_y, max_y] = bounds(a, b, c, width, height);
            let min_y = min_y.max(start);
            let max_y = max_y.min(start + rows - 1);
            if min_y > max_y {
                continue;
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
                    let at = (y - start) * width + x;
                    if z <= depth[at] {
                        continue;
                    }
                    if !depth[at].is_finite() {
                        covered += 1;
                    }
                    depth[at] = z;
                    let mut n = [0f64; 3];
                    for (k, component) in n.iter_mut().enumerate() {
                        for j in 0..3 {
                            *component +=
                                f64::from(weights[j]) * f64::from(mesh.vertices[ids[j]].1[k]);
                        }
                    }
                    let length = (n[0] * n[0] + n[1] * n[1] + n[2] * n[2]).sqrt();
                    let diffuse = if length > 1e-8 {
                        ((n[0] * 0.3 + n[1] * 0.7 + n[2] * 0.65) / length).clamp(0., 1.)
                    } else {
                        0.
                    };
                    let shade = (55. + 185. * diffuse) as u8;
                    rgb[at * 3..at * 3 + 3].fill(shade);
                }
            }
        }
    }
    covered
}
pub fn render(
    inputs: &[(&[u8], usize)],
    width: usize,
    height: usize,
    yaw: f32,
    workers: usize,
) -> Result<Frame, &'static str> {
    if !(1..=4).contains(&workers) {
        return Err("preview worker bounds");
    }
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
    let projected: Vec<_> = meshes
        .iter()
        .map(|mesh| Projected {
            indices: mesh.indices,
            vertices: mesh
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
                .collect(),
        })
        .collect();
    let mut triangles = 0;
    let mut visits = 0usize;
    // Exact original global work bound, checked before any worker is started.
    for mesh in &projected {
        for t in mesh.indices.as_chunks::<12>().0 {
            let ids = triangle_ids(t);
            let [a, b, c] = [
                mesh.vertices[ids[0]].0,
                mesh.vertices[ids[1]].0,
                mesh.vertices[ids[2]].0,
            ];
            if edge(a, b, c[0], c[1]).abs() < 1e-8 {
                continue;
            }
            triangles += 1;
            let [x0, x1, y0, y1] = bounds(a, b, c, width, height);
            visits = visits
                .checked_add((x1 - x0 + 1) * (y1 - y0 + 1))
                .ok_or("preview work overflow")?;
            if visits > 64 * 1024 * 1024 {
                return Err("preview raster work budget");
            }
        }
    }
    let mut frame = Frame {
        width,
        height,
        rgb: vec![24; width * height * 3],
        covered_pixels: 0,
        triangles,
        stage_ms: None,
    };
    if workers == 1 {
        frame.covered_pixels = band(&projected, &mut frame.rgb, width, height, 0);
        return Ok(frame);
    }
    let band_rows = height.div_ceil(workers);
    frame.covered_pixels = std::thread::scope(|scope| {
        let mut jobs = Vec::new();
        let mut spawn_failed = false;
        for (index, rgb) in frame.rgb.chunks_mut(band_rows * width * 3).enumerate() {
            let meshes = &projected;
            match std::thread::Builder::new()
                .stack_size(512 * 1024)
                .spawn_scoped(scope, move || {
                    band(meshes, rgb, width, height, index * band_rows)
                }) {
                Ok(job) => jobs.push(job),
                Err(_) => {
                    spawn_failed = true;
                    break;
                }
            }
        }
        let mut total = 0;
        let mut panicked = false;
        // Join every started worker, including after a failed spawn or panic.
        for job in jobs {
            match job.join() {
                Ok(n) => total += n,
                Err(_) => panicked = true,
            }
        }
        if spawn_failed {
            Err("preview worker creation failed")
        } else if panicked {
            Err("preview worker panicked")
        } else {
            Ok(total)
        }
    })?;
    Ok(frame)
}
#[cfg(test)]
mod tests {
    use super::*;
    use crate::preview::{render as baseline, tests::fixture};
    fn same(input: &[(&[u8], usize)], w: usize, h: usize, yaw: f32) {
        let old = baseline(input, w, h, yaw);
        for workers in 1..=4 {
            let new = render(input, w, h, yaw, workers);
            match (&old, new) {
                (Ok(a), Ok(b)) => {
                    assert_eq!(a.rgb, b.rgb, "workers={workers} yaw={yaw}");
                    assert_eq!(a.covered_pixels, b.covered_pixels);
                    assert_eq!(a.triangles, b.triangles);
                    assert_eq!((a.width, a.height), (b.width, b.height));
                }
                (Err(a), Err(b)) => assert_eq!(*a, b),
                _ => panic!("different acceptance"),
            }
        }
    }
    #[test]
    fn complete_frames_match_across_bands_and_views() {
        let mut near = fixture(0.2, [0., 0., 1.], false);
        for (i, n) in [[-1f32, 0., 1.], [1., 0., 1.], [0., 1., 1.]]
            .iter()
            .enumerate()
        {
            for (k, v) in n.iter().enumerate() {
                near[16 + i * 56 + 12 + k * 4..16 + i * 56 + 16 + k * 4]
                    .copy_from_slice(&v.to_le_bytes());
            }
        }
        let far = fixture(-0.2, [0., 0., -1.], true);
        for (w, h) in [(16, 16), (33, 65), (128, 67)] {
            for yaw in [-3.1, -1.5, -0.1, 0., 0.7, 1.5, 3.1] {
                same(&[(&near, 1), (&far, 1)], w, h, yaw);
                same(&[(&far, 1), (&near, 1)], w, h, yaw);
            }
        }
    }
    #[test]
    fn ties_and_extreme_normals_match() {
        let a = fixture(0., [f32::MAX; 3], false);
        let b = fixture(0., [0., 0., -1.], true);
        same(&[(&a, 1), (&b, 1)], 64, 65, 0.);
        same(&[(&b, 1), (&a, 1)], 64, 65, 0.);
    }
    #[test]
    fn malformed_inputs_and_worker_bounds_refuse() {
        let a = fixture(0., [0., 0., 1.], false);
        same(&[(&a[..40], 1)], 64, 64, 0.);
        same(&[], 64, 64, 0.);
        same(&[(&a, 1)], 0, 64, 0.);
        same(&[(&a, 1)], 64, 64, f32::NAN);
        for workers in [0, 5, usize::MAX] {
            assert_eq!(
                render(&[(&a, 1)], 64, 64, 0., workers).unwrap_err(),
                "preview worker bounds"
            );
        }
    }
    #[test]
    fn original_overdraw_budget_is_retained() {
        let mut a = fixture(0., [0., 0., 1.], false);
        a.truncate(16 + 3 * 56);
        a[12..16].copy_from_slice(&(3u32 * 1000).to_le_bytes());
        for _ in 0..1000 {
            for i in [0u32, 1, 2] {
                a.extend(i.to_le_bytes());
            }
        }
        same(&[(&a, 1)], 1024, 1024, 0.);
    }
}

#[cfg(test)]
mod differential_tests {
 use super::*;
 struct Rng(u64);
 impl Rng {fn unit(&mut self)->f32 {self.0^=self.0<<13;self.0^=self.0>>7;self.0^=self.0<<17;((self.0>>40) as f32/16777215.)*2.-1.}}
 fn mesh(rng:&mut Rng,case:usize)->Vec<u8>{
  let n=12u32;let mut bytes=b"APXMESH1".to_vec();bytes.extend(n.to_le_bytes());bytes.extend(n.to_le_bytes());
  for i in 0..n {
   let mut p=[rng.unit()*2.,rng.unit()*3.,rng.unit()];
   if case%7==0 && i<3 {p=[0.;3];}
   let normal=if case%11==0 {[f32::MAX;3]} else {[rng.unit(),rng.unit(),rng.unit()]};
   for x in p.into_iter().chain(normal).chain([0.,0.]){bytes.extend(x.to_le_bytes());}
   bytes.extend([0u8;8]);for x in [1f32,0.,0.,0.]{bytes.extend(x.to_le_bytes());}
  }
  for i in 0..n {bytes.extend(i.to_le_bytes());}bytes
 }
 #[test] fn varied_complete_pixels_match_serial_for_all_worker_counts(){
  let mut rng=Rng(0x72a819e10f4d339b);
  for case in 0..72 {
   let a=mesh(&mut rng,case);let b=if case%6==0 {a.clone()} else {mesh(&mut rng,case+1)};
   let (w,h)=[(16,17),(31,65),(64,33),(95,47)][case%4];
   let yaw=[-3.1f32,-1.5,-0.01,0.,0.7,1.5,3.1][case%7];
   for reverse in [false,true] {
    let inputs:Vec<(&[u8],usize)>=if reverse {vec![(&b,1),(&a,1)]}else{vec![(&a,1),(&b,1)]};
    let serial=crate::preview::render(&inputs,w,h,yaw).expect("valid bounded scene");
    for workers in 1..=4 {
     let tiled=render(&inputs,w,h,yaw,workers).expect("valid tiled scene");
     assert_eq!(serial.rgb,tiled.rgb,"case={case} reversed={reverse} workers={workers}");
     assert_eq!((serial.covered_pixels,serial.triangles,serial.width,serial.height),(tiled.covered_pixels,tiled.triangles,tiled.width,tiled.height));
    }
   }
  }
 }
}
