//! Provenance across providers. A link discovered in WCIF remains a WCIF
//! observation about that site, not a fabricated independent provider match.
use anyhow::{Result, ensure};
use reqwest::Url;
use rusqlite::{Connection, params};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::{
    io::Read,
    path::Path,
    sync::OnceLock,
    time::{SystemTime, UNIX_EPOCH},
};

pub fn provider(url: &str) -> Option<&'static str> {
    let value = Url::parse(url).ok()?;
    if value.scheme() != "https" || !value.username().is_empty() || value.password().is_some() {
        return None;
    }
    let host = value.host_str()?;
    for (domain, name) in [
        ("wcif.cc", "wcif"),
        ("curseforge.com", "curseforge"),
        ("thesimsresource.com", "tsr"),
        ("simsfinds.com", "simsfinds"),
        ("thesimsfinds.com", "simsfinds"),
        ("ts4rebels.cc", "ts4rebels"),
        ("patreon.com", "patreon"),
        ("tumblr.com", "tumblr"),
        ("simfileshare.net", "simfileshare"),
        ("gametimedev.de", "gametimedev"),
    ] {
        if host == domain || host.ends_with(&format!(".{domain}")) {
            return Some(name);
        }
    }
    Some("website")
}
fn stamp() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs() as i64
}
pub fn index(path: &Path) -> Result<Value> {
    let mut c = Connection::open(path)?;
    ensure!(
        c.query_row("PRAGMA user_version", [], |r| r.get::<_, i64>(0))? == 8101,
        "Not an Apex WCIF archive"
    );
    let receipt: Value = serde_json::from_str(&c.query_row(
        "SELECT value FROM import_meta WHERE key='receipt'",
        [],
        |r| r.get::<_, String>(0),
    )?)?;
    ensure!(
        receipt["job_complete"] == true,
        "Wait for the explicit import job before indexing source links"
    );
    c.execute_batch("CREATE TABLE IF NOT EXISTS source_links(kind TEXT,entity_id TEXT,provider TEXT,url TEXT,observed_via TEXT,PRIMARY KEY(kind,entity_id,provider,url)) WITHOUT ROWID;
      CREATE INDEX IF NOT EXISTS links_provider ON source_links(provider,url);
      CREATE TABLE IF NOT EXISTS source_documents(url TEXT PRIMARY KEY,provider TEXT,http_status INTEGER,metadata_json TEXT,response_sha256 TEXT,fetched_at INTEGER,bytes INTEGER);")?;
    let tx = c.transaction()?;
    tx.execute("DELETE FROM source_links", [])?;
    for (kind, table) in [("creator", "creators"), ("item", "items")] {
        let mut statement = tx.prepare(&format!("SELECT id,data_json FROM {table} ORDER BY id"))?;
        let mut rows = statement.query([])?;
        while let Some(row) = rows.next()? {
            let id: String = row.get(0)?;
            let data: Value = serde_json::from_str(&row.get::<_, String>(1)?)?;
            let mut urls = Vec::new();
            if kind == "creator" {
                for field in [
                    "facebook",
                    "instagram",
                    "modCoPage",
                    "patreonPage",
                    "tSRPage",
                    "tumblrPage",
                    "youTube",
                    "website",
                    "url",
                ] {
                    if let Some(url) = data[field].as_str() {
                        urls.push(url);
                    }
                }
                if let Some(links) = data["socialLinks"].as_array() {
                    for link in links {
                        if let Some(url) = link["url"].as_str() {
                            urls.push(url);
                        }
                    }
                }
            } else {
                for field in ["Direct Downloadlink", "url", "sourceUrl"] {
                    if let Some(url) = data[field].as_str() {
                        urls.push(url);
                    }
                }
            }
            for url in urls {
                let url = url.trim();
                if url.len() > 4096 || url.chars().any(char::is_control) {
                    continue;
                }
                if let Some(provider) = provider(url) {
                    tx.execute(
                        "INSERT OR IGNORE INTO source_links VALUES(?,?,?,?,'wcif')",
                        params![kind, id, provider, url],
                    )?;
                }
            }
        }
    }
    tx.commit()?;
    let counts:Vec<Value>=c.prepare("SELECT provider,count(*),count(DISTINCT url) FROM source_links GROUP BY provider ORDER BY provider")?.query_map([],|r|Ok(json!({"provider":r.get::<_,String>(0)?,"observations":r.get::<_,i64>(1)?,"unique_urls":r.get::<_,i64>(2)?})))?.collect::<rusqlite::Result<_>>()?;
    Ok(
        json!({"ok":true,"archive_coverage_complete":receipt["ok"],"source_gaps":receipt["incomplete"],"sources":counts,"relationship":"link observed in WCIF; independent source fetch recorded separately","service_installed":false}),
    )
}
fn metadata(html: &str) -> Value {
    static LD: OnceLock<regex::Regex> = OnceLock::new();
    static TAG: OnceLock<regex::Regex> = OnceLock::new();
    static ATTR: OnceLock<regex::Regex> = OnceLock::new();
    let ld = LD.get_or_init(|| {
        regex::Regex::new(
            r#"(?is)<script\b[^>]*type\s*=\s*["']application/ld\+json["'][^>]*>(.*?)</script\s*>"#,
        )
        .unwrap()
    });
    let tag = TAG.get_or_init(|| regex::Regex::new(r"(?is)<(?:meta|link)\b[^>]*>").unwrap());
    let attr = ATTR.get_or_init(|| {
        regex::Regex::new(r#"(?i)([a-z][a-z0-9_:-]*)\s*=\s*(?:"([^"]*)"|'([^']*)')"#).unwrap()
    });
    let structured: Vec<Value> = ld
        .captures_iter(html)
        .take(64)
        .filter_map(|m| serde_json::from_str(&m[1]).ok())
        .collect();
    let mut properties = Vec::new();
    for tag in tag.find_iter(html).take(500) {
        if tag.len() > 16384 {
            continue;
        }
        let mut fields = serde_json::Map::new();
        for a in attr.captures_iter(tag.as_str()) {
            fields.insert(
                a[1].to_lowercase(),
                json!(a.get(2).or_else(|| a.get(3)).unwrap().as_str()),
            );
        }
        if fields
            .get("property")
            .and_then(Value::as_str)
            .is_some_and(|v| v.starts_with("og:") || v.starts_with("article:"))
            || fields.get("name").and_then(Value::as_str).is_some_and(|v| {
                matches!(
                    v,
                    "author" | "description" | "twitter:title" | "twitter:description"
                )
            })
            || fields.get("rel").and_then(Value::as_str) == Some("canonical")
        {
            properties.push(fields);
        }
    }
    json!({"json_ld":structured,"properties":properties,"scripts_executed":false,"author_identity_verified":false})
}
/// Bounded explicit direct-source refresh. Never follows download/image links,
/// logs in, starts a service, or calls provider websites during CAS search.
pub fn refresh(path: &Path, wanted: &str, limit: usize) -> Result<Value> {
    ensure!(
        matches!(wanted, "tsr" | "simsfinds" | "ts4rebels" | "curseforge"),
        "Choose a supported direct metadata provider"
    );
    ensure!(
        (1..=10000).contains(&limit),
        "Choose an explicit source-page limit from 1..10000"
    );
    let c = Connection::open(path)?;
    ensure!(
        c.query_row("PRAGMA user_version", [], |r| r.get::<_, i64>(0))? == 8101,
        "Not an Apex WCIF archive"
    );
    let mut urls: Vec<String> = c
        .prepare(
            "SELECT DISTINCT url FROM source_links WHERE provider=? ORDER BY kind,url LIMIT ?",
        )?
        .query_map(params![wanted, limit as i64], |r| r.get(0))?
        .collect::<rusqlite::Result<_>>()?;
    if urls.is_empty() {
        urls.push(
            match wanted {
                "tsr" => "https://www.thesimsresource.com/",
                "simsfinds" => "https://www.simsfinds.com/",
                "ts4rebels" => "https://ts4rebels.cc/",
                _ => "https://www.curseforge.com/sims4",
            }
            .into(),
        );
    }
    urls.retain(|url| {
        Url::parse(url).is_ok_and(|v| {
            let path = v.path().to_lowercase();
            ![".package", ".zip", ".rar", ".7z"]
                .iter()
                .any(|suffix| path.ends_with(suffix))
                && !path.contains("/files/download/")
                && !path.ends_with("/download")
        })
    });
    let client = crate::providers::client()?;
    let mut succeeded = 0;
    let mut statuses = std::collections::BTreeMap::new();
    for url in &urls {
        ensure!(
            provider(url) == Some(wanted),
            "Source URL changed provider identity"
        );
        let response = client.get(url).send();
        let (status, value, hash, bytes) = match response {
            Ok(response) => {
                let status = response.status().as_u16();
                let content = response
                    .headers()
                    .get("Content-Type")
                    .and_then(|v| v.to_str().ok())
                    .unwrap_or("")
                    .to_ascii_lowercase();
                if status == 200 && content.contains("text/html") {
                    let mut bytes = Vec::new();
                    response.take(4 * 1024 * 1024 + 1).read_to_end(&mut bytes)?;
                    ensure!(
                        bytes.len() <= 4 * 1024 * 1024,
                        "Source metadata page exceeds its bound"
                    );
                    let html = String::from_utf8_lossy(&bytes);
                    let value = metadata(&html);
                    if value["json_ld"].as_array().is_some_and(|a| !a.is_empty())
                        || value["properties"]
                            .as_array()
                            .is_some_and(|a| !a.is_empty())
                    {
                        succeeded += 1;
                    }
                    (
                        status,
                        value,
                        format!("{:x}", Sha256::digest(&bytes)),
                        bytes.len(),
                    )
                } else {
                    (
                        status,
                        json!({"available":false,"reason":"Source requires access, redirected, or did not return public HTML metadata"}),
                        String::new(),
                        0,
                    )
                }
            }
            Err(_) => (
                0,
                json!({"available":false,"reason":"Public metadata transport unavailable"}),
                String::new(),
                0,
            ),
        };
        *statuses.entry(status).or_insert(0) += 1;
        c.execute(
            "INSERT OR REPLACE INTO source_documents VALUES(?,?,?,?,?,?,?)",
            params![
                url,
                wanted,
                status,
                value.to_string(),
                hash,
                stamp(),
                bytes as i64
            ],
        )?;
    }
    Ok(
        json!({"ok":true,"provider":wanted,"pages_attempted":urls.len(),"pages_with_metadata":succeeded,"statuses":statuses,"credentials_used":false,"service_installed":false,"packages_downloaded":false}),
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn domains_cannot_be_spoofed_by_paths_credentials_or_suffixes() {
        assert_eq!(provider("https://www.thesimsresource.com/a"), Some("tsr"));
        assert_eq!(
            provider("https://evil.com/thesimsresource.com"),
            Some("website")
        );
        assert_eq!(
            provider("https://thesimsresource.com.evil.com"),
            Some("website")
        );
        assert_eq!(provider("https://user:pass@ts4rebels.cc/a"), None);
        assert_eq!(provider("http://wcif.cc"), None);
    }
    #[test]
    fn structured_metadata_preserves_multiple_claims_and_unknown_fields() {
        let html = r#"<meta content='An Author' name='author'><script type="application/ld+json">{"@type":"CreativeWork","author":{"name":"A"},"unknown":{"future":7}}</script><script>throw 1</script>"#;
        let v = metadata(html);
        assert_eq!(v["json_ld"][0]["unknown"]["future"], 7);
        assert_eq!(v["properties"][0]["content"], "An Author");
        assert_eq!(v["scripts_executed"], false);
    }
}
