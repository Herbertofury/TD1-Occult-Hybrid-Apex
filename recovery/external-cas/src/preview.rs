//! Bounded CPU diagnostic preview of validated APXMESH1 rest-pose geometry.
//! Optional opaque diffuse sampling; posing/morphing remain caller operations.
//! Not native CAS, layered/transparent materials, or game Sim authority.
use crate::mesh::{STRIDE, SceneBudget};
pub mod color_shift;
pub mod layers;
pub mod skin_detail;
pub mod texture;
pub mod tiled;
#[derive(Debug)]
pub struct Frame {
    pub width: usize,
    pub height: usize,
    pub rgb: Vec<u8>,
    pub covered_pixels: usize,
    pub triangles: usize,
    pub stage_ms: Option<[f64; 3]>,
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
/// Immutable world-space envelope. Geometry outside it is rejected, never clipped.
#[derive(Clone, Copy, Debug)]
pub struct FramingBounds {
    lo: [f32; 3],
    hi: [f32; 3],
}
impl FramingBounds {
    pub fn new(lo: [f32; 3], hi: [f32; 3]) -> Result<Self, &'static str> {
        if (0..3).any(|i| {
            !lo[i].is_finite()
                || !hi[i].is_finite()
                || lo[i] > hi[i]
                || lo[i].abs() > 1e6
                || hi[i].abs() > 1e6
        }) {
            return Err("invalid framing envelope");
        }
        Ok(Self { lo, hi })
    }
    pub fn contains(&self, p: [f32; 3]) -> bool {
        (0..3).all(|i| p[i].is_finite() && p[i] >= self.lo[i] && p[i] <= self.hi[i])
    }
}
#[derive(Clone, Copy, Debug)]
pub struct Camera {
    pub yaw: f32,
    pub framing: Option<FramingBounds>,
}
impl From<f32> for Camera {
    fn from(yaw: f32) -> Self {
        Self { yaw, framing: None }
    }
}
#[derive(Clone, Copy)]
struct RenderView { camera: Camera, rows: Option<(usize,usize)> }
impl From<Camera> for RenderView { fn from(camera:Camera)->Self { Self{camera,rows:None} } }
#[derive(Clone, Copy)]
pub struct RasterBand { pub camera:Camera, pub first_row:usize, pub past_last_row:usize }
/// A cropped worker result, never publishable as a full scene without joining all rows.
pub struct BandFrame { pub rows:(usize,usize), pub frame:Frame }
pub fn render(
    inputs: &[(&[u8], usize)],
    width: usize,
    height: usize,
    yaw: f32,
) -> Result<Frame, &'static str> {
    render_impl::<false>(inputs, width, height, Camera::from(yaw), &[], &[], None)
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
    render_impl::<true>(inputs, width, height, Camera::from(yaw), textures, materials, None)
}
/// Explicit alpha-test diagnostic. No translucent blending or game shader parity.
pub fn render_textured_cutout(
    inputs: &[(&[u8], usize)],
    width: usize,
    height: usize,
    yaw: f32,
    textures: &[texture::OpaqueTexture<'_>],
    materials: &[usize],
    masks: &[Option<texture::AlphaMask<'_>>],
) -> Result<Frame, &'static str> {
    render_textured_cutout_camera(
        inputs,
        width,
        height,
        Camera::from(yaw),
        textures,
        materials,
        masks,
    )
}
/// Fixed-envelope variant for callers that have validated a complete pose range.
pub fn render_textured_cutout_camera(inputs:&[(&[u8],usize)],width:usize,height:usize,camera:Camera,textures:&[texture::OpaqueTexture<'_>],materials:&[usize],masks:&[Option<texture::AlphaMask<'_>>])->Result<Frame,&'static str> {
    render_textured_cutout_view(inputs,width,height,camera.into(),textures,materials,masks)
}
pub fn render_textured_cutout_band(inputs:&[(&[u8],usize)],width:usize,height:usize,band:RasterBand,textures:&[texture::OpaqueTexture<'_>],materials:&[usize],masks:&[Option<texture::AlphaMask<'_>>])->Result<BandFrame,&'static str> {
    let rows=(band.first_row,band.past_last_row);
    let frame=render_textured_cutout_view(inputs,width,height,RenderView{camera:band.camera,rows:Some(rows)},textures,materials,masks)?;
    Ok(BandFrame{rows,frame})
}
fn render_textured_cutout_view(
    inputs: &[(&[u8], usize)],
    width: usize,
    height: usize,
    camera: RenderView,
    textures: &[texture::OpaqueTexture<'_>],
    materials: &[usize],
    masks: &[Option<texture::AlphaMask<'_>>],
) -> Result<Frame, &'static str> {
    if textures.is_empty()
        || textures.len() > 3
        || materials.len() != inputs.len()
        || materials.iter().any(|i| *i >= textures.len())
        || masks.len() != textures.len()
    {
        return Err("preview material mapping bounds");
    }
    if masks
        .iter()
        .zip(textures)
        .any(|(m, t)| m.as_ref().is_some_and(|m| m.dimensions() != t.dimensions()))
    {
        return Err("cutout mask dimensions");
    }
    render_impl::<true>(
        inputs,
        width,
        height,
        camera,
        textures,
        materials,
        Some(masks),
    )
}
fn render_impl<const TEXTURED: bool>(
    inputs: &[(&[u8], usize)],
    width: usize,
    height: usize,
    camera: impl Into<RenderView>,
    textures: &[texture::OpaqueTexture<'_>],
    materials: &[usize],
    masks: Option<&[Option<texture::AlphaMask<'_>>]>,
) -> Result<Frame, &'static str> {
    let view = camera.into();
    let camera = view.camera;
    let yaw = camera.yaw;
    if !(16..=1024).contains(&width)
        || !(16..=1024).contains(&height)
        || !yaw.is_finite()
        || inputs.is_empty()
        || inputs.len() > 64
    {
        return Err("preview input bounds");
    }
    let (first_row,past_last_row)=view.rows.unwrap_or((0,height));
    if first_row>=past_last_row || past_last_row>height { return Err("raster band bounds"); }
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
            let world = [f32_at(v, 0), f32_at(v, 4), f32_at(v, 8)];
            if camera.framing.is_some_and(|b| !b.contains(world)) {
                return Err("geometry outside framing envelope");
            }
            if camera.framing.is_none() {
                let p = rotate(world, cos, sin);
                for k in 0..3 {
                    lo[k] = lo[k].min(p[k]);
                    hi[k] = hi[k].max(p[k]);
                }
            }
        }
    }
    if let Some(bounds) = camera.framing {
        for corner in 0..8 {
            let world = std::array::from_fn(|k| {
                if corner & (1 << k) == 0 {
                    bounds.lo[k]
                } else {
                    bounds.hi[k]
                }
            });
            let p = rotate(world, cos, sin);
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
    let pixels = width * (past_last_row-first_row);
    let mut frame = Frame {
        width,
        height: past_last_row-first_row,
        rgb: vec![24; pixels * 3],
        covered_pixels: 0,
        triangles: 0,
        stage_ms: None,
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
            let min_y=min_y.max(first_row);
            let max_y=max_y.min(past_last_row-1);
            if min_y>max_y { continue; }
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
                    let at = (y-first_row) * width + x;
                    if z <= depth[at] {
                        continue;
                    }

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
                        if let Some(mask) = masks.and_then(|m| m[materials[mesh_index]].as_ref())
                            && !mask.visible(uv)?
                        {
                            continue;
                        }
                        let color = textures[materials[mesh_index]].sample(uv)?;
                        for (k, value) in color.iter().enumerate() {
                            frame.rgb[at * 3 + k] =
                                (value * f64::from(shade) / 255.).round().clamp(0., 255.) as u8;
                        }
                    } else {
                        frame.rgb[at * 3..at * 3 + 3].fill(shade);
                    }
                    if !depth[at].is_finite() {
                        frame.covered_pixels += 1;
                    }
                    depth[at] = z;
                }
            }
        }
    }
    Ok(frame)
}
#[cfg(test)]
mod tests {
    use super::*;
    pub(super) fn fixture(z: f32, normal: [f32; 3], reverse: bool) -> Vec<u8> {
        let mut b = b"APXMESH1".to_vec();
        b.extend(3u32.to_le_bytes());
        b.extend(3u32.to_le_bytes());
        for p in [[-1., -1., z], [1., -1., z], [0., 1., z]] {
            for f in p.into_iter().chain(normal).chain([0., 0.]) {
                b.extend(f.to_le_bytes());
            }
            b.extend([0u8; 8]);
            for f in [1f32, 0., 0., 0.] {
                b.extend(f.to_le_bytes());
            }
        }
        for i in if reverse { [2u32, 1, 0] } else { [0u32, 1, 2] } {
            b.extend(i.to_le_bytes());
        }
        b
    }
    #[test]
    fn fixed_framing_rejects_invalid_and_outside_geometry() {
        assert!(FramingBounds::new([f32::NAN; 3], [1.; 3]).is_err());
        assert!(FramingBounds::new([2.; 3], [1.; 3]).is_err());
        assert!(FramingBounds::new([0.; 3], [f32::INFINITY; 3]).is_err());
        let mesh = fixture(0., [0., 0., 1.], false);
        let bounds = FramingBounds::new([-0.5; 3], [0.5; 3]).unwrap();
        let result = render_impl::<false>(
            &[(&mesh, 1)],
            64,
            64,
            Camera {
                yaw: 0.,
                framing: Some(bounds),
            },
            &[],
            &[],
            None,
        );
        assert_eq!(result.unwrap_err(), "geometry outside framing envelope");
    }
    #[test]
    fn fixed_framing_matches_equivalent_auto_and_does_not_pump() {
        let mesh = fixture(0., [0., 0., 1.], false);
        let tight = FramingBounds::new([-1., -1., 0.], [1., 1., 0.]).unwrap();
        let fixed = |inputs: &[(&[u8], usize)], bounds| {
            render_impl::<false>(
                inputs,
                64,
                64,
                Camera {
                    yaw: 0.,
                    framing: Some(bounds),
                },
                &[],
                &[],
                None,
            )
            .unwrap()
            .rgb
        };
        assert_eq!(
            fixed(&[(&mesh, 1)], tight),
            render(&[(&mesh, 1)], 64, 64, 0.).unwrap().rgb
        );
        // Degenerate indexed geometry affects auto-fit, but cannot paint pixels.
        let mut moved = fixture(0., [0., 0., 1.], false);
        moved[16 + 3 * STRIDE..].fill(0);
        for i in 0..3 {
            moved[16 + i * STRIDE + 4..20 + i * STRIDE + 4].copy_from_slice(&2f32.to_le_bytes());
        }
        let bounds = FramingBounds::new([-1., -1., 0.], [1., 2., 0.]).unwrap();
        assert_eq!(
            fixed(&[(&mesh, 1)], bounds),
            fixed(&[(&mesh, 1), (&moved, 1)], bounds)
        );
        assert_ne!(
            render(&[(&mesh, 1)], 64, 64, 0.).unwrap().rgb,
            render(&[(&mesh, 1), (&moved, 1)], 64, 64, 0.).unwrap().rgb
        );
    }
    #[test]
    fn transparent_near_surface_does_not_occlude_far_surface() {
        let near = fixture(1., [0., 0., 1.], false);
        let far = fixture(-1., [0., 0., 1.], false);
        let white = [255; 4];
        let red = [255, 0, 0, 255];
        let transparent = [0; 4];
        let textures = [
            texture::OpaqueTexture::new(1, 1, &white).unwrap(),
            texture::OpaqueTexture::new(1, 1, &red).unwrap(),
        ];
        let masks = [
            Some(texture::AlphaMask::new(1, 1, &transparent, 128).unwrap()),
            None,
        ];
        let a = render_textured_cutout(
            &[(&near, 1), (&far, 1)],
            64,
            64,
            0.,
            &textures,
            &[0, 1],
            &masks,
        )
        .unwrap();
        let b = render_textured_cutout(
            &[(&far, 1), (&near, 1)],
            64,
            64,
            0.,
            &textures,
            &[1, 0],
            &masks,
        )
        .unwrap();
        let reference =
            render_textured(&[(&near, 1), (&far, 1)], 64, 64, 0., &textures, &[1, 1]).unwrap();
        assert_eq!(a.rgb, b.rgb);
        assert_eq!(a.rgb, reference.rgb);
        assert_eq!(a.covered_pixels, b.covered_pixels);
    }
    #[test]
    fn opaque_masks_match_existing_complete_frame() {
        let a = fixture(0., [0., 0., 1.], false);
        let bytes = [34, 94, 190, 255];
        let textures = [texture::OpaqueTexture::new(1, 1, &bytes).unwrap()];
        let masks = [Some(texture::AlphaMask::new(1, 1, &bytes, 128).unwrap())];
        let old = render_textured(&[(&a, 1)], 64, 64, 0., &textures, &[0]).unwrap();
        let new = render_textured_cutout(&[(&a, 1)], 64, 64, 0., &textures, &[0], &masks).unwrap();
        assert_eq!(old.rgb, new.rgb);
        assert_eq!(old.covered_pixels, new.covered_pixels);
        assert_eq!(old.triangles, new.triangles);
        assert!(render_textured_cutout(&[(&a, 1)], 64, 64, 0., &textures, &[0], &[]).is_err());
    }
    #[test]
    fn triangle_visible_and_winding_independent() {
        let a = fixture(0., [0., 0., 1.], false);
        let b = fixture(0., [0., 0., 1.], true);
        let fa = render(&[(&a, 1)], 64, 64, 0.).unwrap();
        let fb = render(&[(&b, 1)], 64, 64, 0.).unwrap();
        assert!(fa.covered_pixels > 1000);
        assert_eq!(fa.covered_pixels, fb.covered_pixels);
        assert_eq!(fa.rgb, fb.rgb);
    }
    #[test]
    fn near_surface_wins_in_both_submission_orders() {
        let near = fixture(1., [0., 0., 1.], false);
        let far = fixture(-1., [0., 0., -1.], false);
        let a = render(&[(&near, 1), (&far, 1)], 64, 64, 0.).unwrap();
        let b = render(&[(&far, 1), (&near, 1)], 64, 64, 0.).unwrap();
        assert_eq!(a.rgb, b.rgb);
        assert!(a.rgb[(32 * 64 + 32) * 3] > 150);
    }
    #[test]
    fn input_bounds_and_empty_refuse() {
        let a = fixture(0., [0., 0., 1.], false);
        for (w, h, yaw) in [(0, 64, 0.), (1025, 64, 0.), (64, 64, f32::NAN)] {
            assert!(render(&[(&a, 1)], w, h, yaw).is_err());
        }
        assert!(render(&[], 64, 64, 0.).is_err());
    }
    #[test]
    fn invalid_mesh_refuses_even_after_valid_mesh() {
        let a = fixture(0., [0., 0., 1.], false);
        assert!(render(&[(&a, 1), (&a[..40], 1)], 64, 64, 0.).is_err());
    }
    #[test]
    fn extreme_finite_normals_produce_visible_geometry() {
        let a = fixture(0., [f32::MAX; 3], false);
        let f = render(&[(&a, 1)], 64, 64, 0.).unwrap();
        assert!(f.rgb[(32 * 64 + 32) * 3] > 150);
    }
    #[test]
    fn excessive_overdraw_refuses_instead_of_unbounded_work() {
        let mut a = fixture(0., [0., 0., 1.], false);
        a.truncate(16 + 3 * 56);
        a[12..16].copy_from_slice(&(3u32 * 1000).to_le_bytes());
        for _ in 0..1000 {
            for i in [0u32, 1, 2] {
                a.extend(i.to_le_bytes());
            }
        }
        assert_eq!(
            render(&[(&a, 1)], 1024, 1024, 0.).unwrap_err(),
            "preview raster work budget"
        );
    }
    #[test]
    fn opaque_white_material_preserves_every_baseline_pixel() {
        let bytes = [255u8; 4];
        let textures = [texture::OpaqueTexture::new(1, 1, &bytes).unwrap()];
        for reverse in [false, true] {
            for yaw in [0., 0.3, 1.7] {
                let mesh = fixture(0., [0.1, 0.2, 1.], reverse);
                let base = render(&[(&mesh, 1)], 64, 96, yaw).unwrap();
                let textured =
                    render_textured(&[(&mesh, 1)], 64, 96, yaw, &textures, &[0]).unwrap();
                assert_eq!(base.rgb, textured.rgb);
                assert_eq!(base.covered_pixels, textured.covered_pixels);
                assert_eq!(base.triangles, textured.triangles);
            }
        }
    }
    #[test]
    fn materials_keep_depth_order_and_complete_channel_values() {
        let back = fixture(0., [0., 0., 1.], false);
        let front = fixture(1., [0., 0., 1.], true);
        let r = [255, 0, 0, 255];
        let g = [0, 255, 0, 255];
        let textures = [
            texture::OpaqueTexture::new(1, 1, &r).unwrap(),
            texture::OpaqueTexture::new(1, 1, &g).unwrap(),
        ];
        let out =
            render_textured(&[(&back, 1), (&front, 1)], 64, 64, 0., &textures, &[0, 1]).unwrap();
        let ref_frame = render(&[(&front, 1)], 64, 64, 0.).unwrap();
        for (colored, gray) in out
            .rgb
            .as_chunks::<3>()
            .0
            .iter()
            .zip(ref_frame.rgb.as_chunks::<3>().0.iter())
        {
            if *gray == [24, 24, 24] {
                assert_eq!(colored, gray);
            } else {
                assert_eq!(*colored, [0, gray[0], 0]);
            }
        }
        let reversed =
            render_textured(&[(&front, 1), (&back, 1)], 64, 64, 0., &textures, &[1, 0]).unwrap();
        assert_eq!(out.rgb, reversed.rgb);
    }
    #[test]
    fn material_mapping_is_exact_and_not_an_implicit_fallback() {
        let mesh = fixture(0., [0., 0., 1.], false);
        let bytes = [255u8; 4];
        let textures = [texture::OpaqueTexture::new(1, 1, &bytes).unwrap()];
        assert!(render_textured(&[(&mesh, 1)], 64, 64, 0., &textures, &[]).is_err());
        assert!(render_textured(&[(&mesh, 1)], 64, 64, 0., &textures, &[1]).is_err());
        assert!(render_textured(&[(&mesh, 1)], 64, 64, 0., &[], &[0]).is_err());
        assert_eq!(textures[0].bytes().as_ptr(), bytes.as_ptr());
    }
}

#[cfg(test)]
mod textured_band_tests {
    use super::*;
    #[test]
    fn joined_uneven_bands_match_all_pixels_and_coverage() {
        let mesh=super::tests::fixture(0.,[0.,0.,1.],false);let rgba=[91,53,207,255];let masks=[None];
        for height in [16,17,63] { for yaw in [0.,0.37,1.2] {let tex=[texture::OpaqueTexture::new(1,1,&rgba).unwrap()];let full=render_textured_cutout_camera(&[(&mesh,1)],64,height,yaw.into(),&tex,&[0],&masks).unwrap();let mut rgb=Vec::new();let mut covered=0;for (start,end) in [(0,1),(1,height/2),(height/2,height)] {let part=render_textured_cutout_band(&[(&mesh,1)],64,height,RasterBand{camera:yaw.into(),first_row:start,past_last_row:end},&tex,&[0],&masks).unwrap();assert_eq!(part.frame.height,end-start);assert_eq!(part.frame.triangles,full.triangles);covered+=part.frame.covered_pixels;rgb.extend(part.frame.rgb);}assert_eq!(rgb,full.rgb);assert_eq!(covered,full.covered_pixels);}}
        let tex=[texture::OpaqueTexture::new(1,1,&rgba).unwrap()];for (start,end) in [(0,0),(17,16),(0,17)] {assert!(render_textured_cutout_band(&[(&mesh,1)],64,16,RasterBand{camera:0f32.into(),first_row:start,past_last_row:end},&tex,&[0],&masks).is_err());}
    }
}
