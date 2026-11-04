// SPDX-License-Identifier: GPL-3.0-or-later
// In-memory bridge to the retained renderer's rigid skinning diagnostic.
#[path = "../../src/mesh.rs"] mod mesh;
#[path = "../../src/skin.rs"] mod skin;
use std::io::{self, Read};
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut bytes = Vec::new();
    io::stdin().lock().take(32 * 1024 * 1024 + 165 * 48 + 5).read_to_end(&mut bytes)?;
    if bytes.len() < 4 { return Err("packet extent".into()); }
    let size = u32::from_le_bytes(bytes[..4].try_into()?) as usize;
    if size > 32 * 1024 * 1024 || bytes.len() != 4 + size + 165 * 48 { return Err("packet extent".into()); }
    let raw = &bytes[4..4 + size];
    let matrices: Vec<[f32; 12]> = bytes[4 + size..].chunks_exact(48).map(|chunk| {
        std::array::from_fn(|i| f32::from_le_bytes(chunk[i*4..i*4+4].try_into().unwrap()))
    }).collect();
    let view = mesh::SceneBudget::default().validate(raw, matrices.len())?;
    let output = skin::pose_rigid(raw, &matrices)?;
    let mut max_pos = 0f32; let mut max_normal = 0f32;
    for n in 0..view.vertex_count as usize {
        let at = 16 + n * mesh::STRIDE;
        for j in 0..6 {
            let p = at + j * 4;
            let a = f32::from_le_bytes(raw[p..p+4].try_into()?);
            let b = f32::from_le_bytes(output[p..p+4].try_into()?);
            if j < 3 { max_pos = max_pos.max((a-b).abs()); }
            else { max_normal = max_normal.max((a-b).abs()); }
        }
    }
    println!("accepted {} {} {}", view.vertex_count, max_pos, max_normal);
    Ok(())
}
