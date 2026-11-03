use apex_external_cas_draft_research::preview::skin_detail::blend;
use std::fs;
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let a: Vec<_> = std::env::args().collect();
    if a.len() != 7 {
        return Err("width height tone.rgba detail.rgba opacity output.rgba".into());
    }
    for p in [&a[3], &a[4]] {
        if fs::metadata(p)?.len() > 64 * 1024 * 1024 {
            return Err("input extent".into());
        }
    }
    let tone = fs::read(&a[3])?;
    let detail = fs::read(&a[4])?;
    let result = blend(
        a[1].parse()?,
        a[2].parse()?,
        &tone,
        &detail,
        a[5].parse()?,
        0.,
    )?;
    fs::write(&a[6], result.view().bytes())?;
    Ok(())
}
