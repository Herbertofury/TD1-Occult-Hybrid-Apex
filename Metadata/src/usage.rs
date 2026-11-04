//! Compact, save-scoped equipped references. No meshes, thumbnails, package
//! bytes or Sim restore payloads live here. The game opens a pinned snapshot
//! read-only; explicit capture/import jobs publish a new snapshot atomically.
use crate::{identity::file_sha256, providers, text::words};
use anyhow::{Context, Result, ensure};
use rusqlite::{Connection, OptionalExtension, params, types::Value as Sql};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::{
    path::{Path, PathBuf},
    time::SystemTime,
};

#[derive(Default, Debug)]
pub struct Filter {
    pub sim: String,
    pub household: String,
    pub sim_id: String,
    pub household_id: String,
    pub form: String,
    pub outfit: String,
}
impl Filter {
    pub fn active(&self) -> bool {
        [
            &self.sim,
            &self.household,
            &self.sim_id,
            &self.household_id,
            &self.form,
            &self.outfit,
        ]
        .iter()
        .any(|s| !s.is_empty())
    }
    pub fn validate(&self) -> Result<()> {
        for text in [&self.sim, &self.household, &self.form] {
            ensure!(
                text.chars().count() <= 128 && !text.chars().any(char::is_control),
                "Sim, household or form filter exceeds its printable bound"
            );
            ensure!(
                text.is_empty() || !key(text).is_empty(),
                "A name filter needs letters or numbers"
            );
        }
        for id in [&self.sim_id, &self.household_id] {
            if !id.is_empty() {
                decimal(id)?;
            }
        }
        if !self.outfit.is_empty() {
            outfit(&self.outfit)?;
        }
        Ok(())
    }
}
pub fn key(s: &str) -> String {
    words(s).join(" ")
}
pub fn decimal(s: &str) -> Result<()> {
    ensure!(
        s.parse::<u64>().is_ok_and(|n| n > 0 && n.to_string() == s),
        "Use an exact positive decimal save, household, Sim or CAS item ID"
    );
    Ok(())
}
fn outfit(value: &str) -> Result<(u32, Option<u32>)> {
    let (category, ordinal) = value
        .split_once('/')
        .map_or((value, None), |(a, b)| (a, Some(b)));
    let category = match key(category).replace(' ', "").as_str() {
        "everyday" => 0,
        "formal" => 1,
        "athletic" => 2,
        "sleep" | "sleepwear" => 3,
        "party" => 4,
        "swim" | "swimwear" => 5,
        "hotweather" => 10,
        "coldweather" => 11,
        _ => category
            .parse::<u32>()
            .context("Use outfit:everyday/2 or a numeric outfit category")?,
    };
    ensure!(category <= 255, "Outfit category exceeds its bound");
    let ordinal = ordinal
        .map(|n| -> Result<u32> {
            let n = n
                .parse::<u32>()
                .context("Outfit number must be one-based, such as everyday/2")?;
            ensure!((1..=256).contains(&n), "Outfit number must be 1..256");
            Ok(n - 1)
        })
        .transpose()?;
    Ok((category, ordinal))
}

pub struct Pin {
    path: PathBuf,
    length: u64,
    modified: SystemTime,
    pub snapshot: Value,
}
impl Pin {
    pub fn check(&self) -> Result<()> {
        let meta = self.path.metadata()?;
        ensure!(
            meta.len() == self.length && meta.modified()? == self.modified,
            "Equipped references changed; refresh the pinned usage snapshot"
        );
        Ok(())
    }
}
fn readonly_uri(path: &Path) -> Result<String> {
    let path = path.canonicalize()?;
    let raw = path
        .to_str()
        .context("Usage snapshot path must be UTF-8")?
        .replace('\\', "/");
    let raw = raw.strip_prefix("//?/").unwrap_or(&raw);
    let mut encoded = String::new();
    for b in raw.as_bytes() {
        if b.is_ascii_alphanumeric() || b"/:.-_~".contains(b) {
            encoded.push(*b as char);
        } else {
            encoded.push_str(&format!("%{b:02X}"));
        }
    }
    Ok(format!("file:{encoded}?mode=ro&immutable=1"))
}
pub fn attach(
    c: &Connection,
    path: &Path,
    sha: &str,
    catalog_sha: &str,
    save: &str,
) -> Result<Pin> {
    decimal(save)?;
    ensure!(
        providers::hash(sha) && path.is_file(),
        "A pinned equipped-reference snapshot is required"
    );
    let before = path.metadata()?;
    ensure!(
        before.len() <= 512 * 1024 * 1024 && file_sha256(path)? == sha,
        "Equipped-reference snapshot differs from its pinned digest or bound"
    );
    c.execute("ATTACH DATABASE ? AS equipped", [readonly_uri(path)?])?;
    let version: i64 = c.query_row("PRAGMA equipped.user_version", [], |r| r.get(0))?;
    ensure!(version == 8201, "Unsupported equipped-reference schema");
    let snapshot: Value = serde_json::from_str(&c.query_row::<String, _, _>(
        "SELECT value FROM equipped.snapshot",
        [],
        |r| r.get(0),
    )?)?;
    ensure!(
        snapshot["catalog_sha256"] == catalog_sha
            && snapshot["save_guid"] == save
            && snapshot["complete"] == true,
        "Equipped references belong to a different catalogue/save or are incomplete"
    );
    let after = path.metadata()?;
    ensure!(
        before.len() == after.len() && before.modified()? == after.modified()?,
        "Usage snapshot changed while opening"
    );
    Ok(Pin {
        path: path.into(),
        length: after.len(),
        modified: after.modified()?,
        snapshot,
    })
}
/// No names are interpolated into SQL. IDs, names, forms and outfit numbers
/// apply to the same actor/use row, so separate Sims cannot satisfy half a query.
pub fn selection(f: &Filter) -> Result<(String, Vec<Sql>)> {
    f.validate()?;
    let mut clauses = Vec::new();
    let mut args = Vec::new();
    for (column, text) in [("a.sim_key", &f.sim), ("a.household_key", &f.household)] {
        if !text.is_empty() {
            clauses.push(format!("instr({column},?)>0"));
            args.push(Sql::Text(key(text)));
        }
    }
    for (column, id) in [("a.sim_id", &f.sim_id), ("a.household_id", &f.household_id)] {
        if !id.is_empty() {
            clauses.push(format!("{column}=?"));
            args.push(Sql::Text(id.clone()));
        }
    }
    if !f.form.is_empty() {
        clauses.push("(u.form_key=? OR u.owner_id=?)".into());
        args.extend([Sql::Text(key(&f.form)), Sql::Text(f.form.clone())]);
    }
    if !f.outfit.is_empty() {
        let (category, ordinal) = outfit(&f.outfit)?;
        clauses.push("u.category=?".into());
        args.push(Sql::Integer(category.into()));
        if let Some(n) = ordinal {
            clauses.push("u.ordinal=?".into());
            args.push(Sql::Integer(n.into()));
        }
    }
    Ok((
        format!(
            "SELECT u.part_id FROM equipped.uses u JOIN equipped.actors a ON a.sim_id=u.sim_id{}",
            if clauses.is_empty() {
                String::new()
            } else {
                format!(" WHERE {}", clauses.join(" AND "))
            }
        ),
        args,
    ))
}
pub fn used_by(c: &Connection, id: &str, filter: &Filter) -> Result<Value> {
    let (selection, mut args) = selection(filter)?;
    // Reuse the same predicates for provenance, not just for item membership.
    let suffix = selection
        .split_once(" WHERE ")
        .map_or(String::new(), |(_, v)| format!(" AND {v}"));
    let sql = format!(
        "SELECT a.household_id,a.household_name,a.sim_id,a.sim_name,u.owner_id,u.form_label,u.category,u.ordinal,u.outfit_id,u.body_type,u.layer,a.captured_at,a.source_epoch FROM equipped.uses u JOIN equipped.actors a ON a.sim_id=u.sim_id WHERE u.part_id=?{suffix} ORDER BY a.household_name,a.sim_name,u.owner_id,u.category,u.ordinal,u.body_type,u.layer LIMIT 9"
    );
    args.insert(0, Sql::Text(id.into()));
    let mut rows: Vec<Value> = c.prepare_cached(&sql)?.query_map(rusqlite::params_from_iter(args),|r|Ok(json!({
        "household_id":r.get::<_,String>(0)?,"household":r.get::<_,String>(1)?,"sim_id":r.get::<_,String>(2)?,
        "sim":r.get::<_,String>(3)?,"owner_id":r.get::<_,String>(4)?,"form":r.get::<_,String>(5)?,
        "outfit_category":r.get::<_,u32>(6)?,"outfit_number":r.get::<_,u32>(7)?+1,"outfit_id":r.get::<_,String>(8)?,
        "body_type":r.get::<_,u32>(9)?,"layer":r.get::<_,Option<u32>>(10)?,"captured_at":r.get::<_,i64>(11)?,"source_epoch":r.get::<_,String>(12)?})))?.collect::<rusqlite::Result<_>>()?;
    let complete = rows.len() <= 8;
    rows.truncate(8);
    Ok(json!({"rows":rows,"complete":complete,"limit":8}))
}

#[derive(Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Document {
    pub schema: u32,
    pub catalog_sha256: String,
    pub save_guid: String,
    pub captured_at: u64,
    pub source: String,
    pub source_epoch: String,
    pub complete: bool,
    pub households: Vec<Household>,
}
#[derive(Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Household {
    pub household_id: String,
    pub name: String,
    pub members: Vec<Actor>,
}
#[derive(Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Actor {
    pub sim_id: String,
    pub name: String,
    pub generation: u64,
    pub owners: Vec<Owner>,
}
#[derive(Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Owner {
    pub owner_id: String,
    pub form: String,
    pub outfits: Vec<Outfit>,
}
#[derive(Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Outfit {
    pub category: u32,
    pub ordinal: u32,
    pub outfit_id: String,
    pub parts: Vec<Part>,
}
#[derive(Deserialize, Serialize, Clone)]
#[serde(deny_unknown_fields)]
pub struct Part {
    pub instance: String,
    pub body_type: u32,
    pub layer: Option<u32>,
}

#[cfg(feature = "cli")]
pub fn import(
    index: &Path,
    sha: &str,
    document: &Path,
    output: &Path,
    previous: Option<(&Path, &str)>,
) -> Result<Value> {
    use std::{
        collections::{BTreeMap, BTreeSet},
        io::Write,
    };
    let started = std::time::Instant::now();
    ensure!(
        !output.exists(),
        "Retain the existing usage snapshot; publish a new output path"
    );
    ensure!(
        document.metadata()?.len() <= 64 * 1024 * 1024,
        "Usage capture exceeds its bound"
    );
    let raw = std::fs::read(document)?;
    let d: Document = serde_json::from_slice(&raw)?;
    ensure!(
        d.schema == 1 && d.complete && d.catalog_sha256 == sha && providers::hash(sha),
        "A complete capture for this exact catalogue is required"
    );
    decimal(&d.save_guid)?;
    ensure!(
        (1..=256).contains(&d.households.len())
            && d.captured_at > 0
            && d.captured_at <= i64::MAX as u64,
        "Usage capture household/date bound differs"
    );
    ensure!(
        matches!(
            d.source.as_str(),
            "native-cas-committed" | "live-committed" | "tray"
        ) && !d.source_epoch.is_empty()
            && d.source_epoch.len() <= 128,
        "An explicit source and bounded capture epoch are required"
    );
    let mut households = BTreeSet::new();
    let mut actors = BTreeSet::new();
    let mut refs = BTreeSet::new();
    let mut count = 0;
    let label =
        |s: &str| !s.is_empty() && s.chars().count() <= 128 && !s.chars().any(char::is_control);
    for h in &d.households {
        decimal(&h.household_id)?;
        ensure!(
            households.insert(&h.household_id)
                && label(&h.name)
                && (1..=32).contains(&h.members.len()),
            "Duplicate household, missing name or incomplete roster"
        );
        for a in &h.members {
            decimal(&a.sim_id)?;
            ensure!(
                actors.insert(&a.sim_id)
                    && label(&a.name)
                    && (1..=256).contains(&a.owners.len())
                    && a.generation <= i64::MAX as u64,
                "Duplicate Sim or incomplete form inventory"
            );
            let mut owners = BTreeSet::new();
            for o in &a.owners {
                ensure!(
                    label(&o.owner_id)
                        && label(&o.form)
                        && !key(&o.form).is_empty()
                        && owners.insert(&o.owner_id)
                        && o.outfits.len() <= 128,
                    "Duplicate or unbounded form owner"
                );
                let mut outfits = BTreeSet::new();
                for outfit in &o.outfits {
                    ensure!(
                        outfit
                            .outfit_id
                            .parse::<u64>()
                            .is_ok_and(|n| n.to_string() == outfit.outfit_id),
                        "Outfit identity must be canonical uint64, including an empty native outfit's zero default"
                    );
                    ensure!(
                        outfit.category <= 255
                            && outfit.ordinal <= 255
                            && outfits.insert((outfit.category, outfit.ordinal))
                            && outfit.parts.len() <= 4096,
                        "Duplicate or unbounded outfit"
                    );
                    for p in &outfit.parts {
                        decimal(&p.instance)?;
                        refs.insert((p.instance.parse::<u64>()?, p.body_type));
                        count += 1;
                        ensure!(count <= 1_000_000, "Usage capture reference bound exceeded");
                    }
                }
            }
        }
    }
    ensure!(
        file_sha256(index)? == sha,
        "Catalogue differs from the capture pin"
    );
    let source = providers::readonly(index)?;
    // A single metadata-only pass resolves all references. Source .packages
    // are never opened. This job exits; typing never repeats this traversal.
    let mut mapping: BTreeMap<(u64, u32), Vec<String>> = BTreeMap::new();
    let mut stmt = source
        .prepare("SELECT part_id,body_type,json_extract(row_json,'$.resource_tgi') FROM parts")?;
    for row in stmt.query_map([], |r| {
        Ok((
            r.get::<_, String>(0)?,
            r.get::<_, Option<u32>>(1)?,
            r.get::<_, String>(2)?,
        ))
    })? {
        let (id, body, tgi) = row?;
        if let (Some(body), Some(instance)) = (
            body,
            tgi.rsplit(':')
                .next()
                .and_then(|s| u64::from_str_radix(s, 16).ok()),
        ) {
            if refs.contains(&(instance, body)) {
                mapping.entry((instance, body)).or_default().push(id);
            }
        }
    }
    let parent = output.parent().context("Usage output needs a parent")?;
    std::fs::create_dir_all(parent)?;
    let mut temp = tempfile::NamedTempFile::new_in(parent)?;
    if let Some((previous, expected)) = previous {
        ensure!(
            previous.metadata()?.len() <= 512 * 1024 * 1024
                && providers::hash(expected)
                && file_sha256(previous)? == expected,
            "Previous usage snapshot differs"
        );
        let prior = providers::readonly(previous)?;
        ensure!(
            prior.query_row::<i64, _, _>("PRAGMA user_version", [], |r| r.get(0))? == 8201,
            "Unsupported previous usage schema"
        );
        let previous_meta: Value = serde_json::from_str(&prior.query_row::<String, _, _>(
            "SELECT value FROM snapshot",
            [],
            |r| r.get(0),
        )?)?;
        ensure!(
            previous_meta["catalog_sha256"] == sha
                && previous_meta["save_guid"] == d.save_guid
                && previous_meta["complete"] == true,
            "Previous usage belongs to another save/catalogue"
        );
        let bytes = std::fs::read(previous)?;
        ensure!(
            format!("{:x}", <sha2::Sha256 as sha2::Digest>::digest(&bytes)) == expected,
            "Previous usage changed while copying"
        );
        temp.write_all(&bytes)?;
    }
    let mut c = Connection::open(temp.path())?;
    c.execute_batch("PRAGMA user_version=8201;PRAGMA journal_mode=DELETE;CREATE TABLE IF NOT EXISTS snapshot(value TEXT);CREATE TABLE IF NOT EXISTS actors(sim_id TEXT PRIMARY KEY,sim_name TEXT,sim_key TEXT,household_id TEXT,household_name TEXT,household_key TEXT,generation INTEGER,captured_at INTEGER,source_epoch TEXT);CREATE INDEX IF NOT EXISTS actors_household ON actors(household_id);CREATE TABLE IF NOT EXISTS uses(part_id TEXT,sim_id TEXT,owner_id TEXT,form_label TEXT,form_key TEXT,category INTEGER,ordinal INTEGER,outfit_id TEXT,body_type INTEGER,layer INTEGER,UNIQUE(part_id,sim_id,owner_id,category,ordinal,body_type,layer));CREATE UNIQUE INDEX IF NOT EXISTS uses_exact ON uses(part_id,sim_id,owner_id,category,ordinal,body_type,coalesce(layer,-1));CREATE INDEX IF NOT EXISTS uses_part ON uses(part_id);CREATE INDEX IF NOT EXISTS uses_actor ON uses(sim_id,form_key,category,ordinal);")?;
    let tx = c.transaction()?;
    for h in &d.households {
        for a in &h.members {
            let old: Option<(i64, i64, String)> = tx
                .query_row(
                    "SELECT captured_at,generation,source_epoch FROM actors WHERE sim_id=?",
                    [&a.sim_id],
                    |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?)),
                )
                .optional()?;
            ensure!(
                old.is_none_or(|(date, generation, epoch)| d.captured_at > date as u64
                    && (epoch != d.source_epoch || a.generation >= generation as u64)),
                "Stale Sim capture cannot replace newer references, including after a household move"
            );
        }
        let newest: Option<i64> = tx.query_row(
            "SELECT max(captured_at) FROM actors WHERE household_id=?",
            [&h.household_id],
            |r| r.get(0),
        )?;
        ensure!(
            newest.is_none_or(|v| d.captured_at > v as u64),
            "Stale household capture cannot replace newer equipped references"
        );
    }
    // Preserve all freshness evidence until every included household passes.
    for h in &d.households {
        tx.execute(
            "DELETE FROM uses WHERE sim_id IN (SELECT sim_id FROM actors WHERE household_id=?)",
            [&h.household_id],
        )?;
        tx.execute("DELETE FROM actors WHERE household_id=?", [&h.household_id])?;
    }
    let mut missing = BTreeSet::new();
    let mut ambiguous = BTreeSet::new();
    let mut resolved = 0;
    for h in &d.households {
        for a in &h.members {
            // A moved Sim replaces its former household association atomically.
            tx.execute("DELETE FROM uses WHERE sim_id=?", [&a.sim_id])?;
            tx.execute(
                "INSERT OR REPLACE INTO actors VALUES(?,?,?,?,?,?,?,?,?)",
                params![
                    a.sim_id,
                    a.name,
                    key(&a.name),
                    h.household_id,
                    h.name,
                    key(&h.name),
                    a.generation as i64,
                    d.captured_at as i64,
                    d.source_epoch
                ],
            )?;
            for o in &a.owners {
                for outfit in &o.outfits {
                    for p in &outfit.parts {
                        let reference = (p.instance.parse::<u64>()?, p.body_type);
                        let ids = mapping.get(&reference);
                        if ids.is_none() {
                            missing.insert(reference);
                            continue;
                        }
                        let ids = ids.unwrap();
                        if ids.len() != 1 {
                            ambiguous.insert(reference);
                            continue;
                        }
                        resolved += tx.execute(
                            "INSERT OR IGNORE INTO uses VALUES(?,?,?,?,?,?,?,?,?,?)",
                            params![
                                ids[0],
                                a.sim_id,
                                o.owner_id,
                                o.form,
                                key(&o.form),
                                outfit.category,
                                outfit.ordinal,
                                outfit.outfit_id,
                                p.body_type,
                                p.layer
                            ],
                        )?;
                    }
                }
            }
        }
    }
    let actor_count: i64 = tx.query_row("SELECT count(*) FROM actors", [], |r| r.get(0))?;
    let use_count: i64 = tx.query_row("SELECT count(*) FROM uses", [], |r| r.get(0))?;
    let meta = json!({"schema":1,"catalog_sha256":sha,"save_guid":d.save_guid,"complete":true,
        "captured_at":d.captured_at,"source":d.source,"source_epoch":d.source_epoch,"capture_sha256":format!("{:x}", <sha2::Sha256 as sha2::Digest>::digest(&raw)),
        "sims":actor_count,"references":use_count,"unresolved_unique":missing.len(),"ambiguous_unique":ambiguous.len(),
        "resolution_counts_scope":"households in the last explicit capture; retained household references keep their own capture dates",
        "freshness":"captured references; refresh after appearance edits or household changes","assets_exported":false});
    tx.execute("DELETE FROM snapshot", [])?;
    tx.execute("INSERT INTO snapshot VALUES(?)", [meta.to_string()])?;
    tx.commit()?;
    drop(c);
    temp.as_file().sync_all()?;
    temp.persist_noclobber(output).map_err(|e| e.error)?;
    Ok(
        json!({"ok":true,"snapshot":meta,"index":output,"index_sha256":file_sha256(output)?,"bytes":output.metadata()?.len(),
        "captured_references":count,"resolved_references":resolved,"worker_elapsed_ms":started.elapsed().as_millis(),
        "package_scan_performed":false,"sim_written":false,"service_installed":false}),
    )
}
