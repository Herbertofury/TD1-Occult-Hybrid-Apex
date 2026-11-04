//! Explicit metadata-only index preparation; never invoked by a game query.
use anyhow::{Result, ensure};
use rusqlite::Connection;
use serde_json::{Value, json};
use std::path::Path;

pub fn prepare(c: &Connection) -> Result<()> {
    // A family is eligible for this fast path only when category and origin
    // are identical for every swatch. Never choose an unrelated representative.
    let mixed:i64=c.query_row("SELECT count(*) FROM (SELECT family_id FROM parts GROUP BY family_id HAVING count(DISTINCT coalesce(body_type,-1))>1 OR count(DISTINCT origin)>1)",[],|r|r.get(0))?;
    ensure!(
        mixed == 0,
        "Mixed category/origin swatch families need the general query path"
    );
    c.execute_batch("CREATE TABLE IF NOT EXISTS catalog_families(family_id TEXT PRIMARY KEY,part_id TEXT UNIQUE,body_type INTEGER,origin TEXT,title TEXT,creator TEXT,package_name TEXT,first_seen INTEGER,modified INTEGER);
        DELETE FROM catalog_families;
        INSERT INTO catalog_families SELECT family_id,part_id,body_type,origin,title,creator,json_extract(row_json,'$.package_name'),first_seen,modified FROM parts WHERE part_id IN (SELECT min(part_id) FROM parts GROUP BY family_id);
        CREATE INDEX IF NOT EXISTS catalog_family_name ON catalog_families(title COLLATE NOCASE,part_id);
        CREATE INDEX IF NOT EXISTS catalog_family_body_name ON catalog_families(body_type,title COLLATE NOCASE,part_id);
        CREATE INDEX IF NOT EXISTS catalog_family_origin_name ON catalog_families(origin,title COLLATE NOCASE,part_id);
        CREATE INDEX IF NOT EXISTS catalog_family_body_origin_name ON catalog_families(body_type,origin,title COLLATE NOCASE,part_id);
        CREATE INDEX IF NOT EXISTS catalog_family_body_origin_package ON catalog_families(body_type,origin,package_name COLLATE NOCASE,part_id);
        CREATE INDEX IF NOT EXISTS catalog_family_body_origin_creator ON catalog_families(body_type,origin,creator COLLATE NOCASE,title COLLATE NOCASE,part_id);
        ANALYZE catalog_families;")?;
    Ok(())
}

pub fn run(index: &Path, sha: &str, output: &Path) -> Result<Value> {
    use crate::{identity::file_sha256, providers};
    ensure!(
        !output.exists() && providers::hash(sha) && file_sha256(index)? == sha,
        "A fresh output and exact input catalogue digest are required"
    );
    let started = std::time::Instant::now();
    let before = index.metadata()?;
    let parent = output
        .parent()
        .ok_or_else(|| anyhow::anyhow!("Output needs a parent"))?;
    std::fs::create_dir_all(parent)?;
    let temp = tempfile::NamedTempFile::new_in(parent)?;
    std::fs::copy(index, temp.path())?;
    let after = index.metadata()?;
    ensure!(
        before.len() == after.len()
            && before.modified()? == after.modified()?
            && file_sha256(temp.path())? == sha,
        "Catalogue changed during copying"
    );
    let mut c = Connection::open(temp.path())?;
    ensure!(
        c.query_row::<i64, _, _>("PRAGMA user_version", [], |r| r.get(0))? == 7,
        "Enrich this catalogue before optimizing its native library pages"
    );
    let tx = c.transaction()?;
    prepare(&tx)?;
    tx.commit()?;
    let families: i64 = c.query_row("SELECT count(*) FROM catalog_families", [], |r| r.get(0))?;
    drop(c);
    temp.as_file().sync_all()?;
    temp.persist_noclobber(output).map_err(|e| e.error)?;
    Ok(
        json!({"ok":true,"index":output,"index_sha256":file_sha256(output)?,"families":families,"elapsed_ms":started.elapsed().as_millis(),"package_scan_performed":false,"source_modified":false,"service_installed":false}),
    )
}
