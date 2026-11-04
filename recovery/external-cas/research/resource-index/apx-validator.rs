// SPDX-License-Identifier: GPL-3.0-or-later
// Bridge to the retained renderer's actual APXMESH reader. Data stays in memory.
#[path = "../../src/mesh.rs"] mod mesh;
use std::io::{self, Read};
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut bytes = Vec::new();
    io::stdin().lock().take(32 * 1024 * 1024 + 1).read_to_end(&mut bytes)?;
    let view = mesh::SceneBudget::default().validate(&bytes, 165)?;
    println!("accepted {} {}", view.vertex_count, view.index_count);
    Ok(())
}
