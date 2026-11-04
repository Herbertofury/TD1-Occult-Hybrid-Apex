//! Explicit, resumable public WCIF metadata import. Never linked into the game.
//! Preserve complete returned objects, including unknown/future fields. No
//! images, packages, attachment URLs or external social sites are downloaded.
use anyhow::{Context, Result, ensure};
use reqwest::blocking::Client;
use rusqlite::{Connection, params};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::{
    collections::BTreeSet,
    io::Read,
    path::Path,
    time::{Duration, SystemTime, UNIX_EPOCH},
};

const API: &str = "https://api.wcif.cc/api";
const SOURCE: &str = "https://wcif.cc/creators?sortBy=favoriteCount";
fn now() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs() as i64
}
fn database(path: &Path) -> Result<Connection> {
    let c = Connection::open(path)?;
    c.busy_timeout(Duration::from_secs(20))?;
    c.execute_batch("PRAGMA foreign_keys=ON;PRAGMA trusted_schema=OFF;")?;
    Ok(c)
}
fn identity(row: &Value) -> Result<String> {
    let id = row["id"]
        .as_str()
        .map(String::from)
        .or_else(|| row["id"].as_u64().map(|n| n.to_string()))
        .context("WCIF object has no identity")?;
    ensure!(
        !id.is_empty() && id.len() <= 160 && !id.chars().any(char::is_control),
        "WCIF identity is invalid"
    );
    Ok(id)
}
fn post(client: &Client, route: &str, body: &Value) -> Result<(Value, String)> {
    let mut last = String::new();
    for attempt in 0..3 {
        let response = client
            .post(format!("{API}{route}"))
            .header("Origin", "https://wcif.cc")
            .json(body)
            .send();
        match response {
            Ok(response) => {
                let status = response.status();
                if status.as_u16() == 429 || status.is_server_error() {
                    last = format!("WCIF temporary status {}", status.as_u16());
                    let seconds = response
                        .headers()
                        .get("Retry-After")
                        .and_then(|v| v.to_str().ok())
                        .and_then(|v| v.parse::<u64>().ok())
                        .unwrap_or(2 + attempt * 2)
                        .min(20);
                    std::thread::sleep(Duration::from_secs(seconds));
                    continue;
                }
                let response = response.error_for_status()?;
                let mut bytes = Vec::new();
                response
                    .take(16 * 1024 * 1024 + 1)
                    .read_to_end(&mut bytes)?;
                ensure!(bytes.len() <= 16 * 1024 * 1024, "WCIF page exceeds 16 MiB");
                return Ok((
                    serde_json::from_slice(&bytes)?,
                    format!("{:x}", Sha256::digest(&bytes)),
                ));
            }
            Err(error) => {
                last = if error.is_timeout() {
                    "WCIF request timed out".into()
                } else {
                    "WCIF metadata transport failed".into()
                };
                std::thread::sleep(Duration::from_secs(2 + attempt * 2));
            }
        }
    }
    anyhow::bail!("{last}; re-run the same explicit job to resume")
}
fn creators(client: &Client, c: &mut Connection) -> Result<usize> {
    let mut seen = BTreeSet::new();
    let mut expected = None;
    let mut all = Vec::new();
    for page in 1..=500 {
        let (reply, hash) = post(
            client,
            "/creators",
            &json!({"page":page,"limit":100,"searchQuery":"","sortBy":"name","sortOrder":"asc","filters":{}}),
        )?;
        ensure!(
            reply["success"] == true,
            "WCIF directory request did not succeed"
        );
        let total = reply["totalResults"]
            .as_u64()
            .context("WCIF directory has no total")?;
        ensure!(
            total <= 50000 && expected.is_none_or(|v| v == total),
            "WCIF directory changed during paging; resume the explicit import"
        );
        expected = Some(total);
        let rows = reply["creators"]
            .as_array()
            .context("WCIF directory has no rows")?;
        ensure!(rows.len() <= 100, "WCIF directory page exceeds its bound");
        for row in rows {
            let id = identity(row)?;
            ensure!(
                seen.insert(id.clone()),
                "WCIF creator duplicated during paging"
            );
            all.push((id, row.clone()));
        }
        c.execute(
            "INSERT OR REPLACE INTO directory_pages VALUES(?,?,?,?)",
            params![page, hash, rows.len() as i64, now()],
        )?;
        if all.len() as u64 == total {
            break;
        }
        ensure!(
            !rows.is_empty() && (all.len() as u64) < total,
            "WCIF directory ended before its declared total"
        );
    }
    ensure!(
        Some(all.len() as u64) == expected,
        "WCIF directory pagination exceeded its bound"
    );
    let tx = c.transaction()?;
    tx.execute("DELETE FROM creator_roster", [])?;
    for (id, row) in &all {
        // Replace complete objects, never select a short list of known fields.
        tx.execute(
            "INSERT OR REPLACE INTO creators VALUES(?,?,?,?)",
            params![id, row.to_string(), SOURCE, now()],
        )?;
        tx.execute("INSERT INTO creator_roster VALUES(?)", [id])?;
    }
    tx.commit()?;
    Ok(all.len())
}
fn item_request(creator: &str, page: u64) -> Value {
    json!({"query":"","page":page,"resultsPerPage":100,"sortBy":"normalizedAdded","sortOrder":"asc",
        "creator":creator,"isLocked":true,"isFree":true,"timeFilter":"all","isScarletsRealm":false,
        "keepSimfileshare":true,"includeSearchText":true,"stylesFilter":[],"earlyAccessFilter":"all","hostedOnly":false})
}
fn import_creator(client: &Client, path: &Path, id: &str, expected_count: u64) -> Result<()> {
    let mut c = database(path)?;
    let complete:bool=c.query_row("SELECT EXISTS(SELECT 1 FROM coverage WHERE creator_id=? AND complete=1 AND declared_count=?)",params![id,expected_count as i64],|r|r.get(0))?;
    if complete {
        return Ok(());
    }
    c.execute("INSERT OR REPLACE INTO coverage(creator_id,declared_count,complete,error) VALUES(?,?,0,'')",params![id,expected_count as i64])?;
    let mut expected = None;
    let mut collected = 0_u64;
    let mut seen = BTreeSet::new();
    for page in 1..=20000_u64 {
        let cached:Option<(String,String)>=c.query_row("SELECT response_json,response_sha256 FROM item_pages WHERE creator_id=? AND page=?",params![id,page as i64],|r|Ok((r.get(0)?,r.get(1)?))).ok();
        let (reply, hash) = if let Some((raw, hash)) = cached {
            let mut value: Value = serde_json::from_str(&raw)?;
            if let Some(ids) = value.get("item_ids").and_then(Value::as_array) {
                let mut restored = Vec::new();
                for item in ids {
                    let raw: String = c.query_row(
                        "SELECT data_json FROM items WHERE id=?",
                        [item.as_str().context("Invalid cached item identity")?],
                        |r| r.get(0),
                    )?;
                    restored.push(serde_json::from_str::<Value>(&raw)?);
                }
                value["results"] = json!(restored);
                value.as_object_mut().unwrap().remove("item_ids");
            }
            (value, hash)
        } else {
            post(client, "/cc-items/search", &item_request(id, page))?
        };
        let total = reply["totalResults"]
            .as_u64()
            .context("WCIF item page has no total")?;
        ensure!(
            total <= 2_000_000 && expected.is_none_or(|v| v == total),
            "WCIF item count changed during paging; incomplete creator retained for review"
        );
        expected = Some(total);
        // A wrong limit/filter can return HTTP 200 with zero rows. Never label
        // that successful when the creator directory says items exist.
        ensure!(
            total != 0 || expected_count == 0,
            "WCIF returned no items for a nonempty creator"
        );
        let rows = reply["results"]
            .as_array()
            .context("WCIF item page has no results")?;
        ensure!(rows.len() <= 100, "WCIF item page exceeds its bound");
        let tx = c.transaction()?;
        for row in rows {
            let item = identity(row)?;
            ensure!(
                seen.insert(item.clone()),
                "WCIF item duplicated across pages; incomplete creator retained for review"
            );
            let creator = row["creatorId"]
                .as_str()
                .map(String::from)
                .or_else(|| row["creatorId"].as_u64().map(|v| v.to_string()));
            ensure!(
                creator.as_deref() == Some(id),
                "WCIF returned an item belonging to another creator"
            );
            tx.execute(
                "INSERT OR REPLACE INTO items VALUES(?,?,?,?)",
                params![
                    item,
                    row.to_string(),
                    format!("{API}/cc-items/search"),
                    now()
                ],
            )?;
            tx.execute(
                "INSERT OR IGNORE INTO creator_items VALUES(?,?)",
                params![id, item],
            )?;
        }
        // Keep each complete item once. Page receipts retain its ordered IDs
        // and all outer response fields instead of duplicating large objects.
        let mut receipt = reply.clone();
        receipt.as_object_mut().unwrap().remove("results");
        receipt["item_ids"] = json!(rows.iter().map(identity).collect::<Result<Vec<_>>>()?);
        tx.execute(
            "INSERT OR REPLACE INTO item_pages VALUES(?,?,?,?,?,?)",
            params![
                id,
                page as i64,
                receipt.to_string(),
                hash,
                rows.len() as i64,
                now()
            ],
        )?;
        tx.commit()?;
        collected += rows.len() as u64;
        if page % 25 == 0 {
            eprintln!(
                "{}",
                json!({"event":"wcif-items-progress","creator_id":id,"rows":collected,"total":total})
            );
        }
        if collected == total {
            c.execute("UPDATE coverage SET api_total=?,retrieved=?,complete=1,error='',completed_at=? WHERE creator_id=?",params![total as i64,collected as i64,now(),id])?;
            return Ok(());
        }
        ensure!(
            !rows.is_empty() && collected < total,
            "WCIF item pagination is incomplete"
        );
    }
    anyhow::bail!("WCIF creator exceeds its item pagination bound")
}

pub fn run(path: &Path, workers: usize) -> Result<Value> {
    ensure!(
        (1..=4).contains(&workers),
        "WCIF import allows 1..4 explicit HTTP workers"
    );
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let mut c = database(path)?;
    let version: i64 = c.query_row("PRAGMA user_version", [], |r| r.get(0))?;
    ensure!(
        matches!(version, 0 | 8101),
        "This is not an Apex WCIF archive"
    );
    if version == 0 {
        let count: i64 = c.query_row(
            "SELECT count(*) FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%'",
            [],
            |r| r.get(0),
        )?;
        ensure!(
            count == 0,
            "Refusing to change an unrelated SQLite database"
        );
    }
    c.execute_batch("PRAGMA user_version=8101;PRAGMA journal_mode=WAL;
      CREATE TABLE IF NOT EXISTS creators(id TEXT PRIMARY KEY,data_json TEXT NOT NULL,source_url TEXT,fetched_at INTEGER);
      CREATE TABLE IF NOT EXISTS creator_roster(id TEXT PRIMARY KEY);
      CREATE TABLE IF NOT EXISTS items(id TEXT PRIMARY KEY,data_json TEXT NOT NULL,source_url TEXT,fetched_at INTEGER);
      CREATE TABLE IF NOT EXISTS creator_items(creator_id TEXT,item_id TEXT,PRIMARY KEY(creator_id,item_id));
      CREATE TABLE IF NOT EXISTS directory_pages(page INTEGER PRIMARY KEY,response_sha256 TEXT,rows INTEGER,fetched_at INTEGER);
      CREATE TABLE IF NOT EXISTS item_pages(creator_id TEXT,page INTEGER,response_json TEXT,response_sha256 TEXT,rows INTEGER,fetched_at INTEGER,PRIMARY KEY(creator_id,page));
      CREATE TABLE IF NOT EXISTS coverage(creator_id TEXT PRIMARY KEY,declared_count INTEGER,api_total INTEGER,retrieved INTEGER,complete INTEGER,error TEXT,completed_at INTEGER);
      CREATE TABLE IF NOT EXISTS import_meta(key TEXT PRIMARY KEY,value TEXT);")?;
    c.execute(
        "INSERT OR REPLACE INTO import_meta VALUES('complete','false')",
        [],
    )?;
    let client = crate::providers::client()?;
    let count = creators(&client, &mut c)?;
    let rows:Vec<(String,u64)>=c.prepare("SELECT creators.id,COALESCE(json_extract(data_json,'$.itemCount'),0) FROM creators JOIN creator_roster ON creator_roster.id=creators.id ORDER BY creators.id")?
        .query_map([],|r|Ok((r.get(0)?,r.get::<_,i64>(1)? as u64)))?.collect::<rusqlite::Result<_>>()?;
    ensure!(
        rows.iter().all(|(_, n)| *n <= 2_000_000),
        "Creator item count exceeds its bound"
    );
    let declared: u64 = rows.iter().map(|r| r.1).sum();
    eprintln!(
        "{}",
        json!({"event":"wcif-directory-imported","creators":count,"declared_items":declared,"all_source_fields_preserved":true,"workers":workers})
    );
    let pool = rayon::ThreadPoolBuilder::new()
        .num_threads(workers)
        .build()?;
    use rayon::prelude::*;
    use std::sync::atomic::{AtomicUsize, Ordering};
    let finished = AtomicUsize::new(0);
    pool.install(||rows.par_iter().for_each(|(id,expected)|{
        if let Err(error)=import_creator(&client,path,id,*expected) {
            if let Ok(db)=database(path){let _=db.execute("UPDATE coverage SET complete=0,error=? WHERE creator_id=?",params![error.to_string(),id]);}
            eprintln!("{}",json!({"event":"wcif-creator-incomplete","creator_id":id,"reason":error.to_string()}));
        }
        let done=finished.fetch_add(1,Ordering::Relaxed)+1;
        if done%10==0||done==count{eprintln!("{}",json!({"event":"wcif-creators-progress","finished":done,"total":count}));}
    }));
    let complete:i64=c.query_row("SELECT count(*) FROM coverage JOIN creator_roster ON creator_roster.id=coverage.creator_id WHERE complete=1",[],|r|r.get(0))?;
    let items: i64 = c.query_row("SELECT count(*) FROM items", [], |r| r.get(0))?;
    let associated:i64=c.query_row("SELECT count(*) FROM creator_items JOIN creator_roster ON creator_roster.id=creator_items.creator_id",[],|r|r.get(0))?;
    let failures:Vec<Value>=c.prepare("SELECT creator_id,error FROM coverage JOIN creator_roster ON creator_roster.id=coverage.creator_id WHERE complete!=1 ORDER BY creator_id")?
        .query_map([],|r|Ok(json!({"creator_id":r.get::<_,String>(0)?,"error":r.get::<_,String>(1)?})))?.collect::<rusqlite::Result<_>>()?;
    let result = json!({"ok":complete as usize==count,"provider":"wcif","source":SOURCE,"archive":path,"creators":count,"complete_creators":complete,"unique_items":items,"creator_item_associations":associated,"declared_items":declared,"incomplete":failures,
        "all_source_fields_preserved":true,"images_downloaded":false,"packages_downloaded":false,"service_installed":false,"job_complete":true});
    c.execute(
        "INSERT OR REPLACE INTO import_meta VALUES('receipt',?)",
        [result.to_string()],
    )?;
    c.execute(
        "INSERT OR REPLACE INTO import_meta VALUES('complete',?)",
        [if complete as usize == count {
            "true"
        } else {
            "false"
        }],
    )?;
    c.execute_batch("PRAGMA wal_checkpoint(TRUNCATE);PRAGMA journal_mode=DELETE;PRAGMA optimize;")?;
    drop(c);
    Ok(result)
}

/// Materialize attachment filename/size lookups after a complete import. Full
/// original attachment objects remain in items.data_json; no URL is followed.
pub fn index_files(path: &Path) -> Result<Value> {
    let mut c = database(path)?;
    ensure!(
        c.query_row("PRAGMA user_version", [], |r| r.get::<_, i64>(0))? == 8101,
        "Not an Apex WCIF archive"
    );
    let coverage_complete = c.query_row(
        "SELECT value FROM import_meta WHERE key='complete'",
        [],
        |r| r.get::<_, String>(0),
    )? == "true";
    let receipt: Value = serde_json::from_str(&c.query_row(
        "SELECT value FROM import_meta WHERE key='receipt'",
        [],
        |r| r.get::<_, String>(0),
    )?)?;
    ensure!(
        receipt["job_complete"] == true,
        "Wait for the explicit import job before indexing available records"
    );
    c.execute_batch("CREATE TABLE IF NOT EXISTS files(filename_key TEXT,bytes INTEGER,item_id TEXT,creator_id TEXT,filename TEXT,PRIMARY KEY(filename_key,bytes,item_id,creator_id)) WITHOUT ROWID;")?;
    let tx = c.transaction()?;
    tx.execute("DELETE FROM files", [])?;
    let mut statement = tx.prepare("SELECT id,data_json FROM items ORDER BY id")?;
    let mut rows = statement.query([])?;
    let mut indexed = 0;
    let mut item_count = 0;
    while let Some(row) = rows.next()? {
        let id: String = row.get(0)?;
        let data: Value = serde_json::from_str(&row.get::<_, String>(1)?)?;
        let creator = data["creatorId"]
            .as_str()
            .map(String::from)
            .or_else(|| data["creatorId"].as_u64().map(|v| v.to_string()))
            .context("Item lost its creator identity")?;
        if let Some(attachments) = data["attachments"].as_array() {
            ensure!(
                attachments.len() <= 10000,
                "WCIF item attachment inventory is too large"
            );
            for attachment in attachments {
                let Some(filename) = attachment["file_name"].as_str() else {
                    continue;
                };
                if !filename.to_lowercase().ends_with(".package")
                    || filename.contains(['/', '\\'])
                    || filename.chars().any(char::is_control)
                    || filename.len() > 1024
                {
                    continue;
                }
                let Some(bytes) = attachment["size_bytes"]
                    .as_u64()
                    .and_then(|n| i64::try_from(n).ok())
                else {
                    continue;
                };
                indexed += tx.execute(
                    "INSERT OR IGNORE INTO files VALUES(?,?,?,?,?)",
                    params![filename.to_lowercase(), bytes, id, creator, filename],
                )?;
            }
        }
        item_count += 1;
    }
    drop(rows);
    drop(statement);
    tx.execute(
        "INSERT OR REPLACE INTO import_meta VALUES('files_indexed','true')",
        [],
    )?;
    tx.commit()?;
    Ok(
        json!({"ok":true,"archive_coverage_complete":coverage_complete,"source_gaps":receipt["incomplete"],"items_examined":item_count,"package_attachments_indexed":indexed,"source_objects_modified":false,"files_downloaded":false,"service_installed":false}),
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn full_item_request_includes_locked_and_all_styles_without_downloading_files() {
        let q = item_request("14342", 1);
        assert_eq!(q["isLocked"], true);
        assert_eq!(q["isFree"], true);
        assert_eq!(q["resultsPerPage"], 100);
        assert_eq!(q["stylesFilter"], json!([]));
        assert_eq!(q["keepSimfileshare"], true);
    }
    #[test]
    fn ids_accept_both_published_types_but_not_missing_or_controls() {
        assert_eq!(identity(&json!({"id":14342})).unwrap(), "14342");
        assert_eq!(identity(&json!({"id":"cc_hello"})).unwrap(), "cc_hello");
        assert!(identity(&json!({"id":"bad\n"})).is_err());
        assert!(identity(&json!({})).is_err());
    }
}
