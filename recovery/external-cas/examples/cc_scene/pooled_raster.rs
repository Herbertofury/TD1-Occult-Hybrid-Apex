//! Private retained-pool candidate. Inputs stay immutable; partial bands never publish.
use apex_external_cas_draft_research::preview::{self,Frame,Camera,texture::{OpaqueTexture,AlphaMask}};
use rayon::prelude::*;
pub struct Inputs<'a> {
    pub meshes:&'a [(&'a [u8],usize)], pub camera:Camera,
    pub textures:&'a [OpaqueTexture<'a>],pub materials:&'a [usize],pub masks:&'a [Option<AlphaMask<'a>>],
}
pub fn render(pool:&rayon::ThreadPool,scene:Inputs<'_>,width:usize,height:usize)->Result<Frame,&'static str> {
    let workers=pool.current_num_threads();
    if ![1,2,4].contains(&workers) || !(16..=1024).contains(&width) || !(16..=1024).contains(&height) { return Err("pooled raster bounds"); }
    let rows=height.div_ceil(workers);
    // Only owned band outputs mutate. Rayon install joins its scoped work before
    // propagating a panic; no partial output or game-owner operation can escape.
    let parts=std::panic::catch_unwind(std::panic::AssertUnwindSafe(||pool.install(|| {
        (0..workers).into_par_iter().map(|i| {
            let start=i*rows; let end=(start+rows).min(height);
            preview::render_textured_cutout_band(scene.meshes,width,height,preview::RasterBand{camera:scene.camera,first_row:start,past_last_row:end},scene.textures,scene.materials,scene.masks)
        }).collect::<Result<Vec<_>,_>>()
    }))).map_err(|_|"pooled raster worker panicked")??;
    let triangles=parts.first().ok_or("missing raster bands")?.frame.triangles;
    let mut frame=Frame{width,height,rgb:Vec::with_capacity(width*height*3),covered_pixels:0,triangles,stage_ms:None};let mut next=0;
    for part in parts {
        if part.rows.0!=next || part.rows.1>height || part.frame.width!=width || part.frame.height!=part.rows.1-part.rows.0 || part.frame.rgb.len()!=part.frame.height*width*3 || part.frame.triangles!=triangles { return Err("incomplete raster band join"); }
        frame.rgb.extend_from_slice(&part.frame.rgb);frame.covered_pixels=frame.covered_pixels.checked_add(part.frame.covered_pixels).ok_or("coverage overflow")?;next=part.rows.1;
    }
    if next!=height || frame.rgb.len()!=width*height*3 { return Err("incomplete raster frame"); }
    Ok(frame)
}
#[cfg(test)]
mod tests {
    use super::*;
    fn mesh()->Vec<u8> {let mut b=b"APXMESH1".to_vec();b.extend(3u32.to_le_bytes());b.extend(3u32.to_le_bytes());for p in [[-1f32,-1.,0.],[1.,-1.,0.],[0.,1.,0.]] {for f in p.into_iter().chain([0.,0.,1.,0.,0.]) {b.extend(f.to_le_bytes());}b.extend([0u8;8]);for f in [1f32,0.,0.,0.] {b.extend(f.to_le_bytes());}}for i in [0u32,1,2]{b.extend(i.to_le_bytes());}b}
    #[test]
    fn retained_workers_preserve_complete_rows_and_recover_after_refusal() {
        let raw=mesh();let rgba=[80,140,220,255];let textures=[OpaqueTexture::new(1,1,&rgba).unwrap()];let masks=[None];let inputs=[(raw.as_slice(),1)];
        for workers in [1,2,4] {let pool=rayon::ThreadPoolBuilder::new().num_threads(workers).stack_size(512*1024).build().unwrap();for height in [16,17,63] {let camera=Camera::from(0.37);let expected=preview::render_textured_cutout_camera(&inputs,64,height,camera,&textures,&[0],&masks).unwrap();let actual=render(&pool,Inputs{meshes:&inputs,camera,textures:&textures,materials:&[0],masks:&masks},64,height).unwrap();assert_eq!(actual.rgb,expected.rgb);assert_eq!(actual.covered_pixels,expected.covered_pixels);assert_eq!(actual.triangles,expected.triangles);}let bad=[(&raw[..5],1)];assert!(render(&pool,Inputs{meshes:&bad,camera:0f32.into(),textures:&textures,materials:&[0],masks:&masks},64,64).is_err());assert!(render(&pool,Inputs{meshes:&inputs,camera:0f32.into(),textures:&textures,materials:&[0],masks:&masks},64,64).is_ok());}
    }
}
