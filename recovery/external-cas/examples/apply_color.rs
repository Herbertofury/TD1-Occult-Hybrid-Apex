//! Fixture comparison runner. No file/game write path.
use apex_external_cas_draft_research::Draft;
use std::io::{self, Read};
fn main() {
    let args: Vec<String> = std::env::args().collect();
    assert_eq!(args.len(), 5);
    let mut input = String::new();
    io::stdin()
        .take(16 * 1024 * 1024 + 1)
        .read_to_string(&mut input)
        .unwrap();
    let hex = input.trim();
    assert!(hex.len() <= 16 * 1024 * 1024 && hex.len().is_multiple_of(2) && hex.is_ascii());
    let raw: Vec<u8> = (0..hex.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&hex[i..i + 2], 16).unwrap())
        .collect();
    let mut draft = Draft::new(args[1].parse().unwrap(), raw).unwrap();
    draft
        .edit_outfit_color(
            0,
            args[2].parse().unwrap(),
            args[3].parse().unwrap(),
            args[4].parse().unwrap(),
        )
        .unwrap();
    for byte in draft.bytes() {
        print!("{byte:02x}")
    }
    println!();
}
