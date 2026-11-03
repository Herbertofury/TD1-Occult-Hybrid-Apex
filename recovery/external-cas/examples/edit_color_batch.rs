//! Offline differential-test driver; input is not a live-game command protocol.
use apex_external_cas_draft_research::preview::color_shift::{Channel, EditRange, replace_lanes};
use std::io::{self, BufRead};
fn main() {
    for line in io::stdin().lock().lines() {
        let line = line.expect("stdin");
        let args: Vec<_> = line.split_whitespace().collect();
        assert_eq!(args.len(), 6);
        let channel = match args[1] {
            "0" => Channel::Brightness,
            "1" => Channel::Saturation,
            "2" => Channel::Hue,
            "3" => Channel::Opacity,
            _ => panic!("channel"),
        };
        let result = replace_lanes(
            u64::from_str_radix(args[0], 16).unwrap(),
            &[(
                channel,
                args[2].parse().unwrap(),
                EditRange {
                    enabled: args[3] == "1",
                    min: args[4].parse().unwrap(),
                    max: args[5].parse().unwrap(),
                },
            )],
        );
        match result {
            Ok(bits) => println!("{bits:016x}"),
            Err(_) => println!("REFUSED"),
        }
    }
}
