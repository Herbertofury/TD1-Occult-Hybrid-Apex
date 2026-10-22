pub use crate::text::{aliases, deletions, words};
use crate::{
    identity::{Identity, file_identity, file_sha256},
    providers::{self, Creator, Record},
};
use anyhow::{Context, Result, ensure};
use rayon::prelude::*;
use rusqlite::{Connection, params};
use serde_json::{Value, json};
use std::{
    collections::{BTreeMap, BTreeSet},
    path::{Path, PathBuf},
    time::Instant,
};
fn key(value: &str) -> String {
    value
        .chars()
        .filter(|c| c.is_alphanumeric())
        .flat_map(char::to_lowercase)
        .collect()
}

#[derive(Clone, Debug)]
pub struct Evidence {
    pub creator: String,
    pub title: String,
    pub url: String,
    pub kind: String,
    pub verified: bool,
}

// Pre-index provider digests and creator prefixes once. Resolving a CASP must
// not compare it with every author or every provider record in the database.
struct Resolver {
    strong: BTreeMap<String, Vec<Record>>,
    weak: BTreeMap<u32, Vec<Record>>,
    files: BTreeMap<String, Vec<Record>>,
    prefixes: BTreeMap<String, BTreeMap<String, String>>,
}
impl Resolver {
    fn new(records: &[Record], creators: &[Creator]) -> Self {
        let mut result = Self {
            strong: BTreeMap::new(),
            weak: BTreeMap::new(),
            files: BTreeMap::new(),
            prefixes: BTreeMap::new(),
        };
        for row in records {
            if !row.content_hash.is_empty() {
                result
                    .strong
                    .entry(row.content_hash.to_lowercase())
                    .or_default()
                    .push(row.clone());
            }
            if let Some(fp) = row.fingerprint {
                result.weak.entry(fp).or_default().push(row.clone());
            }
            if row.provider == "wcif" && row.fingerprint.is_none() && !row.filename.is_empty() {
                result
                    .files
                    .entry(row.filename.to_lowercase())
                    .or_default()
                    .push(row.clone());
            }
        }
        for creator in creators {
            for name in std::iter::once(&creator.name).chain(creator.aliases.iter()) {
                let k = key(name);
                if k.chars().count() >= 3 {
                    result
                        .prefixes
                        .entry(k)
                        .or_default()
                        .insert(creator.name.clone(), creator.source_url.clone());
                }
            }
        }
        result
    }
    fn resolve(&self, identity: &Identity, filename: &str, code: &str) -> Evidence {
        let mut rows = self
            .strong
            .get(&identity.sha256)
            .cloned()
            .unwrap_or_default();
        rows.extend(
            self.weak
                .get(&identity.curseforge_fingerprint)
                .cloned()
                .unwrap_or_default(),
        );
        rows.extend(
            self.files
                .get(&filename.to_lowercase())
                .cloned()
                .unwrap_or_default(),
        );
        let evidence = choose(identity, filename, code, &rows, &[]);
        if !evidence.creator.is_empty() || evidence.kind.contains("review") {
            return evidence;
        }
        let mut found = BTreeMap::new();
        let mut longest = 0;
        for value in [filename, code] {
            let normalized = key(value);
            for (at, _) in normalized
                .char_indices()
                .skip(3)
                .chain(std::iter::once((normalized.len(), ' ')))
            {
                if at < longest {
                    continue;
                }
                if let Some(names) = self.prefixes.get(&normalized[..at]) {
                    if at > longest {
                        found.clear();
                        longest = at;
                    }
                    found.extend(names.clone());
                }
            }
        }
        if found.len() == 1 {
            let (creator, url) = found.into_iter().next().unwrap();
            return Evidence {
                creator,
                url,
                title: String::new(),
                kind: "creator directory / filename or internal prefix hint".into(),
                verified: false,
            };
        }
        if found.len() > 1 {
            return Evidence {
                kind: "ambiguous creator prefix / review".into(),
                ..evidence
            };
        }
        evidence
    }
}

pub fn choose(
    identity: &Identity,
    filename: &str,
    code: &str,
    records: &[Record],
    creators: &[Creator],
) -> Evidence {
    let exact: Vec<&Record> = records
        .iter()
        .filter(|r| r.content_hash.eq_ignore_ascii_case(&identity.sha256))
        .collect();
    let unique: BTreeSet<_> = exact
        .iter()
        .map(|r| (r.authors.join(", "), r.title.clone()))
        .collect();
    if unique.len() == 1 {
        let record = exact[0];
        return Evidence {
            creator: record.authors.join(", "),
            title: record.title.clone(),
            url: record.source_url.clone(),
            kind: format!("{} / exact SHA-256", record.provider),
            verified: true,
        };
    }
    if unique.len() > 1 {
        return Evidence {
            creator: String::new(),
            title: String::new(),
            url: String::new(),
            kind: "conflicting content-hash records / review".into(),
            verified: false,
        };
    }
    // A 32-bit fingerprint is discovery evidence, never proof of authorship.
    let weak: Vec<&Record> = records
        .iter()
        .filter(|r| {
            (r.fingerprint == Some(identity.curseforge_fingerprint)
                || r.provider == "wcif" && r.fingerprint.is_none())
                && r.bytes == Some(identity.bytes)
                && r.filename.eq_ignore_ascii_case(filename)
        })
        .collect();
    let unique: BTreeSet<_> = weak
        .iter()
        .map(|r| (r.authors.join(", "), r.title.clone()))
        .collect();
    if unique.len() == 1 {
        let record = weak[0];
        return Evidence {
            creator: record.authors.join(", "),
            title: record.title.clone(),
            url: record.source_url.clone(),
            kind: format!(
                "{} / {}+size+filename hint",
                record.provider,
                if record.fingerprint.is_some() {
                    "fingerprint"
                } else {
                    "attachment"
                }
            ),
            verified: false,
        };
    }
    if unique.len() > 1 {
        return Evidence {
            creator: String::new(),
            title: String::new(),
            url: String::new(),
            kind: "conflicting filename or fingerprint records / review".into(),
            verified: false,
        };
    }
    let inputs = [key(filename), key(code)];
    let mut candidates = BTreeMap::new();
    let mut longest = 0;
    for creator in creators {
        for alias in std::iter::once(&creator.name).chain(creator.aliases.iter()) {
            let k = key(alias);
            if k.len() < 3 || !inputs.iter().any(|s| s.starts_with(&k)) {
                continue;
            }
            if k.len() > longest {
                candidates.clear();
                longest = k.len();
            }
            if k.len() == longest {
                candidates.insert(creator.name.clone(), creator.source_url.clone());
            }
        }
    }
    if candidates.len() == 1 {
        let (name, url) = candidates.into_iter().next().unwrap();
        return Evidence {
            creator: name,
            title: String::new(),
            url,
            kind: "creator directory / filename or internal prefix hint".into(),
            verified: false,
        };
    }
    Evidence {
        creator: String::new(),
        title: String::new(),
        url: String::new(),
        kind: if candidates.is_empty() {
            "unidentified"
        } else {
            "ambiguous creator prefix / review"
        }
        .into(),
        verified: false,
    }
}

pub struct Options<'a> {
    pub index: &'a Path,
    pub expected_sha256: &'a str,
    pub output: &'a Path,
    pub cache: &'a Path,
    pub s4mm: &'a [PathBuf],
    pub imports: &'a [PathBuf],
    pub creator_imports: &'a [PathBuf],
    pub wcif_databases: &'a [PathBuf],
    pub online_creators: bool,
    pub wcif_creators: bool,
    pub curseforge_key: Option<&'a str>,
    pub workers: usize,
}

pub fn run(options: Options<'_>) -> Result<Value> {
    let start = Instant::now();
    ensure!(
        !options.output.exists(),
        "Use a fresh catalogue snapshot; existing files are never overwritten"
    );
    ensure!(
        providers::hash(options.expected_sha256)
            && file_sha256(options.index)? == options.expected_sha256,
        "Input catalogue digest differs"
    );
    ensure!(
        (1..=8).contains(&options.workers),
        "Choose 1..8 explicit indexing workers"
    );
    ensure!(
        options.cache != options.index && options.cache != options.output,
        "Fingerprint cache must be separate from catalogue inputs"
    );
    let source = providers::readonly(options.index)?;
    let version: i64 = source.query_row("PRAGMA user_version", [], |r| r.get(0))?;
    ensure!(
        matches!(version, 3..=7),
        "A grouped schema-3..7 catalogue is required"
    );
    let package_paths:Vec<(String,String)>=source.prepare("SELECT DISTINCT json_extract(row_json,'$.package_path'),json_extract(row_json,'$.package_sha256') FROM parts")?
        .query_map([],|r|Ok((r.get(0)?,r.get(1)?)))?.collect::<rusqlite::Result<_>>()?;
    ensure!(
        package_paths.len() <= 100000,
        "Package import exceeds its bound"
    );
    let mut records = Vec::new();
    let mut creators = Vec::new();
    let mut network_sources = Vec::new();
    let seed = providers::bundled_profiles()?;
    let mut profiles = seed.profiles;
    creators.extend(seed.creators);
    let source_snapshot: Value =
        serde_json::from_str(
            &source.query_row("SELECT value FROM snapshot", [], |r| r.get::<_, String>(0))?,
        )?;
    let mut archives = source_snapshot["provider_archives"]
        .as_array()
        .cloned()
        .unwrap_or_default();
    archives.push(json!({"provider":"wcif","coverage":seed.coverage}));
    if version >= 6 {
        creators = source
            .prepare("SELECT name,aliases_json,source_url FROM creator_directory")?
            .query_map([], |r| {
                Ok((
                    r.get::<_, String>(0)?,
                    r.get::<_, String>(1)?,
                    r.get::<_, String>(2)?,
                ))
            })?
            .map(|row| {
                let (name, aliases, url) = row?;
                Ok(Creator {
                    name,
                    aliases: serde_json::from_str(&aliases)?,
                    source_url: url,
                })
            })
            .collect::<Result<_>>()?;
        records=source.prepare("SELECT provider,source_url,title,authors_json,content_hash,fingerprint,bytes,filename FROM metadata_sources")?
            .query_map([],|r|Ok((r.get::<_,String>(0)?,r.get::<_,String>(1)?,r.get::<_,String>(2)?,r.get::<_,String>(3)?,r.get::<_,String>(4)?,r.get::<_,Option<u32>>(5)?,r.get::<_,Option<i64>>(6)?,r.get::<_,String>(7)?)))?
            .map(|row|{let(provider,source_url,title,authors,content_hash,fingerprint,bytes,filename)=row?;Ok(Record{provider,source_url,title,authors:serde_json::from_str(&authors)?,content_hash,fingerprint,bytes:bytes.map(u64::try_from).transpose()?,filename})}).collect::<Result<_>>()?;
        ensure!(
            records.len() <= 100000 && creators.len() <= 50000,
            "Previous metadata exceeds its import bound"
        );
    }
    for path in options.s4mm {
        records.extend(providers::s4mm(path)?);
    }
    for path in options.wcif_databases {
        let archive = providers::wcif_archive(path, &package_paths)?;
        archives.push(
            json!({"provider":"wcif","sha256":file_sha256(path)?,"coverage":archive.coverage}),
        );
        creators.extend(archive.creators);
        records.extend(archive.records);
        profiles.extend(archive.profiles);
    }
    for path in options.imports {
        records.extend(providers::import_records(path)?);
    }
    for path in options.creator_imports {
        ensure!(
            path.metadata()?.len() <= 16 * 1024 * 1024,
            "Creator import exceeds its bound"
        );
        let rows: Vec<Creator> = serde_json::from_reader(std::fs::File::open(path)?)?;
        ensure!(rows.len() <= 50000, "Creator import exceeds its row bound");
        creators.extend(rows);
    }
    if options.online_creators {
        creators.extend(providers::public_creators(&providers::client()?)?);
        network_sources.push(providers::S4MM_CREATORS);
    }
    if options.wcif_creators {
        creators.extend(providers::wcif_creators(&providers::client()?)?);
        network_sources.push("https://wcif.cc/creators");
    }
    for record in &records {
        for name in &record.authors {
            creators.push(Creator {
                name: name.clone(),
                aliases: Vec::new(),
                source_url: record.source_url.clone(),
            });
        }
    }
    let mut names = BTreeMap::new();
    for creator in creators {
        ensure!(
            !creator.name.is_empty()
                && creator.name.chars().count() <= 160
                && creator.aliases.len() <= 100
                && creator.aliases.iter().all(|s| s.chars().count() <= 160),
            "Invalid creator alias record"
        );
        ensure!(
            creator.source_url.starts_with("https://")
                && !creator.name.chars().any(char::is_control),
            "Creator requires a public source"
        );
        names.entry(creator.name.to_lowercase()).or_insert(creator);
    }
    let creators: Vec<Creator> = names.into_values().collect();
    if let Some(parent) = options.cache.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let cache = Connection::open(options.cache)?;
    cache.execute_batch("CREATE TABLE IF NOT EXISTS fingerprints(sha256 TEXT PRIMARY KEY,identity_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS package_history(sha256 TEXT PRIMARY KEY,first_seen INTEGER NOT NULL,baseline INTEGER NOT NULL);")?;
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)?
        .as_secs() as i64;
    let baseline: bool = cache.query_row(
        "SELECT NOT EXISTS(SELECT 1 FROM package_history)",
        [],
        |r| r.get(0),
    )?;
    let mut identities = BTreeMap::new();
    let mut missing = Vec::new();
    let mut reused = 0;
    for (path, expected) in &package_paths {
        ensure!(
            providers::hash(expected),
            "Package source has an invalid SHA-256"
        );
        // Existing immutable source SHA is checked against current bytes even
        // when the expensive Murmur fingerprint is reused. No mtime-only trust.
        let cached = cache.query_row(
            "SELECT identity_json FROM fingerprints WHERE sha256=?",
            [expected],
            |r| r.get::<_, String>(0),
        );
        if let Ok(raw) = cached {
            ensure!(
                file_sha256(Path::new(path))? == *expected,
                "Installed package changed; rebuild the source catalogue first"
            );
            let identity: Identity = serde_json::from_str(&raw)?;
            ensure!(
                identity.sha256 == *expected,
                "Fingerprint cache identity differs"
            );
            identities.insert(path.clone(), identity);
            reused += 1;
        } else {
            missing.push((path.clone(), expected.clone()));
        }
    }
    let pool = rayon::ThreadPoolBuilder::new()
        .num_threads(options.workers)
        .build()?;
    let calculated: Vec<_> = pool.install(|| {
        missing
            .par_iter()
            .map(|(path, expected)| {
                let identity = file_identity(Path::new(path))?;
                ensure!(
                    identity.sha256 == *expected,
                    "Source package changed while indexing"
                );
                Ok::<_, anyhow::Error>((path.clone(), identity))
            })
            .collect::<Result<Vec<_>>>()
    })?;
    for (path, identity) in calculated {
        cache.execute(
            "INSERT OR REPLACE INTO fingerprints VALUES(?,?)",
            params![identity.sha256, serde_json::to_string(&identity)?],
        )?;
        identities.insert(path, identity);
    }
    let mut dates = BTreeMap::new();
    for (path, identity) in &identities {
        cache.execute(
            "INSERT OR IGNORE INTO package_history VALUES(?,?,?)",
            params![identity.sha256, now, baseline],
        )?;
        let (first_seen, initial): (i64, bool) = cache.query_row(
            "SELECT first_seen,baseline FROM package_history WHERE sha256=?",
            [&identity.sha256],
            |r| Ok((r.get(0)?, r.get(1)?)),
        )?;
        let modified = std::fs::metadata(path)?
            .modified()?
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_secs() as i64)
            .unwrap_or(0);
        dates.insert(path.clone(), (first_seen, initial, modified));
    }
    if let Some(key) = options.curseforge_key {
        let fps: BTreeSet<_> = identities
            .values()
            .map(|i| i.curseforge_fingerprint)
            .collect();
        records.extend(providers::curseforge(
            &providers::client()?,
            key,
            &fps.into_iter().collect::<Vec<_>>(),
        )?);
        network_sources.push("https://api.curseforge.com/v1/fingerprints/78062");
    }
    let records: Vec<Record> = records
        .into_iter()
        .map(|r| Ok((serde_json::to_string(&r)?, r)))
        .collect::<Result<BTreeMap<_, _>>>()?
        .into_values()
        .collect();
    ensure!(
        records.len() <= 100000,
        "Provider records exceed the explicit metadata bound"
    );
    let resolver = Resolver::new(&records, &creators);
    let mut package_evidence = BTreeMap::new();
    for (path, identity) in &identities {
        let filename = Path::new(path)
            .file_name()
            .and_then(|s| s.to_str())
            .context("Package filename is not valid Unicode")?;
        package_evidence.insert(path.clone(), resolver.resolve(identity, filename, ""));
    }
    let parent = options
        .output
        .parent()
        .context("Output catalogue needs a parent directory")?;
    std::fs::create_dir_all(parent)?;
    let temp = tempfile::NamedTempFile::new_in(parent)?;
    std::fs::copy(options.index, temp.path())?;
    let mut output = Connection::open(temp.path())?;
    if version < 5 {
        // Names are derived search data. Early catalogues predate the alias
        // column; rebuild their FTS table rather than editing a source package
        // or pretending an old index already has the new search contract.
        output.execute_batch("DROP TABLE names;CREATE VIRTUAL TABLE names USING fts5(preferred_name,package_name,code_name,search_aliases);")?;
    }
    if version < 6 {
        output.execute_batch("ALTER TABLE parts ADD COLUMN creator TEXT COLLATE NOCASE; ALTER TABLE parts ADD COLUMN title TEXT; ALTER TABLE parts ADD COLUMN package_sha256 TEXT; ALTER TABLE parts ADD COLUMN creator_key TEXT;")?;
    }
    if version < 7 {
        output.execute_batch("ALTER TABLE parts ADD COLUMN folder_key TEXT; ALTER TABLE parts ADD COLUMN first_seen INTEGER; ALTER TABLE parts ADD COLUMN baseline INTEGER; ALTER TABLE parts ADD COLUMN modified INTEGER;")?;
    }
    output.execute_batch("PRAGMA user_version=7; CREATE TABLE IF NOT EXISTS creator_directory(name TEXT PRIMARY KEY,source_url TEXT,aliases_json TEXT); DELETE FROM creator_directory; CREATE TABLE IF NOT EXISTS metadata_sources(provider TEXT,source_url TEXT,title TEXT,authors_json TEXT,content_hash TEXT,fingerprint INTEGER,bytes INTEGER,filename TEXT); DELETE FROM metadata_sources;")?;
    output.execute_batch("CREATE TABLE IF NOT EXISTS provider_profiles(provider TEXT,id TEXT,record_json TEXT,source_url TEXT,PRIMARY KEY(provider,id)) WITHOUT ROWID;")?;
    crate::folders::create(&output)?;
    let tx = output.transaction()?;
    for profile in &profiles {
        tx.execute(
            "INSERT OR REPLACE INTO provider_profiles VALUES('wcif',?,?,?)",
            params![
                profile["id"].as_str(),
                profile.to_string(),
                "https://wcif.cc/creators"
            ],
        )?;
    }
    for creator in &creators {
        tx.execute(
            "INSERT INTO creator_directory VALUES(?,?,?)",
            params![
                creator.name,
                creator.source_url,
                serde_json::to_string(&creator.aliases)?
            ],
        )?;
    }
    for r in &records {
        let bytes = r.bytes.map(i64::try_from).transpose()?;
        tx.execute(
            "INSERT INTO metadata_sources VALUES(?,?,?,?,?,?,?,?)",
            params![
                r.provider,
                r.source_url,
                r.title,
                serde_json::to_string(&r.authors)?,
                r.content_hash,
                r.fingerprint,
                bytes,
                r.filename
            ],
        )?;
    }
    tx.execute("DELETE FROM names", [])?;
    let mut exact = 0;
    let mut hints = 0;
    let mut count = 0;
    let mut statement =
        source.prepare("SELECT rowid,part_id,origin,row_json FROM parts ORDER BY rowid")?;
    let mut rows = statement.query([])?;
    while let Some(row) = rows.next()? {
        let rowid: i64 = row.get(0)?;
        let id: String = row.get(1)?;
        let origin: String = row.get(2)?;
        let mut value: Value = serde_json::from_str(&row.get::<_, String>(3)?)?;
        let filename = value["package_name"]
            .as_str()
            .context("Missing original package filename")?
            .to_owned();
        let code = value["code_name"].as_str().unwrap_or_default().to_owned();
        let identity = identities
            .get(
                value["package_path"]
                    .as_str()
                    .context("Missing original package path")?,
            )
            .context("Unbound package metadata")?;
        let evidence = if origin == "ea" {
            Evidence {
                creator: "EA".into(),
                title: String::new(),
                url: "https://www.ea.com/games/the-sims/the-sims-4".into(),
                kind: "EA resource".into(),
                verified: true,
            }
        } else {
            let e = package_evidence
                .get(value["package_path"].as_str().unwrap())
                .unwrap();
            if !e.creator.is_empty() || e.kind.contains("review") {
                e.clone()
            } else {
                resolver.resolve(identity, &filename, &code)
            }
        };
        if evidence.verified {
            exact += 1;
        } else if !evidence.creator.is_empty() {
            hints += 1;
        }
        if !evidence.creator.is_empty() {
            value["creator_hint"] = json!(evidence.creator);
        }
        value["creator_source"] = json!(evidence.kind);
        value["creator_verified"] = json!(evidence.verified);
        value["provider_title"] = json!(evidence.title);
        value["metadata_source_url"] = json!(evidence.url);
        value["metadata_source_sha256"] = json!(identity.sha256);
        let path = value["package_path"].as_str().unwrap();
        let folder = crate::folders::relative(path);
        let (first_seen, initial, modified) = dates[path];
        crate::folders::insert(&tx, &folder)?;
        value["folder_relative"] = json!(folder);
        value["first_seen_unix"] = json!(first_seen);
        value["first_scan_baseline"] = json!(initial);
        value["modified_unix"] = json!(modified);
        let title = value["preferred_name"].as_str().unwrap_or(&code).to_owned();
        let creator = value["creator_hint"].as_str().unwrap_or_default();
        tx.execute("UPDATE parts SET row_json=?,creator=?,title=?,package_sha256=?,creator_key=?,folder_key=?,first_seen=?,baseline=?,modified=? WHERE part_id=?",params![serde_json::to_string(&value)?,creator,title,identity.sha256,crate::text::creator_key(creator),crate::folders::normalize(&folder),first_seen,initial,modified,id])?;
        let searchable = aliases(&format!(
            "{} {} {} {} {}",
            title, filename, code, creator, evidence.title
        ));
        tx.execute("INSERT INTO names(rowid,preferred_name,package_name,code_name,search_aliases) VALUES(?,?,?,?,?)",params![rowid,title,filename,code,searchable])?;
        count += 1;
    }
    tx.execute_batch("CREATE INDEX IF NOT EXISTS parts_creator ON parts(creator_key,body_type,origin,part_id); CREATE INDEX IF NOT EXISTS parts_package_sha256 ON parts(package_sha256);
        CREATE INDEX IF NOT EXISTS parts_folder ON parts(folder_key,body_type,origin,part_id);
        CREATE INDEX IF NOT EXISTS parts_added ON parts(first_seen DESC,part_id); CREATE INDEX IF NOT EXISTS parts_modified ON parts(modified DESC,part_id);")?;
    tx.commit()?;
    // Precompute spelling deletes once. Search never scans packages or builds
    // an all-library vocabulary while a player is typing.
    output.execute_batch("CREATE VIRTUAL TABLE IF NOT EXISTS apex_vocab USING fts5vocab(names,'row'); CREATE TABLE IF NOT EXISTS spelling(deleted TEXT,term TEXT,PRIMARY KEY(deleted,term)) WITHOUT ROWID; DELETE FROM spelling;")?;
    let vocabulary: Vec<String> = output
        .prepare("SELECT term FROM apex_vocab WHERE length(term) BETWEEN 3 AND 48 LIMIT 500001")?
        .query_map([], |r| r.get(0))?
        .collect::<rusqlite::Result<_>>()?;
    ensure!(
        vocabulary.len() <= 500000,
        "Vocabulary exceeds the explicit index bound"
    );
    let tx = output.transaction()?;
    for term in &vocabulary {
        for deleted in deletions(term) {
            tx.execute(
                "INSERT OR IGNORE INTO spelling VALUES(?,?)",
                params![deleted, term],
            )?;
        }
    }
    tx.commit()?;
    let mut snapshot: Value =
        serde_json::from_str(
            &output.query_row("SELECT value FROM snapshot", [], |r| r.get::<_, String>(0))?,
        )?;
    snapshot["schema"] = json!(7);
    snapshot["enrichment"] = json!({"creators":creators.len(),"records":records.len(),"verified_parts":exact,"hinted_parts":hints,"network_sources":network_sources,"user_started_job":true,"background_service":false});
    snapshot["history"] = json!({"clock":"first observed SHA-256 in the explicit local indexing job","baseline_created":baseline,"indexed_unix":now,"moved_identical_content_remains_known":true});
    snapshot["provider_archives"] = json!(archives);
    crate::optimize::prepare(&output)?;
    snapshot["native_family_lookup"] = json!(true);
    output.execute(
        "UPDATE snapshot SET value=?",
        [serde_json::to_string(&snapshot)?],
    )?;
    output.execute_batch("PRAGMA optimize;")?;
    drop(output);
    temp.as_file().sync_all()?;
    ensure!(
        file_sha256(options.index)? == options.expected_sha256,
        "Source catalogue changed before publication"
    );
    temp.persist_noclobber(options.output)
        .map_err(|e| e.error)?;
    let digest = file_sha256(options.output)?;
    Ok(
        json!({"ok":true,"schema":7,"index":options.output,"index_sha256":digest,"packages":package_paths.len(),"parts":count,"creators":creators.len(),"provider_records":records.len(),"verified_parts":exact,"hinted_parts":hints,"fingerprints_reused":reused,"baseline_created":baseline,"elapsed_ms":start.elapsed().as_millis(),"source_packages_modified":false,"service_installed":false,"job_complete":true}),
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    fn identity() -> Identity {
        Identity {
            sha256: "a".repeat(64),
            blake3: "b".repeat(64),
            curseforge_fingerprint: 42,
            bytes: 100,
        }
    }
    fn record(author: &str) -> Record {
        Record {
            provider: "user".into(),
            source_url: "https://example.org/item".into(),
            title: "Lipstick".into(),
            authors: vec![author.into()],
            content_hash: "a".repeat(64),
            ..Default::default()
        }
    }
    #[test]
    fn contradictory_strong_records_never_choose_a_winner() {
        let r = choose(
            &identity(),
            "test.package",
            "",
            &[record("One"), record("Two")],
            &[],
        );
        assert!(!r.verified);
        assert!(r.creator.is_empty());
        assert!(r.kind.contains("conflicting"));
    }
    #[test]
    fn strong_hash_beats_a_filename_hint() {
        let r = choose(
            &identity(),
            "Wrong_package.package",
            "",
            &[record("Correct")],
            &[],
        );
        assert!(r.verified);
        assert_eq!(r.creator, "Correct");
    }
    #[test]
    fn fingerprint_collision_is_not_a_verified_match() {
        let mut r = record("One");
        r.content_hash.clear();
        r.fingerprint = Some(42);
        r.bytes = Some(100);
        r.filename = "item.package".into();
        let e = choose(&identity(), "item.package", "", &[r], &[]);
        assert!(!e.verified);
        assert_eq!(e.creator, "One");
    }
    #[test]
    fn camel_case_and_unicode_names_remain_searchable() {
        assert_eq!(aliases("MagicHand_yfLipstick"), "magic hand yf lipstick");
        assert!(aliases("头发_Étoile").contains("étoile"));
    }
}
