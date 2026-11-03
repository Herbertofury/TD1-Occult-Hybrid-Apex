#[path = "cc_reference/renderer.rs"]
mod original;
// Selected public CC diagnostic, not complete Sim/CASP assembly or EA TONE parity.
use apex_external_cas_draft_research::preview::{
    layers::{Layer, Mode, compose},
    render_textured_cutout,
    texture::{AlphaMask, OpaqueTexture},
};
use sha2::{Digest, Sha256};
use std::{fs, path::Path};
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let a: Vec<_> = std::env::args().collect();
    if !(7..=8).contains(&a.len()) {
        return Err(
            "selected-dir head dress shoes hair output-dir [verified-CASP-Q14-clothing-hex]".into(),
        );
    }
    let dir = Path::new(&a[1]);
    let head = fs::read(&a[2])?;
    let dress = fs::read(&a[3])?;
    let shoes = fs::read(&a[4])?;
    let hair_mesh = fs::read(&a[5])?;
    let hair_rgba = fs::read(dir.join("AH00B-SugarHair-V1-Plain.rgba"))?;
    let mut hair_opaque = hair_rgba.clone();
    for p in hair_opaque.as_chunks_mut::<4>().0 {
        p[3] = 255;
    }
    let eyes = fs::read(dir.join("eyes.2048.rgba"))?;
    let tone_base = fs::read(dir.join("tone-base.2048.rgba"))?;
    OpaqueTexture::new(2048, 4096, &tone_base)?;
    let skin = fs::read(dir.join("miiko-rhea-skin.2048.rgba"))?;
    let tattoo = fs::read(dir.join("myshunosun-caroline-tattoo.2048.rgba"))?;
    let shoe = fs::read(dir.join("Jius-BowFlipFlops01.2048.rgba"))?;
    let cloth_raw = fs::read(dir.join("FatalRose-PastelGothDress.2048.rgba"))?;
    let shift_hex = a.get(7).map(String::as_str).unwrap_or("4000000000000000");
    let shift = apex_external_cas_draft_research::preview::color_shift::ColorShift::decode(
        u64::from_str_radix(shift_hex, 16)?,
    )?;
    let cloth = shift.apply(&cloth_raw)?;
    let skin_blend = apex_external_cas_draft_research::preview::skin_detail::blend(
        2048, 4096, &tone_base, &skin, 0.35, 0.,
    )?;
    // Base pixels come from the selected real CC TONE resource; composition remains diagnostic.
    let texture = compose(
        2048,
        4096,
        [0, 0, 0],
        &[
            Layer {
                rgba: skin_blend.view().bytes(),
                mode: Mode::SourceOver,
            },
            Layer {
                rgba: &tattoo,
                mode: Mode::SourceOver,
            },
            Layer {
                rgba: &eyes,
                mode: Mode::SourceOver,
            },
            Layer {
                rgba: &shoe,
                mode: Mode::SourceOver,
            },
            Layer {
                rgba: &cloth,
                mode: Mode::SourceOver,
            },
        ],
    )?;
    let tex = [
        texture.view(),
        OpaqueTexture::new(1024, 2048, &hair_opaque)?,
    ];
    let masks = [None, Some(AlphaMask::new(1024, 2048, &hair_rgba, 128)?)];
    fs::create_dir_all(&a[6])?;
    for yaw in [0f32, 0.6, 1.2, 2.4] {
        let control_inputs = [
            (head.as_slice(), 165),
            (dress.as_slice(), 165),
            (shoes.as_slice(), 165),
        ];
        let old = original::render_textured(&control_inputs, 768, 1024, yaw, &tex, &[0, 0, 0])?;
        let new = apex_external_cas_draft_research::preview::render_textured(
            &control_inputs,
            768,
            1024,
            yaw,
            &tex,
            &[0, 0, 0],
        )?;
        assert_eq!(old.rgb, new.rgb);
        assert_eq!(old.covered_pixels, new.covered_pixels);
        assert_eq!(old.triangles, new.triangles);
        let frame = render_textured_cutout(
            &[
                (&head, 165),
                (&dress, 165),
                (&shoes, 165),
                (&hair_mesh, 165),
            ],
            768,
            1024,
            yaw,
            &tex,
            &[0, 0, 0, 1],
            &masks,
        )?;
        let mut ppm = b"P6\n768 1024\n255\n".to_vec();
        ppm.extend(&frame.rgb);
        fs::write(Path::new(&a[6]).join(format!("female-{yaw}.ppm")), ppm)?;
        println!(
            "{{\"yaw\":{yaw},\"covered\":{},\"triangles\":{},\"rgb_sha256\":\"{:x}\",\"clothing_shift\":\"{shift_hex}\",\"base\":\"real CC TONE state0 texture; soft-light/overlay detail mode; native game parity unverified\",\"hair\":\"selected highest-layer no-hat region; alpha-test128 diagnostic, not game shader parity\"}}",
            frame.covered_pixels,
            frame.triangles,
            Sha256::digest(&frame.rgb)
        );
    }
    Ok(())
}
