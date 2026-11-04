//! Existing package locations, materialized by an explicit indexing job only.
use crate::text::{creator_key, deletions, one_typo};
use anyhow::{Result, ensure};
use rusqlite::{Connection, params};
use std::collections::BTreeSet;

pub fn relative(path: &str) -> String {
    let path = path.replace('\\', "/");
    let pieces: Vec<_> = path.split('/').collect();
    let start = pieces
        .iter()
        .rposition(|p| p.eq_ignore_ascii_case("Mods"))
        .map(|i| i + 1)
        .unwrap_or(0);
    pieces[start..pieces.len().saturating_sub(1)].join("/")
}
pub fn normalize(value: &str) -> String {
    value.replace('\\', "/").trim_matches('/').to_lowercase()
}
pub fn create(connection: &Connection) -> Result<()> {
    connection.execute_batch("CREATE TABLE IF NOT EXISTS folders(path TEXT PRIMARY KEY,display TEXT NOT NULL,leaf TEXT NOT NULL,leaf_key TEXT NOT NULL) WITHOUT ROWID;
      CREATE INDEX IF NOT EXISTS folders_leaf ON folders(leaf,path);
      CREATE TABLE IF NOT EXISTS folder_spelling(deleted TEXT,leaf_key TEXT,path TEXT,PRIMARY KEY(deleted,leaf_key,path)) WITHOUT ROWID;
      DELETE FROM folders;DELETE FROM folder_spelling;")?;
    Ok(())
}
pub fn insert(connection: &Connection, display: &str) -> Result<()> {
    let parts: Vec<_> = display.split('/').filter(|p| !p.is_empty()).collect();
    for at in 0..parts.len() {
        let display = parts[..=at].join("/");
        let path = normalize(&display);
        let leaf = parts[at].to_lowercase();
        let key = creator_key(&leaf);
        let inserted = connection.execute(
            "INSERT OR IGNORE INTO folders VALUES(?,?,?,?)",
            params![path, display, leaf, key],
        )?;
        if inserted != 0 && (3..=64).contains(&key.chars().count()) {
            for deleted in deletions(&key) {
                connection.execute(
                    "INSERT OR IGNORE INTO folder_spelling VALUES(?,?,?)",
                    params![deleted, key, path],
                )?;
            }
        }
    }
    Ok(())
}
#[derive(Default, Debug)]
pub struct Matches {
    pub paths: Vec<String>,
    pub suggestions: Vec<String>,
    pub corrected: bool,
}
pub fn resolve(connection: &Connection, value: &str, fuzzy: bool) -> Result<Matches> {
    if value.is_empty() {
        return Ok(Matches::default());
    }
    let value = normalize(value);
    ensure!(value.chars().count() <= 512, "Folder filter is too long");
    let mut result = Matches::default();
    // Full relative paths and leaf-name prefixes use indexed range lookups.
    // A literal %/_ is a folder character, never an implicit wildcard.
    let ceiling = format!("{value}\u{10ffff}");
    for prefix in [false, true] {
        let sql = if prefix {
            "SELECT path,display FROM folders WHERE (path>=?1 AND path<?2) OR (leaf>=?1 AND leaf<?2) ORDER BY length(path),path LIMIT 257"
        } else {
            "SELECT path,display FROM folders WHERE path=?1 OR leaf=?1 ORDER BY length(path),path LIMIT 257"
        };
        let mut statement = connection.prepare_cached(sql)?;
        let mut rows = if prefix {
            statement.query(params![value, ceiling])?
        } else {
            statement.query([&value])?
        };
        while let Some(row) = rows.next()? {
            result.paths.push(row.get(0)?);
            result.suggestions.push(row.get(1)?);
        }
        if !result.paths.is_empty() {
            break;
        }
    }
    ensure!(
        result.paths.len() <= 256,
        "Folder prefix is too broad; type more of its name"
    );
    if result.paths.is_empty() && fuzzy {
        let key = creator_key(value.rsplit('/').next().unwrap_or(&value));
        let mut candidates = BTreeSet::new();
        let mut statement = connection.prepare_cached(
            "SELECT leaf_key,path FROM folder_spelling WHERE deleted=? LIMIT 1025",
        )?;
        for deleted in deletions(&key) {
            for row in statement.query_map([deleted], |r| {
                Ok((r.get::<_, String>(0)?, r.get::<_, String>(1)?))
            })? {
                let (leaf, path) = row?;
                if one_typo(&key, &leaf)
                    && (!value.contains('/')
                        || path.rsplit_once('/').map(|p| p.0)
                            == value.rsplit_once('/').map(|p| p.0))
                {
                    candidates.insert(path);
                }
                ensure!(
                    candidates.len() <= 256,
                    "Folder spelling has too many candidates"
                );
            }
        }
        for path in candidates {
            let display =
                connection.query_row("SELECT display FROM folders WHERE path=?", [&path], |r| {
                    r.get(0)
                })?;
            result.paths.push(path);
            result.suggestions.push(display);
        }
        result.corrected = !result.paths.is_empty();
    }
    result.suggestions.truncate(8);
    Ok(result)
}
