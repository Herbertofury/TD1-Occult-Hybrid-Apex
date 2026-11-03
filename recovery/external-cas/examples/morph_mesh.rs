use apex_external_cas_draft_research::morph_preview::MorphPlan;
use std::{fs, io::Write};
fn main() {
    let args: Vec<_> = std::env::args().collect();
    assert_eq!(
        args.len(),
        5,
        "source.apxmesh deltas.f32 weight output.apxmesh"
    );
    assert!(fs::metadata(&args[1]).unwrap().len() <= 32 * 1024 * 1024);
    assert!(fs::metadata(&args[2]).unwrap().len() <= 24 * 1_000_000);
    let raw = fs::read(&args[1]).unwrap();
    let d = fs::read(&args[2]).unwrap();
    assert!(d.len().is_multiple_of(24));
    let deltas = d
        .as_chunks::<24>()
        .0
        .iter()
        .map(|x| {
            std::array::from_fn(|i| f32::from_le_bytes(x[i * 4..i * 4 + 4].try_into().unwrap()))
        })
        .collect();
    let plan = MorphPlan::new(&raw, deltas, 165).unwrap();
    let out = plan.apply(&raw, args[3].parse().unwrap()).unwrap();
    let mut f = fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&args[4])
        .unwrap();
    f.write_all(&out).unwrap();
    println!("bytes={} game_applied=false", out.len());
}
