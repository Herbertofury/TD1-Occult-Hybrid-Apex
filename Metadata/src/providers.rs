use anyhow::{Context, Result, ensure};
#[cfg(feature = "cli")]
use reqwest::blocking::Client;
use rusqlite::{Connection, OpenFlags};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::{collections::BTreeSet, io::Read, path::Path, time::Duration};

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Record {
    pub provider: String,
    pub source_url: String,
    pub title: String,
    pub authors: Vec<String>,
    #[serde(default)]
    pub content_hash: String,
    #[serde(default)]
    pub fingerprint: Option<u32>,
    #[serde(default)]
    pub bytes: Option<u64>,
    #[serde(default)]
    pub filename: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Creator {
    pub name: String,
    #[serde(default)]
    pub aliases: Vec<String>,
    pub source_url: String,
}

pub fn readonly(path: &Path) -> Result<Connection> {
    ensure!(path.is_file(), "Metadata input must be an existing file");
    let c = Connection::open_with_flags(
        path,
        OpenFlags::SQLITE_OPEN_READ_ONLY
            | OpenFlags::SQLITE_OPEN_NO_MUTEX
            | OpenFlags::SQLITE_OPEN_URI,
    )?;
    c.execute_batch("PRAGMA query_only=ON; PRAGMA trusted_schema=OFF;")?;
    Ok(c)
}

pub fn s4mm(path: &Path) -> Result<Vec<Record>> {
    // Public catalogue/file metadata only. Never read settings, session tokens,
    // browser storage, credentials or the app's embedded developer API key.
    let c = readonly(path)?;
    let has_hash = c
        .prepare("PRAGMA table_info(Files)")?
        .query_map([], |r| r.get::<_, String>(1))?
        .collect::<rusqlite::Result<Vec<_>>>()?
        .iter()
        .any(|s| s == "hash");
    let sql = format!(
        "SELECT f.name,f.size,f.fingerprint,{},m.name,m.primaryAuthor,m.link \
        FROM Files f JOIN CurseForge m ON m.id=f.cf_id WHERE f.cf_id>0 LIMIT 100001",
        if has_hash { "f.hash" } else { "NULL" }
    );
    let mut statement = c.prepare(&sql)?;
    let rows = statement.query_map([], |r| {
        Ok((
            r.get::<_, String>(0)?,
            r.get::<_, Option<i64>>(1)?,
            r.get::<_, Option<u32>>(2)?,
            r.get::<_, Option<String>>(3)?,
            r.get::<_, String>(4)?,
            r.get::<_, String>(5)?,
            r.get::<_, String>(6)?,
        ))
    })?;
    let mut out = Vec::new();
    for row in rows {
        let (filename, bytes, fingerprint, hash, title, author, source_url) = row?;
        ensure!(
            out.len() < 100000,
            "S4MM metadata exceeds the explicit import bound"
        );
        ensure!(bytes.is_none_or(|v| v >= 0), "Invalid cached file size");
        let bytes = bytes.map(|v| v as u64);
        let record = Record {
            provider: "s4mm-curseforge-cache".into(),
            source_url,
            title,
            authors: vec![author],
            content_hash: hash.unwrap_or_default(),
            fingerprint,
            bytes,
            filename,
        };
        validate(&record)?;
        out.push(record);
    }
    Ok(out)
}

pub fn validate(record: &Record) -> Result<()> {
    ensure!(
        matches!(
            record.provider.as_str(),
            "s4mm-curseforge-cache"
                | "curseforge"
                | "plumbdex"
                | "wcif"
                | "tsr"
                | "simsfinds"
                | "ts4rebels"
                | "user"
        ),
        "Unknown metadata provider"
    );
    ensure!(
        !record.title.is_empty() && record.title.chars().count() <= 1024,
        "Invalid metadata title"
    );
    ensure!(
        !record.authors.is_empty()
            && record.authors.len() <= 16
            && record.authors.iter().all(|s| !s.trim().is_empty()
                && s.chars().count() <= 160
                && !s.chars().any(char::is_control)),
        "Invalid metadata authors"
    );
    ensure!(
        record.content_hash.is_empty() || hash(&record.content_hash),
        "Expected a complete content digest"
    );
    ensure!(
        record.source_url.starts_with("https://")
            && record.source_url.len() <= 2048
            && !record.source_url.chars().any(char::is_control),
        "Metadata must retain a public HTTPS source"
    );
    Ok(())
}

pub fn hash(value: &str) -> bool {
    value.len() == 64 && value.bytes().all(|c| c.is_ascii_hexdigit())
}

#[cfg(feature = "cli")]
pub fn client() -> Result<Client> {
    Ok(Client::builder()
        .timeout(Duration::from_secs(20))
        .connect_timeout(Duration::from_secs(5))
        .redirect(reqwest::redirect::Policy::none())
        .user_agent("Apex-Catalog/0.1 explicit-metadata-refresh")
        .build()?)
}

#[cfg(feature = "cli")]
pub fn get_bounded(client: &Client, url: &str) -> Result<Vec<u8>> {
    ensure!(
        url.starts_with("https://"),
        "Metadata downloads require HTTPS"
    );
    let mut response = client.get(url).send()?.error_for_status()?;
    let mut raw = Vec::new();
    response
        .by_ref()
        .take(16 * 1024 * 1024 + 1)
        .read_to_end(&mut raw)?;
    ensure!(
        raw.len() <= 16 * 1024 * 1024,
        "Metadata response exceeds 16 MiB"
    );
    Ok(raw)
}

pub const S4MM_CREATORS: &str = "https://api.gametimedev.de/S4MM/cf/creators.txt";
#[cfg(feature = "cli")]
pub fn public_creators(client: &Client) -> Result<Vec<Creator>> {
    let bytes = get_bounded(client, S4MM_CREATORS)?;
    let text = std::str::from_utf8(&bytes).context("Creator directory must be UTF-8")?;
    let mut seen = BTreeSet::new();
    let mut out = Vec::new();
    for line in text.lines().map(str::trim).filter(|s| !s.is_empty()) {
        ensure!(
            line.chars().count() <= 160 && !line.chars().any(char::is_control),
            "Invalid creator directory row"
        );
        if seen.insert(line.to_lowercase()) {
            out.push(Creator {
                name: line.into(),
                aliases: Vec::new(),
                source_url: S4MM_CREATORS.into(),
            });
        }
    }
    ensure!(out.len() <= 50000, "Creator directory is too large");
    Ok(out)
}

#[cfg(feature = "cli")]
pub fn wcif_creators(client: &Client) -> Result<Vec<Creator>> {
    let mut out = Vec::new();
    let mut expected = None;
    let mut seen = BTreeSet::new();
    for page in 1..=500 {
        let response=client.post("https://api.wcif.cc/api/creators")
            .header("Origin","https://wcif.cc")
            .json(&serde_json::json!({"page":page,"limit":100,"searchQuery":"","sortBy":"name","sortOrder":"asc","filters":{}}))
            .send()?.error_for_status()?;
        let mut bytes = Vec::new();
        response
            .take(16 * 1024 * 1024 + 1)
            .read_to_end(&mut bytes)?;
        ensure!(
            bytes.len() <= 16 * 1024 * 1024,
            "WCIF creator page exceeds its bound"
        );
        let value: Value = serde_json::from_slice(&bytes)?;
        ensure!(
            value["success"] == true,
            "WCIF did not return a successful public creator page"
        );
        let total = value["totalResults"]
            .as_u64()
            .context("Missing public creator count")?;
        ensure!(
            total <= 50000 && expected.is_none_or(|n| n == total),
            "WCIF directory changed while paging; repeat the explicit refresh"
        );
        expected = Some(total);
        let rows = value["creators"]
            .as_array()
            .context("Missing public creators")?;
        ensure!(rows.len() <= 100, "WCIF page exceeds its row bound");
        for row in rows {
            let id = row["id"]
                .as_u64()
                .map(|v| v.to_string())
                .or_else(|| row["id"].as_str().map(String::from))
                .context("Missing creator identity")?;
            ensure!(seen.insert(id), "Repeated public creator while paging");
            let name = row["displayName"]
                .as_str()
                .filter(|s| !s.trim().is_empty())
                .or_else(|| row["name"].as_str())
                .context("Missing creator name")?
                .trim()
                .to_owned();
            let mut aliases = BTreeSet::new();
            for field in ["name", "originalName"] {
                if let Some(s) = row[field].as_str().filter(|s| !s.trim().is_empty()) {
                    aliases.insert(s.trim().to_owned());
                }
            }
            ensure!(
                !name.is_empty() && name.chars().count() <= 160,
                "Invalid public creator name"
            );
            out.push(Creator {
                name,
                aliases: aliases.into_iter().collect(),
                source_url: "https://wcif.cc/creators".into(),
            });
        }
        if out.len() as u64 == total {
            return Ok(out);
        }
        ensure!(
            !rows.is_empty(),
            "WCIF directory ended before its declared total"
        );
    }
    anyhow::bail!("WCIF directory exceeds its explicit page bound")
}

pub fn import_records(path: &Path) -> Result<Vec<Record>> {
    ensure!(
        path.metadata()?.len() <= 64 * 1024 * 1024,
        "Metadata import is too large"
    );
    let values: Vec<Record> = serde_json::from_reader(std::fs::File::open(path)?)?;
    ensure!(values.len() <= 100000, "Too many metadata records");
    for row in &values {
        validate(row)?;
    }
    Ok(values)
}

#[cfg(feature = "cli")]
pub struct WcifArchive {
    pub creators: Vec<Creator>,
    pub records: Vec<Record>,
    pub profiles: Vec<Value>,
    pub coverage: Value,
}

#[cfg(feature = "cli")]
pub fn bundled_profiles() -> Result<WcifArchive> {
    let seed: Value = serde_json::from_str(include_str!("../data/wcif-creator-seed.json"))?;
    ensure!(
        seed["schema"] == 1
            && seed["provider"] == "wcif"
            && seed["creator_objects_complete"] == true,
        "Bundled creator seed schema differs"
    );
    let profiles = seed["creators"]
        .as_array()
        .context("Bundled seed has no creators")?
        .clone();
    ensure!(
        profiles.len() <= 50000,
        "Bundled seed exceeds its row bound"
    );
    let mut creators = Vec::new();
    for value in &profiles {
        let id = value["id"]
            .as_str()
            .context("Bundled creator has no stable identity")?;
        let name = value["displayName"]
            .as_str()
            .filter(|s| !s.is_empty())
            .or_else(|| value["name"].as_str())
            .context("Bundled creator has no name")?
            .to_owned();
        let aliases = ["name", "originalName", "displayName"]
            .into_iter()
            .filter_map(|field| value[field].as_str().map(String::from))
            .collect();
        creators.push(Creator {
            name,
            aliases,
            source_url: format!("https://wcif.cc/creators/{id}"),
        });
    }
    Ok(WcifArchive {
        creators,
        records: Vec::new(),
        profiles,
        coverage: json!({"scope":"bundled creator objects only","creators":seed["creators"].as_array().unwrap().len(),"item_archive_bundled":false,"fetched_date":seed["fetched_date"]}),
    })
}
#[cfg(feature = "cli")]
pub fn wcif_archive(path: &Path, packages: &[(String, String)]) -> Result<WcifArchive> {
    let c = readonly(path)?;
    ensure!(
        c.query_row("PRAGMA user_version", [], |r| r.get::<_, i64>(0))? == 8101,
        "Not an Apex WCIF archive"
    );
    let coverage: Value = serde_json::from_str(&c.query_row(
        "SELECT value FROM import_meta WHERE key='receipt'",
        [],
        |r| r.get::<_, String>(0),
    )?)?;
    ensure!(
        coverage["job_complete"] == true,
        "Wait for the explicit WCIF import job to finish"
    );
    ensure!(
        c.query_row(
            "SELECT value FROM import_meta WHERE key='files_indexed'",
            [],
            |r| r.get::<_, String>(0)
        )? == "true",
        "Run wcif-index once before matching installed attachments"
    );
    let mut out = WcifArchive {
        creators: Vec::new(),
        records: Vec::new(),
        profiles: Vec::new(),
        coverage,
    };
    let mut authors = std::collections::BTreeMap::new();
    for row in c.prepare("SELECT creators.id,data_json FROM creators JOIN creator_roster ON creator_roster.id=creators.id ORDER BY creators.id")?.query_map([],|r|Ok((r.get::<_,String>(0)?,r.get::<_,String>(1)?)))? {
        let (id,raw)=row?;let value:Value=serde_json::from_str(&raw)?;
        let name=value["displayName"].as_str().filter(|s|!s.is_empty()).or_else(||value["name"].as_str()).context("WCIF profile has no name")?.to_owned();
        let aliases=["name","originalName","displayName"].into_iter().filter_map(|field|value[field].as_str().map(String::from)).collect();
        authors.insert(id.clone(),name.clone());out.creators.push(Creator{name,aliases,source_url:format!("https://wcif.cc/creators/{id}")});out.profiles.push(value);
    }
    ensure!(
        out.creators.len() <= 50000,
        "WCIF archive creator inventory exceeds its bound"
    );
    let mut seen = BTreeSet::new();
    let mut statement=c.prepare_cached("SELECT f.filename,f.bytes,f.item_id,f.creator_id,i.data_json FROM files f JOIN items i ON i.id=f.item_id WHERE filename_key=? AND bytes=? LIMIT 101")?;
    for (path, _) in packages {
        let filename = Path::new(path)
            .file_name()
            .and_then(|v| v.to_str())
            .context("Package filename is not Unicode")?;
        let bytes = i64::try_from(std::fs::metadata(path)?.len())?;
        let mut matches = 0;
        for row in statement.query_map(rusqlite::params![filename.to_lowercase(), bytes], |r| {
            Ok((
                r.get::<_, String>(0)?,
                r.get::<_, i64>(1)?,
                r.get::<_, String>(2)?,
                r.get::<_, String>(3)?,
                r.get::<_, String>(4)?,
            ))
        })? {
            let (filename, bytes, item, creator, raw) = row?;
            matches += 1;
            ensure!(
                matches <= 100,
                "Ambiguous installed attachment has too many WCIF matches"
            );
            if !seen.insert((item.clone(), filename.clone(), bytes)) {
                continue;
            }
            let value: Value = serde_json::from_str(&raw)?;
            let Some(author) = authors.get(&creator) else {
                continue;
            };
            let r = Record {
                provider: "wcif".into(),
                source_url: format!("https://wcif.cc/cc/{item}"),
                title: value["Name"].as_str().unwrap_or_default().into(),
                authors: vec![author.clone()],
                content_hash: String::new(),
                fingerprint: None,
                bytes: Some(u64::try_from(bytes)?),
                filename,
            };
            validate(&r)?;
            out.records.push(r);
        }
    }
    Ok(out)
}

// Official API calls only when the user supplies their own configured key.
// Hashes are sent in bounded batches; paths and package bytes are never sent.
#[cfg(feature = "cli")]
pub fn curseforge(client: &Client, key: &str, fingerprints: &[u32]) -> Result<Vec<Record>> {
    ensure!(
        !key.is_empty() && key.len() <= 512,
        "A configured CurseForge API key is required"
    );
    let mut out = Vec::new();
    for batch in fingerprints.chunks(500) {
        let response = client
            .post("https://api.curseforge.com/v1/fingerprints/78062")
            .header("x-api-key", key)
            .json(&serde_json::json!({"fingerprints":batch}))
            .send()?
            .error_for_status()?;
        let mut bytes = Vec::new();
        response
            .take(16 * 1024 * 1024 + 1)
            .read_to_end(&mut bytes)?;
        ensure!(
            bytes.len() <= 16 * 1024 * 1024,
            "CurseForge fingerprint response exceeds its bound"
        );
        let reply: Value = serde_json::from_slice(&bytes)?;
        let matches = reply["data"]["exactMatches"]
            .as_array()
            .context("Missing exact fingerprint matches")?;
        let ids: BTreeSet<u64> = matches.iter().filter_map(|v| v["id"].as_u64()).collect();
        let mut mods = std::collections::BTreeMap::new();
        for ids in ids.into_iter().collect::<Vec<_>>().chunks(50) {
            let response = client
                .post("https://api.curseforge.com/v1/mods")
                .header("x-api-key", key)
                .json(&serde_json::json!({"modIds":ids}))
                .send()?
                .error_for_status()?;
            let mut raw = Vec::new();
            response.take(16 * 1024 * 1024 + 1).read_to_end(&mut raw)?;
            ensure!(
                raw.len() <= 16 * 1024 * 1024,
                "CurseForge project page exceeds its bound"
            );
            let value: Value = serde_json::from_slice(&raw)?;
            for row in value["data"]
                .as_array()
                .context("Missing CurseForge projects")?
            {
                if row["gameId"].as_u64() == Some(78062) {
                    mods.insert(
                        row["id"].as_u64().context("Invalid project id")?,
                        row.clone(),
                    );
                }
            }
        }
        for row in matches {
            let id = row["id"].as_u64().context("Invalid matched project")?;
            let Some(project) = mods.get(&id) else {
                continue;
            };
            let file = &row["file"];
            ensure!(
                file["gameId"].as_u64() == Some(78062),
                "Foreign game in fingerprint match"
            );
            let fp = file["fileFingerprint"]
                .as_u64()
                .context("Missing file fingerprint")?;
            // This path identifies an exact installed release file. Archive
            // modules are not silently credited to the archive's publisher.
            // A separate normalized import may retain such containment hints.
            if fp <= u32::MAX as u64 && batch.contains(&(fp as u32)) {
                let record = Record {
                    provider: "curseforge".into(),
                    source_url: project["links"]["websiteUrl"]
                        .as_str()
                        .context("Missing project source")?
                        .into(),
                    title: project["name"]
                        .as_str()
                        .context("Missing project name")?
                        .into(),
                    authors: project["authors"]
                        .as_array()
                        .context("Missing project authors")?
                        .iter()
                        .filter_map(|a| a["name"].as_str().map(String::from))
                        .collect(),
                    fingerprint: Some(fp as u32),
                    bytes: file["fileLength"].as_u64(),
                    filename: file["fileName"].as_str().unwrap_or_default().into(),
                    content_hash: String::new(),
                };
                validate(&record)?;
                out.push(record);
            }
        }
    }
    Ok(out)
}
