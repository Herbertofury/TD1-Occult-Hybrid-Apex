//! Isolated lossless intake for already-derived swatches, not arbitrary CC images.
//!
//! Only IHDR / consecutive IDAT / IEND are accepted. All ancillary chunks
//! (including text, ICC, gamma, palette, and APNG) are rejected, not decompressed.
//! Extent inspection does no CRC or pixel decoding; png 0.18.1 owns those checks.
//! Its internal Limits are best-effort, NOT a hard process-memory cap. Separate
//! source, dimensions, and output limits apply before allocating the pixel buffer.
//! The container extent is exact; png's libpng-compatible tolerance of surplus
//! compressed bytes inside IDAT is not overridden by this container-only check.
use std::{fmt, io::Cursor};

pub const MAX_SOURCE_BYTES: usize = 8 * 1024 * 1024;
pub const MAX_SIDE: u32 = 4096;
pub const MAX_RGBA_BYTES: usize = 64 * 1024 * 1024;
const DECODER_BUDGET: usize = 8 * 1024 * 1024;

#[derive(Debug)]
pub struct IntakeError(String);
impl fmt::Display for IntakeError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.0)
    }
}
impl std::error::Error for IntakeError {}
impl From<png::DecodingError> for IntakeError {
    fn from(e: png::DecodingError) -> Self {
        Self(format!("PNG decode: {e}"))
    }
}
fn reject(message: &str) -> IntakeError {
    IntakeError(message.into())
}

#[derive(Debug, PartialEq, Eq)]
pub struct RgbaImage {
    pub width: u32,
    pub height: u32,
    /// Straight, unmodified RGBA8, including RGB under alpha zero.
    pub pixels: Vec<u8>,
}

fn output_len(width: u32, height: u32) -> Result<usize, IntakeError> {
    if width == 0 || height == 0 || width > MAX_SIDE || height > MAX_SIDE {
        return Err(reject("expected dimensions outside 1..=4096"));
    }
    let len = (width as usize)
        .checked_mul(height as usize)
        .and_then(|n| n.checked_mul(4))
        .ok_or_else(|| reject("output overflow"))?;
    if len > MAX_RGBA_BYTES {
        return Err(reject("output exceeds 64 MiB"));
    }
    Ok(len)
}

// No allocations, bounded by MAX_SOURCE_BYTES. Enforce one exact container and
// narrow chunk grammar before even constructing the decoder.
fn check_container(bytes: &[u8], width: u32, height: u32) -> Result<(), IntakeError> {
    if bytes.len() > MAX_SOURCE_BYTES {
        return Err(reject("source exceeds 8 MiB"));
    }
    if !bytes.starts_with(b"\x89PNG\r\n\x1a\n") {
        return Err(reject("PNG signature"));
    }
    let mut pos = 8usize;
    let mut header = false;
    let mut data = false;
    while pos < bytes.len() {
        let prefix = bytes
            .get(pos..pos + 8)
            .ok_or_else(|| reject("truncated chunk header"))?;
        let len = u32::from_be_bytes(prefix[..4].try_into().unwrap()) as usize;
        let end = pos
            .checked_add(12)
            .and_then(|n| n.checked_add(len))
            .filter(|&n| n <= bytes.len())
            .ok_or_else(|| reject("truncated chunk extent"))?;
        match &prefix[4..8] {
            b"IHDR" if !header && pos == 8 && len == 13 => {
                let h = &bytes[pos + 8..pos + 21];
                if u32::from_be_bytes(h[..4].try_into().unwrap()) != width
                    || u32::from_be_bytes(h[4..8].try_into().unwrap()) != height
                {
                    return Err(reject("PNG dimensions do not match expected dimensions"));
                }
                if h[8..] != [8, 6, 0, 0, 0] {
                    return Err(reject(
                        "requires noninterlaced RGBA8 with standard compression/filter",
                    ));
                }
                header = true;
            }
            b"IDAT" if header => {
                data = true;
            }
            b"IEND" if header && data && len == 0 && end == bytes.len() => return Ok(()),
            _ => {
                return Err(reject(
                    "unsupported chunk, invalid order, or trailing container bytes",
                ));
            }
        }
        pos = end;
    }
    Err(reject("missing complete IEND"))
}

/// Returns the entire verified frame or an error. No partially decoded buffer is
/// exposed and no gamma, color conversion, alpha premultiplication, or resize occurs.
pub fn decode(bytes: &[u8], width: u32, height: u32) -> Result<RgbaImage, IntakeError> {
    let len = output_len(width, height)?;
    check_container(bytes, width, height)?;
    let mut decoder = png::Decoder::new_with_limits(
        Cursor::new(bytes),
        png::Limits {
            bytes: DECODER_BUDGET,
        },
    );
    decoder.set_transformations(png::Transformations::IDENTITY);
    decoder.set_ignore_text_chunk(true);
    decoder.set_ignore_iccp_chunk(true);
    // Explicitly enables both CRC and Adler32 checks; do not rely on defaults.
    decoder.ignore_checksums(false);
    let mut reader = decoder.read_info()?;
    let info = reader.info();
    if info.width != width
        || info.height != height
        || info.interlaced
        || info.color_type != png::ColorType::Rgba
        || info.bit_depth != png::BitDepth::Eight
        || info.animation_control.is_some()
        || info.frame_control.is_some()
        || reader.output_buffer_size() != Some(len)
    {
        return Err(reject(
            "decoder metadata differs from required static RGBA8",
        ));
    }
    let mut pixels = Vec::new();
    pixels
        .try_reserve_exact(len)
        .map_err(|_| reject("output allocation failed"))?;
    pixels.resize(len, 0);
    let out = reader.next_frame(&mut pixels)?;
    if out.width != width
        || out.height != height
        || out.buffer_size() != len
        || out.color_type != png::ColorType::Rgba
        || out.bit_depth != png::BitDepth::Eight
    {
        return Err(reject("incomplete or unexpected output frame"));
    }
    reader.finish()?;
    Ok(RgbaImage {
        width,
        height,
        pixels,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    fn encode(color: png::ColorType, depth: png::BitDepth, data: &[u8]) -> Vec<u8> {
        let mut bytes = Vec::new();
        {
            let mut e = png::Encoder::new(&mut bytes, 2, 1);
            e.set_color(color);
            e.set_depth(depth);
            let mut w = e.write_header().unwrap();
            w.write_image_data(data).unwrap();
            w.finish().unwrap();
        }
        bytes
    }
    fn sample() -> Vec<u8> {
        encode(
            png::ColorType::Rgba,
            png::BitDepth::Eight,
            &[3, 97, 241, 0, 17, 29, 43, 127],
        )
    }
    #[test]
    fn preserves_all_channels_including_hidden_rgb() {
        let b = sample();
        let copy = b.clone();
        assert_eq!(
            decode(&b, 2, 1).unwrap().pixels,
            [3, 97, 241, 0, 17, 29, 43, 127]
        );
        assert_eq!(b, copy);
    }
    #[test]
    fn every_truncation_fails_without_output() {
        let b = sample();
        for end in 0..b.len() {
            assert!(decode(&b[..end], 2, 1).is_err(), "cut {end}");
        }
    }
    #[test]
    fn dimensions_and_source_bounds() {
        let b = sample();
        for (w, h) in [
            (0, 1),
            (1, 0),
            (4097, 1),
            (1, 4097),
            (u32::MAX, u32::MAX),
            (1, 1),
            (2, 2),
        ] {
            assert!(decode(&b, w, h).is_err());
        }
        assert_eq!(output_len(4096, 4096).unwrap(), MAX_RGBA_BYTES);
        assert!(decode(&vec![0; MAX_SOURCE_BYTES + 1], 2, 1).is_err());
    }
    #[test]
    fn crc_end_and_trailing_bytes_fail() {
        let b = sample();
        // Corrupt each existing chunk's CRC, including IEND after full pixels.
        let mut p = 8;
        while p < b.len() {
            let n = u32::from_be_bytes(b[p..p + 4].try_into().unwrap()) as usize;
            let mut bad = b.clone();
            bad[p + 8 + n] ^= 1;
            assert!(decode(&bad, 2, 1).is_err(), "CRC chunk at {p}");
            p += n + 12;
        }
        let mut bad = b.clone();
        bad.extend_from_slice(&[0]);
        assert!(decode(&bad, 2, 1).is_err());
        let mut bad = b.clone();
        bad.extend_from_slice(&b);
        assert!(decode(&bad, 2, 1).is_err());
        let mut bad = b.clone();
        let n = bad.len();
        bad[n - 8..n - 4].copy_from_slice(b"IDAT");
        assert!(decode(&bad, 2, 1).is_err());
    }
    #[test]
    fn other_pixel_modes_refused() {
        assert!(
            decode(
                &encode(png::ColorType::Rgb, png::BitDepth::Eight, &[0; 6]),
                2,
                1
            )
            .is_err()
        );
        assert!(
            decode(
                &encode(png::ColorType::Rgba, png::BitDepth::Sixteen, &[0; 16]),
                2,
                1
            )
            .is_err()
        );
        let mut b = sample();
        b[28] = 1;
        assert!(decode(&b, 2, 1).is_err()); // interlace in IHDR
    }
    // RETAINED UPSTREAM LIMITATION, not desired production acceptance:
    // png 0.18.1 ignores bytes after the zlib stream inside an otherwise valid
    // IDAT. This diagnostic checks exact container extent, not zlib extent.
    #[test]
    fn documents_upstream_surplus_compressed_bytes_acceptance() {
        let original = sample();
        let mut compressed = Vec::new();
        let mut pos = 8;
        while pos < original.len() {
            let len = u32::from_be_bytes(original[pos..pos + 4].try_into().unwrap()) as usize;
            if &original[pos + 4..pos + 8] == b"IDAT" {
                compressed.extend_from_slice(&original[pos + 8..pos + 8 + len]);
            }
            pos += len + 12;
        }
        assert!(!compressed.is_empty());
        compressed.extend_from_slice(b"surplus-after-zlib");
        let mut modified = Vec::new();
        {
            let mut encoder = png::Encoder::new(&mut modified, 2, 1);
            encoder.set_color(png::ColorType::Rgba);
            encoder.set_depth(png::BitDepth::Eight);
            let mut writer = encoder.write_header().unwrap();
            // Maintained png writer computes a valid CRC for the altered IDAT;
            // this is not a CRC bypass or a second hand-written CRC routine.
            writer.write_chunk(png::chunk::IDAT, &compressed).unwrap();
            writer.finish().unwrap();
        }
        assert_eq!(
            decode(&modified, 2, 1).unwrap(),
            decode(&original, 2, 1).unwrap()
        );
    }
    #[test]
    fn valid_apng_is_refused() {
        let mut bytes = Vec::new();
        {
            let mut encoder = png::Encoder::new(&mut bytes, 2, 1);
            encoder.set_color(png::ColorType::Rgba);
            encoder.set_depth(png::BitDepth::Eight);
            encoder.set_animated(1, 0).unwrap();
            let mut writer = encoder.write_header().unwrap();
            writer.write_image_data(&[0; 8]).unwrap();
            writer.finish().unwrap();
        }
        assert!(decode(&bytes, 2, 1).is_err());
    }
    #[test]
    fn rejects_all_metadata_and_animation_before_decoder() {
        for kind in [
            b"acTL", b"fcTL", b"fdAT", b"iCCP", b"tEXt", b"zTXt", b"iTXt", b"gAMA", b"PLTE",
            b"IHDR",
        ] {
            let mut b = sample();
            // CRC deliberately irrelevant: strict grammar rejects the kind first.
            let mut chunk = vec![0, 0, 0, 0];
            chunk.extend_from_slice(kind);
            chunk.extend_from_slice(&[0; 4]);
            b.splice(33..33, chunk);
            assert!(decode(&b, 2, 1).is_err(), "{kind:?}");
        }
    }
}
