//! One pinned private Caluxa short-earring fixture, not an arbitrary CC loader.
//! The immutable material is separate from the dress source/cache transaction.
//! Diffuse + alpha-test with a closed sampled-CLIP gate; no native shader claim.
use super::swatch_png;
use apex_external_cas_draft_research::{
    mesh::{STRIDE, SceneBudget},
    preview::{
        FramingBounds,
        texture::{AlphaMask, OwnedOpaqueTexture},
    },
};
use sha2::{Digest, Sha256};
use std::{fs, io::Read, path::Path};

pub const ID: &str = "034AEECB:80000000:8CD98CB25CD1698D";
// Replaced only from the asset producer's verified receipt, never caller input.
pub const MANIFEST_SHA256: &str =
    "15f55824e03ba8633e620ba07880ebf640f5883df833ac74883353596fb6991a";
pub const POSE_MESH_SHA256: &str =
    "5df4ca6671550064acb5b0a6b51a9671e820f896133394990b54df1f9e1dd4e6";
pub const POSE_CATALOG_SHA256: &str =
    "817830a764ba36780330a7106a7e9f9ea55b9b1cf719c01fbfd9fd15d29a1327";
pub const POSE_LIBRARY_SHA256: &str =
    "90fdf2f87d48b73051c15083343685c7d917d38c1d1afc5a885dc6f10f44192d";
const MANIFEST_LIMIT: usize = 4096;
const MESH_BYTES: usize = 19248;
const WIDTH: u32 = 1024;
const HEIGHT: u32 = 2048;
const FIXED_FIELDS: &[(&str, &str)] = &[
    ("schema", "apex-cc-accessory-v1"),
    ("id", ID),
    (
        "package_sha256",
        "a93525ddeaa5ddb341948d76d648105865352f590622670537e7385b8e0aa8e7",
    ),
    (
        "casp_sha256",
        "3efb507ed8b10be9e639403ce4b76de0f11e4a31cccd19e61a7e8fc1a93bd0ee",
    ),
    ("geom_tgi", "015A1849:80915BCE:035A64F9282E1215"),
    (
        "geom_sha256",
        "82f87159ff5038e6da2ad506c9a1a140d34ef817476436bb35e3a3230f786cf2",
    ),
    ("diffuse_tgi", "3453CF95:80000000:FC8B34A612D90292"),
    (
        "diffuse_sha256",
        "55dfca44d905239ac5093d32bc6f721cf9481e63b363acc3a9e16a03dd77316b",
    ),
    (
        "rig_sha256",
        "616ae121718f2ad1676a008bea6dd8900e40eb741a98d099b6b17712266fe2dc",
    ),
    ("body_type", "10"),
    ("species", "1"),
    ("age_gender", "8312"),
    ("lod", "1"),
    ("geom_version", "14"),
    ("vertices", "292"),
    ("indices", "720"),
    ("positive_bone", "6"),
    ("width", "1024"),
    ("height", "2048"),
];
const SLIDER_FIELDS: &[(&str, &str)] = &[
    ("slider_hue", "-0.5,0.5,0.05000000074505806"),
    ("slider_saturation", "-0.5,0.5,0.05000000074505806"),
    ("slider_brightness", "-0.5,0.5,0.05000000074505806"),
    (
        "slider_opacity_min_increment",
        "0.20000000298023224,0.05000000074505806",
    ),
];

struct Manifest<'a> {
    mesh_file: &'a str,
    mesh_sha256: &'a str,
    png_file: &'a str,
    png_bytes: usize,
    png_sha256: &'a str,
    rgba_sha256: &'a str,
}
fn field<'a>(
    lines: &mut impl Iterator<Item = &'a str>,
    key: &str,
) -> Result<&'a str, &'static str> {
    let (actual, value) = lines
        .next()
        .and_then(|s| s.split_once('='))
        .ok_or("accessory manifest field missing")?;
    if actual != key || value.is_empty() {
        return Err("accessory manifest field order/value");
    }
    Ok(value)
}
fn basename(value: &str) -> Result<&str, &'static str> {
    if value.len() > 96
        || value.starts_with('.')
        || value.is_empty()
        || !value
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || b"-_.".contains(&b))
    {
        return Err("accessory path must be a bounded single basename");
    }
    Ok(value)
}
fn hash_text(value: &str) -> Result<&str, &'static str> {
    if value.len() != 64
        || !value
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
    {
        return Err("accessory SHA256 syntax");
    }
    Ok(value)
}
impl<'a> Manifest<'a> {
    fn parse(raw: &'a [u8]) -> Result<Self, &'static str> {
        if raw.len() > MANIFEST_LIMIT
            || !raw.is_ascii()
            || !raw.ends_with(b"\n")
            || raw.contains(&b'\r')
        {
            return Err("accessory manifest extent/encoding");
        }
        let mut lines = std::str::from_utf8(raw)
            .map_err(|_| "accessory manifest UTF8")?
            .lines();
        for (key, expected) in FIXED_FIELDS {
            if field(&mut lines, key)? != *expected {
                return Err("accessory source metadata mismatch");
            }
        }
        let mesh_file = basename(field(&mut lines, "mesh_file")?)?;
        if field(&mut lines, "mesh_bytes")? != "19248" {
            return Err("accessory mesh extent mismatch");
        }
        let mesh_sha256 = hash_text(field(&mut lines, "mesh_sha256")?)?;
        let png_file = basename(field(&mut lines, "png_file")?)?;
        if mesh_file == png_file {
            return Err("accessory sources must be distinct");
        }
        let png_bytes = field(&mut lines, "png_bytes")?
            .parse::<usize>()
            .map_err(|_| "accessory PNG extent syntax")?;
        if png_bytes == 0 || png_bytes > swatch_png::MAX_SOURCE_BYTES {
            return Err("accessory PNG byte bound");
        }
        let png_sha256 = hash_text(field(&mut lines, "png_sha256")?)?;
        let rgba_sha256 = hash_text(field(&mut lines, "rgba_sha256")?)?;
        for (key, expected) in SLIDER_FIELDS {
            if field(&mut lines, key)? != *expected {
                return Err("accessory CASP slider metadata mismatch");
            }
        }
        if lines.next().is_some() {
            return Err("accessory manifest trailing fields");
        }
        Ok(Self {
            mesh_file,
            mesh_sha256,
            png_file,
            png_bytes,
            png_sha256,
            rgba_sha256,
        })
    }
}
pub(super) fn verified_bytes(bytes: &[u8], length: usize, hash: &str) -> Result<(), &'static str> {
    if bytes.len() != length {
        return Err("accessory exact byte extent mismatch");
    }
    if format!("{:x}", Sha256::digest(bytes)) != hash {
        return Err("accessory SHA256 mismatch");
    }
    Ok(())
}
pub(super) fn read_regular(
    path: &Path,
    expected: Option<usize>,
    limit: usize,
) -> Result<Vec<u8>, &'static str> {
    if path.as_os_str().len() > 4096 {
        return Err("accessory input path bound");
    }
    if !fs::symlink_metadata(path)
        .map_err(|_| "accessory file unavailable")?
        .is_file()
    {
        return Err("accessory requires regular non-symlink files");
    }
    let file = fs::File::open(path).map_err(|_| "accessory file unavailable")?;
    let metadata = file
        .metadata()
        .map_err(|_| "accessory metadata unavailable")?;
    if !metadata.is_file()
        || metadata.len() > limit as u64
        || expected.is_some_and(|n| metadata.len() != n as u64)
    {
        return Err("accessory file extent mismatch");
    }
    let mut raw = Vec::new();
    raw.try_reserve_exact(metadata.len() as usize + 1)
        .map_err(|_| "accessory allocation failed")?;
    file.take(limit as u64 + 1)
        .read_to_end(&mut raw)
        .map_err(|_| "accessory file read failed")?;
    if raw.len() > limit || expected.is_some_and(|n| raw.len() != n) {
        return Err("accessory file extent mismatch");
    }
    Ok(raw)
}
fn validate_mesh(raw: &[u8]) -> Result<(), &'static str> {
    validate_mesh_counts(raw, 292, 720)
}
fn validate_mesh_counts(raw: &[u8], vertices: u32, indices: u32) -> Result<(), &'static str> {
    let mesh = SceneBudget::default().validate(raw, 165)?;
    if mesh.vertex_count != vertices || mesh.index_count != indices {
        return Err("accessory mesh counts mismatch");
    }
    for v in mesh.vertices.as_chunks::<STRIDE>().0 {
        for i in 0..4 {
            let weight = f32::from_le_bytes(v[40 + i * 4..44 + i * 4].try_into().unwrap());
            let joint = u16::from_le_bytes(v[32 + i * 2..34 + i * 2].try_into().unwrap());
            if weight > 0. && joint != 6 {
                return Err("accessory positive influence is not head bone");
            }
        }
    }
    Ok(())
}
fn decode_png(manifest: &Manifest<'_>, encoded: &[u8]) -> Result<Vec<u8>, &'static str> {
    verified_bytes(encoded, manifest.png_bytes, manifest.png_sha256)?;
    let image = swatch_png::decode(encoded, WIDTH, HEIGHT)
        .map_err(|_| "accessory bounded PNG decode failed")?;
    verified_bytes(
        &image.pixels,
        WIDTH as usize * HEIGHT as usize * 4,
        manifest.rgba_sha256,
    )?;
    if image
        .pixels
        .as_chunks::<4>()
        .0
        .iter()
        .any(|p| p[3] != 0 && p[3] != 255)
    {
        return Err("accessory requires verified binary alpha");
    }
    Ok(image.pixels)
}

pub(super) struct Accessory {
    pub(super) mesh: Vec<u8>,
    texture: OwnedOpaqueTexture,
    mask: Vec<u8>,
    diagnostics: String,
}
impl Accessory {
    pub(super) fn load(path: &Path, expected_sha256: &str) -> Result<Self, &'static str> {
        if hash_text(expected_sha256)? != MANIFEST_SHA256 {
            return Err("accessory manifest pin is not the pinned fixture");
        }
        let raw = read_regular(path, None, MANIFEST_LIMIT)?;
        // Reject an unknown manifest before trusting even a file name or length.
        verified_bytes(&raw, raw.len(), expected_sha256)?;
        let manifest = Manifest::parse(&raw)?;
        let directory = path.parent().unwrap_or(Path::new("."));
        let mesh = read_regular(
            &directory.join(manifest.mesh_file),
            Some(MESH_BYTES),
            MESH_BYTES,
        )?;
        verified_bytes(&mesh, MESH_BYTES, manifest.mesh_sha256)?;
        validate_mesh(&mesh)?;
        let encoded = read_regular(
            &directory.join(manifest.png_file),
            Some(manifest.png_bytes),
            swatch_png::MAX_SOURCE_BYTES,
        )?;
        let pixels = decode_png(&manifest, &encoded)?;
        drop(encoded);
        let mut opaque = pixels.clone();
        for p in opaque.as_chunks_mut::<4>().0 {
            p[3] = 255;
        }
        let diagnostics = format!(
            concat!(
                "{{\"enabled\":true,\"id\":\"{}\",\"manifest_sha256\":\"{}\",",
                "\"mesh_sha256\":\"{}\",\"png_sha256\":\"{}\",\"rgba_sha256\":\"{}\",",
                "\"package_sha256\":\"{}\",\"casp_sha256\":\"{}\",\"body_type\":10,\"species\":1,\"age_gender\":8312,",
                "\"lod\":1,\"lod_selection\":\"pinned upstream 0-to-1 fallback; no native parity claim\",",
                "\"positive_bone\":6,\"bone_name\":\"b__Head__\",\"width\":1024,\"height\":2048,",
                "\"material_owner\":\"independent immutable accessory; dress controls do not apply\",",
                "\"fidelity\":\"diffuse alpha-test128 diagnostic; not native SimSkin, metallic, RLES or full-game parity\",",
                "\"rest_framing\":\"fresh combined five-mesh rest envelope; margin0.0001\",\"synthetic_arm_qualified\":false,",
                "\"slider_ui_enabled\":false,\"casp_slider_metadata\":{{",
                "\"hue\":{{\"minimum\":-0.5,\"maximum\":0.5,\"increment\":0.05000000074505806}},",
                "\"saturation\":{{\"minimum\":-0.5,\"maximum\":0.5,\"increment\":0.05000000074505806}},",
                "\"brightness\":{{\"minimum\":-0.5,\"maximum\":0.5,\"increment\":0.05000000074505806}},",
                "\"opacity\":{{\"minimum\":0.20000000298023224,\"increment\":0.05000000074505806,\"maximum_explicit_in_casp\":false}}}}}}"
            ),
            ID,
            MANIFEST_SHA256,
            manifest.mesh_sha256,
            manifest.png_sha256,
            manifest.rgba_sha256,
            FIXED_FIELDS[2].1,
            FIXED_FIELDS[3].1
        );
        Ok(Self {
            mesh,
            texture: OwnedOpaqueTexture::new(WIDTH as usize, HEIGHT as usize, opaque)?,
            mask: pixels,
            diagnostics,
        })
    }
    pub(super) fn load_prepared(
        directory: &Path,
        pin: &super::accessory_selections::Pin,
    ) -> Result<Self, &'static str> {
        let mesh = read_regular(
            &directory.join(pin.mesh_file),
            Some(pin.mesh_bytes),
            pin.mesh_bytes,
        )?;
        verified_bytes(&mesh, pin.mesh_bytes, pin.mesh_sha256)?;
        validate_mesh_counts(&mesh, pin.vertices, pin.indices)?;
        let manifest = Manifest {
            mesh_file: pin.mesh_file,
            mesh_sha256: pin.mesh_sha256,
            png_file: pin.png_file,
            png_bytes: pin.png_bytes,
            png_sha256: pin.png_sha256,
            rgba_sha256: pin.rgba_sha256,
        };
        let encoded = read_regular(
            &directory.join(pin.png_file),
            Some(pin.png_bytes),
            swatch_png::MAX_SOURCE_BYTES,
        )?;
        let pixels = decode_png(&manifest, &encoded)?;
        drop(encoded);
        let mut opaque = pixels.clone();
        for p in opaque.as_chunks_mut::<4>().0 {
            p[3] = 255;
        }
        Ok(Self {
            mesh,
            texture: OwnedOpaqueTexture::new(WIDTH as usize, HEIGHT as usize, opaque)?,
            mask: pixels,
            diagnostics: format!(
                "{{\"enabled\":true,\"id\":\"{}\",\"selection_scope\":\"four separately prepared Caluxa selections; preview only\"}}",
                pin.id
            ),
        })
    }
    pub(super) fn texture(
        &self,
    ) -> apex_external_cas_draft_research::preview::texture::OpaqueTexture<'_> {
        self.texture.view()
    }
    pub(super) fn mask(&self) -> Result<AlphaMask<'_>, &'static str> {
        let [w, h] = self.texture.view().dimensions();
        AlphaMask::new(w, h, &self.mask, 128)
    }
    pub(super) fn diagnostics(&self, qualified: bool) -> String {
        // Internally generated pinned metadata; runtime qualification is never
        // inferred from a catalog's prose or a filename.
        format!(
            "{},\"pose_cache_qualified\":{qualified},\"playback_state\":\"{}\",\"qualified_pose_library_sha256\":\"{}\"}}",
            self.diagnostics
                .strip_suffix('}')
                .expect("internal diagnostic JSON"),
            if qualified {
                "pinned five-mesh sampled CLIP; selected cache envelope; no interpolation or game parity claim"
            } else {
                "static only; no qualified five-mesh library loaded"
            },
            POSE_LIBRARY_SHA256
        )
    }
    #[cfg(test)]
    pub(super) fn fixture(mesh: Vec<u8>) -> Self {
        Self {
            mesh,
            texture: OwnedOpaqueTexture::new(1, 1, vec![30, 220, 80, 255]).unwrap(),
            mask: vec![30, 220, 80, 255],
            diagnostics: "{\"enabled\":true}".into(),
        }
    }
}

pub(super) fn check_pose_library(
    mesh_digest: &[u8; 32],
    library_hash: &[u8; 32],
    catalog: &[u8],
) -> Result<(), &'static str> {
    if format!("{:x}", Sha256::digest(catalog)) != POSE_CATALOG_SHA256
        || hex(mesh_digest) != POSE_MESH_SHA256
    {
        return Err("accessory five-mesh/catalog qualification identity mismatch");
    }
    check_pose_library_identity(library_hash)
}
fn hex(bytes: &[u8; 32]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}
pub(super) fn check_pose_library_identity(library_hash: &[u8; 32]) -> Result<(), &'static str> {
    if hex(library_hash) != POSE_LIBRARY_SHA256 {
        return Err("accessory pose library is not the pinned qualified five-mesh library");
    }
    Ok(())
}
pub(super) fn check_input_pair(path: bool, pin: bool) -> Result<(), &'static str> {
    if path != pin {
        Err("accessory manifest path and SHA256 must be supplied together")
    } else {
        Ok(())
    }
}
pub(super) fn bind_identity(hash: &mut Sha256, accessory: Option<&Accessory>) {
    if accessory.is_some() {
        hash.update(
            b"optional-accessory-static-five-mesh-envelope-v1:margin0.0001:diffuse-cutout128",
        );
        hash.update(MANIFEST_SHA256.as_bytes());
    }
}
/// Derive a new envelope from all geometry; never reuse or relabel a four-mesh envelope.
pub(super) fn framing(
    meshes: &[Vec<u8>],
    accessory: &Accessory,
) -> Result<FramingBounds, &'static str> {
    geometry_framing(
        meshes
            .iter()
            .chain(std::iter::once(&accessory.mesh))
            .map(Vec::as_slice),
    )
}
pub(super) fn geometry_framing<'a>(
    meshes: impl IntoIterator<Item = &'a [u8]>,
) -> Result<FramingBounds, &'static str> {
    let mut lo = [f32::INFINITY; 3];
    let mut hi = [f32::NEG_INFINITY; 3];
    let mut budget = SceneBudget::default();
    for raw in meshes {
        let mesh = budget.validate(raw, 165)?;
        for i in 0..3 {
            lo[i] = lo[i].min(mesh.minimum[i]);
            hi[i] = hi[i].max(mesh.maximum[i]);
        }
    }
    FramingBounds::new(lo.map(|v| v - 0.0001), hi.map(|v| v + 0.0001))
}

#[cfg(test)]
mod tests {
    use super::*;
    fn manifest() -> String {
        let mut text = String::new();
        for (key, value) in FIXED_FIELDS {
            text.push_str(&format!("{key}={value}\n"));
        }
        text.push_str(&format!("mesh_file=caluxa-short-lod1.apxmesh\nmesh_bytes=19248\nmesh_sha256={}\npng_file=caluxa-short.png\npng_bytes=123\npng_sha256={}\nrgba_sha256={}\n", "1".repeat(64), "2".repeat(64), "3".repeat(64)));
        for (key, value) in SLIDER_FIELDS {
            text.push_str(&format!("{key}={value}\n"));
        }
        text
    }
    #[test]
    fn manifest_is_bounded_strict_and_source_bound() {
        let good = manifest();
        assert!(Manifest::parse(good.as_bytes()).is_ok());
        for bad in [
            good.replace("schema=apex-cc-accessory-v1", "schema=apex-cc-accessory-v2"),
            good.replace("body_type=10", "body_type=5"),
            good.replace("lod=1", "lod=0"),
            good.replace("mesh_bytes=19248", "mesh_bytes=19247"),
            good.replace("png_bytes=123", "png_bytes=8388609"),
            good.replace("png_bytes=123", "png_bytes=0"),
            good.replace("png_bytes=123", "png_bytes=-1"),
            good.replace("png_bytes=123", "png_bytes=999999999999999999999999"),
            good.replace("slider_hue=-0.5", "slider_hue=-1"),
            good.replace("\n", "\r\n"),
            format!("{good}extra=1\n"),
            format!("{good}{}", "x".repeat(MANIFEST_LIMIT)),
            good[..good.len() - 1].to_string(),
        ] {
            assert!(Manifest::parse(bad.as_bytes()).is_err(), "{bad}");
        }
        for end in [0, 1, good.len() / 2, good.len() - 2] {
            assert!(Manifest::parse(&good.as_bytes()[..end]).is_err());
        }
        let bad = good.replace(&"1".repeat(64), &"G".repeat(64));
        assert!(Manifest::parse(bad.as_bytes()).is_err());
    }
    #[test]
    fn manifest_paths_cannot_escape_or_alias_sources() {
        let good = manifest();
        for path in [
            "../caluxa.png",
            "/caluxa.png",
            ".",
            "..",
            "a/b.png",
            "a\\b.png",
            "C:evil.png",
            "a\0.png",
            ".hidden.png",
            "",
        ] {
            assert!(
                Manifest::parse(good.replace("caluxa-short.png", path).as_bytes()).is_err(),
                "{path}"
            );
        }
        assert!(basename(&"a".repeat(97)).is_err());
        assert!(
            Manifest::parse(
                good.replace("caluxa-short.png", "caluxa-short-lod1.apxmesh")
                    .as_bytes()
            )
            .is_err()
        );
    }
    #[test]
    fn exact_bytes_and_identities_refuse_corruption() {
        let raw = b"verified input";
        let hash = format!("{:x}", Sha256::digest(raw));
        assert!(verified_bytes(raw, raw.len(), &hash).is_ok());
        assert!(verified_bytes(raw, raw.len() - 1, &hash).is_err());
        assert!(verified_bytes(&raw[..raw.len() - 1], raw.len(), &hash).is_err());
        assert!(verified_bytes(b"modified input", raw.len(), &hash).is_err());
        assert!(verified_bytes(raw, raw.len(), &"0".repeat(64)).is_err());
        assert!(Accessory::load(Path::new("does-not-exist"), &"0".repeat(64)).is_err());
    }
    #[test]
    fn png_requires_both_encoded_and_complete_rgba_identities_and_binary_alpha() {
        fn encode(pixels: &[u8]) -> Vec<u8> {
            let mut encoded = Vec::new();
            {
                let mut encoder = png::Encoder::new(&mut encoded, WIDTH, HEIGHT);
                encoder.set_color(png::ColorType::Rgba);
                encoder.set_depth(png::BitDepth::Eight);
                let mut writer = encoder.write_header().unwrap();
                writer.write_image_data(pixels).unwrap();
                writer.finish().unwrap();
            }
            encoded
        }
        let mut pixels = vec![0; WIDTH as usize * HEIGHT as usize * 4];
        pixels[..8].copy_from_slice(&[3, 97, 241, 0, 10, 20, 30, 255]);
        let encoded = encode(&pixels);
        let source_hash = format!("{:x}", Sha256::digest(&encoded));
        let pixel_hash = format!("{:x}", Sha256::digest(&pixels));
        let text = manifest();
        let mut entry = Manifest::parse(text.as_bytes()).unwrap();
        entry.png_bytes = encoded.len();
        entry.png_sha256 = &source_hash;
        entry.rgba_sha256 = &pixel_hash;
        assert_eq!(decode_png(&entry, &encoded).unwrap(), pixels);
        entry.png_bytes -= 1;
        assert!(decode_png(&entry, &encoded).is_err());
        entry.png_bytes += 1;
        entry.png_sha256 = entry.rgba_sha256;
        assert!(decode_png(&entry, &encoded).is_err());
        entry.png_sha256 = &source_hash;
        entry.rgba_sha256 = &source_hash;
        assert!(decode_png(&entry, &encoded).is_err());
        pixels[3] = 127;
        let partial = encode(&pixels);
        let partial_hash = format!("{:x}", Sha256::digest(&partial));
        let partial_rgba_hash = format!("{:x}", Sha256::digest(&pixels));
        entry.png_bytes = partial.len();
        entry.png_sha256 = &partial_hash;
        entry.rgba_sha256 = &partial_rgba_hash;
        assert_eq!(
            decode_png(&entry, &partial).err(),
            Some("accessory requires verified binary alpha")
        );
    }
    #[test]
    fn optional_pair_and_closed_pose_qualification_fail_closed() {
        assert!(check_input_pair(false, false).is_ok());
        assert!(check_input_pair(true, true).is_ok());
        assert!(check_input_pair(false, true).is_err());
        assert!(check_input_pair(true, false).is_err());
        let pinned = std::array::from_fn(|i| {
            u8::from_str_radix(&POSE_LIBRARY_SHA256[i * 2..i * 2 + 2], 16).unwrap()
        });
        assert!(check_pose_library_identity(&pinned).is_ok());
        for index in 0..32 {
            let mut changed = pinned;
            changed[index] ^= 1;
            assert!(check_pose_library_identity(&changed).is_err());
        }
        assert!(check_pose_library(&[0; 32], &pinned, b"catalog claims qualified").is_err());
    }
    #[test]
    fn optional_off_does_not_change_identity_bytes() {
        let mut old = Sha256::new();
        old.update(b"existing scene transcript");
        let mut absent = old.clone();
        bind_identity(&mut absent, None);
        assert_eq!(old.clone().finalize(), absent.finalize());
        bind_identity(&mut old, Some(&Accessory::fixture(vec![])));
        assert_ne!(old.finalize(), Sha256::digest(b"existing scene transcript"));
    }
    struct TempDir(std::path::PathBuf);
    impl TempDir {
        fn new() -> Self {
            static NEXT: std::sync::atomic::AtomicUsize = std::sync::atomic::AtomicUsize::new(0);
            let path = std::env::temp_dir().join(format!(
                "apex-accessory-{}-{}",
                std::process::id(),
                NEXT.fetch_add(1, std::sync::atomic::Ordering::Relaxed)
            ));
            fs::create_dir(&path).unwrap();
            Self(path)
        }
    }
    impl Drop for TempDir {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }
    #[test]
    fn reads_only_regular_bounded_exact_files() {
        let temp = TempDir::new();
        let path = temp.0.join("input");
        fs::write(&path, b"abcd").unwrap();
        assert_eq!(read_regular(&path, Some(4), 4).unwrap(), b"abcd");
        assert!(read_regular(&path, Some(3), 4).is_err());
        assert!(read_regular(&path, Some(5), 8).is_err());
        assert!(read_regular(&path, None, 3).is_err());
        assert!(read_regular(&temp.0, None, 4).is_err());
        #[cfg(unix)]
        {
            let alias = temp.0.join("alias");
            std::os::unix::fs::symlink(&path, &alias).unwrap();
            assert!(read_regular(&alias, Some(4), 4).is_err());
        }
    }
    #[test]
    fn accessory_mesh_validation_requires_fixture_counts_and_head_weights() {
        let mut mesh = b"APXMESH1".to_vec();
        mesh.extend(292u32.to_le_bytes());
        mesh.extend(720u32.to_le_bytes());
        for _ in 0..292 {
            for f in [0f32, 0., 0., 0., 0., 1., 0., 0.] {
                mesh.extend(f.to_le_bytes());
            }
            mesh.extend(6u16.to_le_bytes());
            mesh.extend([0; 6]);
            for w in [1f32, 0., 0., 0.] {
                mesh.extend(w.to_le_bytes());
            }
        }
        for _ in 0..240 {
            for i in [0u32, 1, 2] {
                mesh.extend(i.to_le_bytes());
            }
        }
        assert_eq!(mesh.len(), MESH_BYTES);
        assert!(validate_mesh(&mesh).is_ok());
        for end in [0, 15, MESH_BYTES - 1] {
            assert!(validate_mesh(&mesh[..end]).is_err());
        }
        mesh[48..50].copy_from_slice(&5u16.to_le_bytes());
        assert!(validate_mesh(&mesh).is_err());
        mesh[48..50].copy_from_slice(&6u16.to_le_bytes());
        mesh[56..60].copy_from_slice(&f32::NAN.to_le_bytes());
        assert!(validate_mesh(&mesh).is_err());
    }
}
