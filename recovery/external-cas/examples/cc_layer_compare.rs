//! Real selected-CC composition comparison, not a game/FPS benchmark.
use apex_external_cas_draft_research::preview::{
    color_shift::ColorShift,
    layers::{Layer, Mode, compose, compose_over},
    skin_detail,
};
use sha2::{Digest, Sha256};
use std::{fs, path::Path, time::Instant};
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let a: Vec<_> = std::env::args().collect();
    if a.len() != 2 {
        return Err("selected-dir".into());
    }
    let dir = Path::new(&a[1]);
    let tone = fs::read(dir.join("tone-base.2048.rgba"))?;
    let skin = fs::read(dir.join("miiko-rhea-skin.2048.rgba"))?;
    let skin = skin_detail::blend(2048, 4096, &tone, &skin, 0.35, 0.)?;
    let tattoo = fs::read(dir.join("myshunosun-caroline-tattoo.2048.rgba"))?;
    let eyes = fs::read(dir.join("eyes.2048.rgba"))?;
    let shoes = fs::read(dir.join("Jius-BowFlipFlops01.2048.rgba"))?;
    let dress = fs::read(dir.join("FatalRose-PastelGothDress.2048.rgba"))?;
    let lower_layers = vec![
        Layer {
            rgba: skin.view().bytes(),
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
            rgba: &shoes,
            mode: Mode::SourceOver,
        },
    ];
    let t = Instant::now();
    let lower = compose(2048, 4096, [0; 3], &lower_layers)?;
    println!(
        "{{\"kind\":\"setup\",\"lower_build_ms\":{},\"retained_lower_bytes\":{}}}",
        t.elapsed().as_secs_f64() * 1000.,
        lower.view().bytes().len()
    );
    for i in 0..24 {
        let bits = 0x4000000000000000u64 | (((i % 9) as i16 * 2048 - 8192) as u16 as u64) << 32;
        let t = Instant::now();
        let cloth = ColorShift::decode(bits)?.apply(&dress)?;
        let shift_ms = t.elapsed().as_secs_f64() * 1000.;
        let mut layers: Vec<_> = lower_layers
            .iter()
            .map(|l| Layer {
                rgba: l.rgba,
                mode: Mode::SourceOver,
            })
            .collect();
        layers.push(Layer {
            rgba: &cloth,
            mode: Mode::SourceOver,
        });
        let full = || {
            let t = Instant::now();
            let v = compose(2048, 4096, [0; 3], &layers).unwrap();
            (v, t.elapsed().as_secs_f64() * 1000.)
        };
        let partial = || {
            let t = Instant::now();
            let v = compose_over(lower.view(), &layers[4..]).unwrap();
            (v, t.elapsed().as_secs_f64() * 1000.)
        };
        let ((full, full_ms), (part, part_ms)) = if i % 2 == 0 {
            (full(), partial())
        } else {
            let p = partial();
            (full(), p)
        };
        assert_eq!(full.view().bytes(), part.view().bytes());
        println!(
            "{{\"kind\":\"pair\",\"index\":{i},\"full_first\":{},\"clothing_bits\":\"{bits:016x}\",\"shift_ms\":{shift_ms},\"full_ms\":{full_ms},\"partial_ms\":{part_ms},\"rgba_sha256\":\"{:x}\",\"exact\":true}}",
            i % 2 == 0,
            Sha256::digest(full.view().bytes())
        );
        layers.pop();
    }
    Ok(())
}
