//! Closed four-selection Caluxa preview catalog. Never reads arbitrary package paths.
//! Its receipt binds real CASP compatibility, resources, source catalog rows and
//! both meshes' checks across all 982 samples of the unchanged pinned library.
use super::accessory::{self, Accessory};
use std::path::{Path, PathBuf};

pub(super) struct Pin {
    pub id: &'static str,
    label: &'static str,
    package_sha256: &'static str,
    casp_sha256: &'static str,
    geom_tgi: &'static str,
    diffuse_tgi: &'static str,
    pub mesh_file: &'static str,
    pub mesh_bytes: usize,
    pub mesh_sha256: &'static str,
    pub vertices: u32,
    pub indices: u32,
    pub png_file: &'static str,
    pub png_bytes: usize,
    pub png_sha256: &'static str,
    pub rgba_sha256: &'static str,
}
include!("accessory_selection_pins.rs");
pub(super) const LONG_ID: &str = "034AEECB:80000000:C8B807499B50E181";
const MANIFEST: &[u8] = include_bytes!("accessory_selections_manifest.json");
const UNSUPPORTED: &str =
    "Only four prepared Caluxa selections; arbitrary CC and other swatches are unsupported.";
const MANIFEST_LIMIT: usize = 16384;

pub(super) struct Catalog {
    directory: PathBuf,
}
impl Catalog {
    pub fn open(path: &Path, pin: &str) -> Result<Self, &'static str> {
        if pin != MANIFEST_SHA256 {
            return Err("unknown prepared selection manifest pin");
        }
        let raw = accessory::read_regular(path, Some(MANIFEST.len()), MANIFEST_LIMIT)?;
        accessory::verified_bytes(&raw, MANIFEST.len(), MANIFEST_SHA256)?;
        if raw != MANIFEST {
            return Err("prepared selection manifest differs from closed source");
        }
        let directory = path
            .parent()
            .ok_or("selection manifest directory")?
            .to_path_buf();
        // All four are admitted together. No arbitrary parser, path or runtime CASP
        // compatibility inference is hidden behind the UI's prepared flag.
        for entry in &PINS {
            let mesh = accessory::read_regular(
                &directory.join(entry.mesh_file),
                Some(entry.mesh_bytes),
                entry.mesh_bytes,
            )?;
            accessory::verified_bytes(&mesh, entry.mesh_bytes, entry.mesh_sha256)?;
            let png = accessory::read_regular(
                &directory.join(entry.png_file),
                Some(entry.png_bytes),
                super::swatch_png::MAX_SOURCE_BYTES,
            )?;
            accessory::verified_bytes(&png, entry.png_bytes, entry.png_sha256)?;
        }
        Ok(Self { directory })
    }
    pub fn find(&self, id: &str) -> Result<&'static Pin, &'static str> {
        PINS.iter()
            .find(|pin| pin.id == id)
            .ok_or("unsupported accessory: not one of four prepared selections")
    }
    pub fn check(&self, id: &str, catalog: &str) -> Result<(), &'static str> {
        if catalog != MANIFEST_SHA256 {
            return Err("stale accessory catalog");
        }
        self.find(id)?;
        Ok(())
    }
    pub fn provenance(&self, pin: &Pin) -> String {
        format!(
            "{{\"id\":\"{}\",\"manifest_sha256\":\"{MANIFEST_SHA256}\",\"package_sha256\":\"{}\",\"casp_sha256\":\"{}\",\"mesh_sha256\":\"{}\",\"png_sha256\":\"{}\",\"rgba_sha256\":\"{}\",\"preview_only\":true}}",
            pin.id,
            pin.package_sha256,
            pin.casp_sha256,
            pin.mesh_sha256,
            pin.png_sha256,
            pin.rgba_sha256
        )
    }
    pub fn load(&self, pin: &Pin) -> Result<Accessory, &'static str> {
        Accessory::load_prepared(&self.directory, pin)
    }
}
pub(super) fn catalog_json(catalog: Option<&Catalog>, scene: &str) -> String {
    let enabled = catalog.is_some();
    let hash = if enabled {
        format!("\"{MANIFEST_SHA256}\"")
    } else {
        "null".into()
    };
    let rows = if enabled {
        PINS.iter().map(|p| format!("{{\"id\":\"{}\",\"label\":\"{}\",\"package_sha256\":\"{}\",\"casp_sha256\":\"{}\",\"geom_tgi\":\"{}\",\"diffuse_tgi\":\"{}\"}}", p.id,p.label,p.package_sha256,p.casp_sha256,p.geom_tgi,p.diffuse_tgi)).collect::<Vec<_>>().join(",")
    } else {
        String::new()
    };
    format!(
        "{{\"schema\":1,\"scene_sha256\":\"{scene}\",\"catalog_sha256\":{hash},\"default_id\":\"{}\",\"enabled\":{enabled},\"selections\":[{rows}],\"unsupported\":\"{UNSUPPORTED}\"}}",
        accessory::ID
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use sha2::{Digest, Sha256};
    #[test]
    fn closed_manifest_and_four_exact_sources() {
        assert!(MANIFEST.len() <= MANIFEST_LIMIT);
        assert_eq!(format!("{:x}", Sha256::digest(MANIFEST)), MANIFEST_SHA256);
        assert_eq!(PINS[0].id, accessory::ID);
        let catalog = Catalog {
            directory: PathBuf::from("unopened"),
        };
        for pin in &PINS {
            assert!(catalog.check(pin.id, MANIFEST_SHA256).is_ok());
            assert!(pin.mesh_bytes <= 32768);
            assert!(pin.png_bytes <= 32768);
        }
        for id in [
            "",
            "034AEECB:80000000:8CD60BB25CCE5880",
            "034AEECB:80000000:0000000000000000",
            "../file",
        ] {
            assert!(catalog.check(id, MANIFEST_SHA256).is_err());
        }
        assert!(catalog.check(accessory::ID, &"0".repeat(64)).is_err());
        assert!(catalog_json(None, &"a".repeat(64)).contains("\"selections\":[]"));
    }
}
