//! Read-only source-file probe. No game, Tray or database writes.
use apex_external_cas_draft_research::{appearance_owners::inspect_owners, Draft, NameField};
use sha2::{Digest, Sha256};
use std::io::Read;
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<_> = std::env::args().collect();
    if args.len() != 3 {
        return Err("Expected explicit SimData file and Sim ID".into());
    }
    let id: u64 = args[2].parse()?;
    let mut original = Vec::new();
    std::fs::File::open(&args[1])?
        .take(8 * 1024 * 1024 + 1)
        .read_to_end(&mut original)?;
    if original.len() > 8 * 1024 * 1024 {
        return Err("source bound".into());
    }
    let owners = inspect_owners(&original, id)?;
    let mut draft = Draft::new(id, original.clone())?;
    draft.edit_name(0, NameField::First, "Offline Preview")?;
    let edited = draft.bytes().to_vec();
    assert_ne!(edited, original);
    let checkpoint = draft.encode_checkpoint()?;
    let mut restored = Draft::decode_checkpoint(id, &checkpoint)?;
    assert_eq!(restored.bytes(), edited);
    restored.undo(1)?;
    assert_eq!(restored.bytes(), original);
    restored.redo(2)?;
    assert_eq!(restored.bytes(), edited);
    let export = restored.prepare_export(3, &original)?;
    assert_eq!(export.proposed_bytes(), edited);
    assert_eq!(std::fs::read(&args[1])?, original);
    println!("source_bytes={} source_sha256={:x} edited_sha256={:x} owners={} checkpoint_exact=true undo_original_exact=true redo_edited_exact=true source_unchanged=true game_applied=false tray_written=false",original.len(),Sha256::digest(&original),Sha256::digest(&edited),owners.owners.len());
    Ok(())
}
