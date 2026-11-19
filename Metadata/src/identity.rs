use anyhow::{Context, Result, bail, ensure};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    fs::File,
    io::{Read, Seek, SeekFrom},
    path::Path,
};

pub const MAX_PACKAGE_BYTES: u64 = 16 * 1024 * 1024 * 1024;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Identity {
    pub sha256: String,
    pub blake3: String,
    pub curseforge_fingerprint: u32,
    pub bytes: u64,
}

// CurseForge's published MurmurHash2 fingerprint uses seed 1 and removes
// precisely TAB/LF/CR/space. Other control bytes must remain significant.
pub fn fingerprint(bytes: &[u8]) -> u32 {
    let whitespace = |b: u8| matches!(b, 9 | 10 | 13 | 32);
    let length = bytes.iter().filter(|&&b| !whitespace(b)).count() as u32;
    let mut h = 1 ^ length;
    let mut k = 0_u32;
    let mut shift = 0;
    for &b in bytes {
        if whitespace(b) {
            continue;
        }
        k |= u32::from(b) << shift;
        shift += 8;
        if shift == 32 {
            k = k.wrapping_mul(0x5bd1e995);
            k ^= k >> 24;
            k = k.wrapping_mul(0x5bd1e995);
            h = h.wrapping_mul(0x5bd1e995) ^ k;
            k = 0;
            shift = 0;
        }
    }
    if shift != 0 {
        h = (h ^ k).wrapping_mul(0x5bd1e995);
    }
    h ^= h >> 13;
    h = h.wrapping_mul(0x5bd1e995);
    h ^ (h >> 15)
}

pub fn file_identity(path: &Path) -> Result<Identity> {
    let link = path
        .symlink_metadata()
        .context("Cannot inspect metadata source")?;
    ensure!(
        link.is_file() && !link.file_type().is_symlink(),
        "A regular package is required"
    );
    ensure!(
        link.len() <= MAX_PACKAGE_BYTES,
        "Package exceeds the bounded fingerprint size"
    );
    let mut file = File::open(path).context("Cannot open package read-only")?;
    let before = file.metadata()?;
    // Fixed memory even for multi-gigabyte merged CC/EA packages. Murmur2
    // requires its normalized length before mixing; two sequential reads avoid
    // retaining the entire package (or making a temporary extracted copy).
    let mut bytes = [0_u8; 256 * 1024];
    let mut sha = Sha256::new();
    let mut blake = blake3::Hasher::new();
    let mut length = 0_u64;
    let mut normalized = 0_u64;
    loop {
        let n = file.read(&mut bytes)?;
        if n == 0 {
            break;
        }
        length += n as u64;
        ensure!(
            length <= MAX_PACKAGE_BYTES,
            "Package grew beyond its size bound"
        );
        sha.update(&bytes[..n]);
        blake.update(&bytes[..n]);
        normalized += bytes[..n]
            .iter()
            .filter(|&&b| !matches!(b, 9 | 10 | 13 | 32))
            .count() as u64;
    }
    ensure!(length == before.len(), "Package changed while hashing");
    file.seek(SeekFrom::Start(0))?;
    let mut h = 1 ^ (normalized as u32);
    let mut k = 0_u32;
    let mut shift = 0;
    let mut second = 0_u64;
    let mut second_sha = Sha256::new();
    loop {
        let n = file.read(&mut bytes)?;
        if n == 0 {
            break;
        }
        second += n as u64;
        ensure!(
            second <= MAX_PACKAGE_BYTES,
            "Package grew beyond its size bound"
        );
        second_sha.update(&bytes[..n]);
        for &b in &bytes[..n] {
            if matches!(b, 9 | 10 | 13 | 32) {
                continue;
            }
            k |= u32::from(b) << shift;
            shift += 8;
            if shift == 32 {
                k = k.wrapping_mul(0x5bd1e995);
                k ^= k >> 24;
                k = k.wrapping_mul(0x5bd1e995);
                h = h.wrapping_mul(0x5bd1e995) ^ k;
                k = 0;
                shift = 0;
            }
        }
    }
    if shift != 0 {
        h = (h ^ k).wrapping_mul(0x5bd1e995);
    }
    h ^= h >> 13;
    h = h.wrapping_mul(0x5bd1e995);
    h ^= h >> 15;
    let sha256 = format!("{:x}", sha.finalize());
    ensure!(
        second == length && format!("{:x}", second_sha.finalize()) == sha256,
        "Package bytes changed between fingerprint passes"
    );
    let after = file.metadata()?;
    let current = path.metadata()?;
    if before.len() != after.len()
        || before.modified()? != after.modified()?
        || after.len() != current.len()
        || after.modified()? != current.modified()?
    {
        bail!("Package changed while fingerprinting");
    }
    Ok(Identity {
        sha256,
        blake3: blake.finalize().to_hex().to_string(),
        curseforge_fingerprint: h,
        bytes: length,
    })
}

pub fn file_sha256(path: &Path) -> Result<String> {
    let mut file = File::open(path)?;
    let mut hash = Sha256::new();
    let mut bytes = [0_u8; 256 * 1024];
    loop {
        let count = file.read(&mut bytes)?;
        if count == 0 {
            break;
        }
        hash.update(&bytes[..count]);
    }
    Ok(format!("{:x}", hash.finalize()))
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn only_the_four_curseforge_whitespace_bytes_are_ignored() {
        assert_eq!(fingerprint(b"abc"), fingerprint(b" a\tb\r\nc "));
        assert_ne!(fingerprint(b"abc"), fingerprint(b"a\x0bb\x0cc"));
        assert_eq!(fingerprint(b""), 0x5bd15e36);
    }
}
