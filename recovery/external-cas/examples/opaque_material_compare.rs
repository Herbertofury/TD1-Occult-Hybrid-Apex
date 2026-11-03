use apex_external_cas_draft_research::preview::{render, render_textured, texture::OpaqueTexture};
use sha2::{Digest, Sha256};
use std::{fs, time::Instant};
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let a: Vec<_> = std::env::args().collect();
    if a.len() != 5 {
        return Err("body.apxmesh head.apxmesh opaque1024x2048.rgba output-directory".into());
    }
    let body = fs::read(&a[1])?;
    let head = fs::read(&a[2])?;
    let pixels = fs::read(&a[3])?;
    let start = Instant::now();
    let texture = OpaqueTexture::new(1024, 2048, &pixels)?;
    let validation = start.elapsed().as_nanos();
    let textures = [texture];
    let white = [255; 4];
    let whites = [OpaqueTexture::new(1, 1, &white)?];
    fs::create_dir_all(&a[4])?;
    for yaw in [0f32, 0.6, 1.2, 2.4] {
        let inputs = [(body.as_slice(), 165), (head.as_slice(), 165)];
        let start = Instant::now();
        let base = render(&inputs, 512, 512, yaw)?;
        let base_ns = start.elapsed().as_nanos();
        let start = Instant::now();
        let same = render_textured(&inputs, 512, 512, yaw, &whites, &[0, 0])?;
        let white_ns = start.elapsed().as_nanos();
        assert_eq!(base.rgb, same.rgb);
        let start = Instant::now();
        let colored = render_textured(&inputs, 512, 512, yaw, &textures, &[0, 0])?;
        let colored_ns = start.elapsed().as_nanos();
        assert_eq!(colored.covered_pixels, base.covered_pixels);
        let name = format!("{}/body-{yaw:.1}.ppm", a[4]);
        let mut ppm = b"P6\n512 512\n255\n".to_vec();
        ppm.extend(&colored.rgb);
        fs::write(name, ppm)?;
        println!(
            "{{\"yaw\":{yaw},\"texture_validation_ns\":{validation},\"baseline_ns\":{base_ns},\"white_control_ns\":{white_ns},\"colored_ns\":{colored_ns},\"white_pixels_exact\":true,\"covered\":{},\"triangles\":{},\"colored_sha256\":\"{:x}\"}}",
            colored.covered_pixels,
            colored.triangles,
            Sha256::digest(&colored.rgb)
        );
    }
    let out = render_textured(&[(head.as_slice(), 165)], 512, 512, 0., &textures, &[0])?;
    let mut ppm = b"P6\n512 512\n255\n".to_vec();
    ppm.extend(&out.rgb);
    fs::write(format!("{}/head.ppm", a[4]), ppm)?;
    Ok(())
}
