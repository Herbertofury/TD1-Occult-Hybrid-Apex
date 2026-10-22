use crate::{
    identity::file_sha256,
    providers::{self, readonly},
    text::{deletions, one_typo, words},
};
use anyhow::{Context, Result, ensure};
use rusqlite::{Connection, params_from_iter, types::Value as Sql};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::{
    collections::BTreeSet,
    path::{Path, PathBuf},
    time::{Instant, SystemTime, UNIX_EPOCH},
};

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Query {
    pub text: String,
    pub body_type: Option<u32>,
    pub origin: Option<String>,
    pub name_mode: String,
    pub offset: u32,
    pub limit: u32,
    pub view: String,
    #[serde(default)]
    pub author: String,
    #[serde(default = "name_sort")]
    pub sort: String,
    #[serde(default)]
    pub grouped: bool,
    #[serde(default)]
    pub fuzzy: bool,
    #[serde(default)]
    pub folder: String,
    #[serde(default)]
    pub added_days: Option<u32>,
}
fn name_sort() -> String {
    "name".into()
}
impl Query {
    pub fn validate(&self) -> Result<()> {
        ensure!(
            self.text.chars().count() <= 200 && !self.text.chars().any(char::is_control),
            "Search text exceeds its printable bound"
        );
        ensure!(
            self.author.chars().count() <= 80 && !self.author.chars().any(char::is_control),
            "Author filter exceeds its bound"
        );
        ensure!(
            self.folder.chars().count() <= 512 && !self.folder.chars().any(char::is_control),
            "Folder filter exceeds its printable bound"
        );
        ensure!(
            self.added_days
                .is_none_or(|days| (1..=36500).contains(&days)),
            "Recently added days exceed their bound"
        );
        ensure!(
            self.origin
                .as_deref()
                .is_none_or(|v| matches!(v, "mod" | "ea")),
            "Unknown origin filter"
        );
        ensure!(
            matches!(self.name_mode.as_str(), "preferred" | "package" | "code"),
            "Unknown name presentation"
        );
        ensure!(
            matches!(
                self.sort.as_str(),
                "name" | "package" | "creator" | "id" | "newest" | "modified"
            ),
            "Unknown catalogue ordering"
        );
        ensure!(
            self.view == "all",
            "Native offline favorites/recent are filtered in the native eligible UI feed"
        );
        ensure!(
            self.limit >= 1 && self.limit <= 240 && self.offset <= 2_000_000,
            "Invalid bounded query page"
        );
        ensure!(
            words(&self.text).len() <= 16,
            "Use at most sixteen search terms"
        );
        Ok(())
    }
}

pub struct Catalog {
    connection: Connection,
    sha256: String,
    snapshot: Value,
    version: i64,
    categories: Value,
    path: PathBuf,
    length: u64,
    modified: SystemTime,
    usage: Option<crate::usage::Pin>,
    fast_families: bool,
}
impl Catalog {
    pub fn open(path: &Path, expected: &str) -> Result<Self> {
        ensure!(
            providers::hash(expected),
            "A pinned catalogue SHA-256 is required"
        );
        let before = path.metadata()?;
        ensure!(
            file_sha256(path)? == expected,
            "Offline catalogue differs from its pinned digest"
        );
        let connection = readonly(path)?;
        let version: i64 = connection.query_row("PRAGMA user_version", [], |r| r.get(0))?;
        ensure!(
            (3..=7).contains(&version),
            "Unsupported offline catalogue schema"
        );
        let snapshot = serde_json::from_str(&connection.query_row::<String, _, _>(
            "SELECT value FROM snapshot",
            [],
            |r| r.get(0),
        )?)?;
        let categories: Vec<Value> = connection
            .prepare("SELECT body_type,count(*) FROM parts GROUP BY body_type ORDER BY body_type")?
            .query_map([], |r| {
                Ok(json!({"body_type":r.get::<_,Option<u32>>(0)?,"count":r.get::<_,i64>(1)?}))
            })?
            .collect::<rusqlite::Result<_>>()?;
        ensure!(
            categories.len() <= 4096,
            "Catalogue category inventory exceeds its bound"
        );
        let after = path.metadata()?;
        let fast_families: bool=connection.query_row("SELECT EXISTS(SELECT 1 FROM sqlite_master WHERE type='table' AND name='catalog_families')",[],|r|r.get(0))?;
        ensure!(
            before.len() == after.len() && before.modified()? == after.modified()?,
            "Offline catalogue changed during opening"
        );
        Ok(Self {
            connection,
            sha256: expected.into(),
            snapshot,
            version,
            categories: json!(categories),
            path: path.into(),
            length: after.len(),
            modified: after.modified()?,
            usage: None,
            fast_families,
        })
    }
    pub fn with_usage(mut self, path: &Path, sha: &str, save: &str) -> Result<Self> {
        ensure!(self.usage.is_none(), "Equipped snapshot is already bound");
        self.usage = Some(crate::usage::attach(
            &self.connection,
            path,
            sha,
            &self.sha256,
            save,
        )?);
        Ok(self)
    }
    fn filtered(
        &self,
        query: &Query,
        terms: &crate::search::Terms,
        folders: &crate::folders::Matches,
        expression: Option<&str>,
    ) -> Result<(String, Vec<Sql>)> {
        let mut clauses = Vec::new();
        let mut parameters = Vec::new();
        if terms.usage.active() {
            let pin = self.usage.as_ref().context(
                "Refresh equipped references for this save before using sim: or household:",
            )?;
            pin.check()?;
            let (selection, args) = crate::usage::selection(&terms.usage)?;
            clauses.push(format!("part_id IN ({selection})"));
            parameters.extend(args);
        }
        if let Some(text) = expression {
            clauses.push("rowid IN (SELECT rowid FROM names WHERE names MATCH ?)".to_owned());
            parameters.push(Sql::Text(text.into()));
        }
        if let Some(body) = query.body_type {
            clauses.push("body_type=?".into());
            parameters.push(Sql::Integer(body.into()));
        }
        if let Some(origin) = &query.origin {
            clauses.push("origin=?".into());
            parameters.push(Sql::Text(origin.clone()));
        }
        if !query.author.is_empty() {
            clauses.push(
                if self.version >= 6 {
                    "creator_key=?"
                } else {
                    "json_extract(row_json,'$.creator_hint')=? COLLATE NOCASE"
                }
                .into(),
            );
            parameters.push(Sql::Text(if self.version >= 6 {
                crate::text::creator_key(&query.author)
            } else {
                query.author.clone()
            }));
        }
        if !query.folder.is_empty() {
            ensure!(
                self.version >= 7,
                "Refresh the catalogue once to index existing folders"
            );
            let mut choices = Vec::new();
            for path in &folders.paths {
                choices.push("(folder_key=? OR (folder_key>=? AND folder_key<?))");
                parameters.extend([
                    Sql::Text(path.clone()),
                    Sql::Text(format!("{path}/")),
                    Sql::Text(format!("{path}/\u{10ffff}")),
                ]);
            }
            clauses.push(if choices.is_empty() {
                "0".into()
            } else {
                format!("({})", choices.join(" OR "))
            });
        }
        if let Some(days) = query.added_days {
            ensure!(
                self.version >= 7,
                "Refresh the catalogue once to record added dates"
            );
            clauses.push("origin='mod' AND baseline=0 AND first_seen>=?".into());
            let now = SystemTime::now().duration_since(UNIX_EPOCH)?.as_secs() as i64;
            parameters.push(Sql::Integer(now - i64::from(days) * 86400));
        }
        for (field, value) in [
            ("package_name", &terms.package),
            ("preferred_name", &terms.name),
            ("code_name", &terms.code),
        ] {
            if !value.is_empty() {
                clauses.push(format!(
                    "json_extract(row_json,'$.{field}') LIKE ? ESCAPE '\\'"
                ));
                parameters.push(Sql::Text(crate::search::pattern(value)));
            }
        }
        for excluded in &terms.exclude {
            let tokens = words(excluded);
            if tokens.is_empty() {
                continue;
            }
            clauses.push("rowid NOT IN (SELECT rowid FROM names WHERE names MATCH ?)".into());
            parameters.push(Sql::Text(
                tokens
                    .iter()
                    .map(|s| format!("\"{s}\"*"))
                    .collect::<Vec<_>>()
                    .join(" AND "),
            ));
        }
        Ok((
            if clauses.is_empty() {
                String::new()
            } else {
                format!(" WHERE {}", clauses.join(" AND "))
            },
            parameters,
        ))
    }
    fn count(
        &self,
        query: &Query,
        terms: &crate::search::Terms,
        folders: &crate::folders::Matches,
        expression: Option<&str>,
    ) -> Result<u32> {
        let (filter, parameters) = self.filtered(query, terms, folders, expression)?;
        let column = if query.grouped {
            "DISTINCT family_id"
        } else {
            "*"
        };
        Ok(self.connection.query_row(
            &format!("SELECT count({column}) FROM parts{filter}"),
            params_from_iter(parameters),
            |r| r.get(0),
        )?)
    }
    fn fuzzy(&self, tokens: &[String]) -> Result<(String, Vec<Value>)> {
        let mut plan = Vec::new();
        let mut corrections = Vec::new();
        for token in tokens {
            let prefix = format!("\"{}\"*", token.replace('"', "\"\""));
            let present: i64 = self.connection.query_row(
                "SELECT EXISTS(SELECT rowid FROM names WHERE names MATCH ? LIMIT 1)",
                [&prefix],
                |r| r.get(0),
            )?;
            if present != 0 || token.chars().count() < 3 || self.version < 6 {
                plan.push(prefix);
                continue;
            }
            let mut candidates = BTreeSet::new();
            let mut statement = self
                .connection
                .prepare_cached("SELECT term FROM spelling WHERE deleted=? LIMIT 1025")?;
            for deleted in deletions(token) {
                for row in statement.query_map([deleted], |r| r.get::<_, String>(0))? {
                    let word = row?;
                    if one_typo(token, &word) {
                        candidates.insert(word);
                    }
                    ensure!(
                        candidates.len() <= 1024,
                        "Fuzzy result exceeds its candidate bound"
                    );
                }
            }
            let candidates: Vec<_> = candidates.into_iter().take(32).collect();
            if candidates.is_empty() {
                plan.push(prefix);
            } else {
                plan.push(format!(
                    "({})",
                    candidates
                        .iter()
                        .map(|s| format!("\"{}\"*", s.replace('"', "\"\"")))
                        .collect::<Vec<_>>()
                        .join(" OR ")
                ));
                corrections.push(json!({"from":token,"to":candidates}));
            }
        }
        Ok((plan.join(" AND "), corrections))
    }
    pub fn query(&self, query: &Query) -> Result<Value> {
        query.validate()?;
        let started = Instant::now();
        let current = self.path.metadata()?;
        ensure!(
            current.len() == self.length && current.modified()? == self.modified,
            "Offline catalogue changed; explicitly reload its pinned snapshot"
        );
        let original = query;
        let (effective, terms) = crate::search::parse(query)?;
        let query = &effective;
        let fast = self.fast_families
            && query.grouped
            && query.text.is_empty()
            && query.author.is_empty()
            && query.folder.is_empty()
            && query.added_days.is_none()
            && !terms.usage.active()
            && terms.exclude.is_empty()
            && terms.package.is_empty()
            && terms.name.is_empty()
            && terms.code.is_empty();
        let folders = if self.version >= 7 {
            crate::folders::resolve(&self.connection, &query.folder, query.fuzzy)?
        } else {
            crate::folders::Matches::default()
        };
        let tokens = words(&query.text);
        let mut expression = (!tokens.is_empty()).then(|| {
            terms
                .include
                .iter()
                .map(|s| format!("\"{}\"*", words(s).join(" ")))
                .collect::<Vec<_>>()
                .join(" AND ")
        });
        let mut total = if fast {
            let (filter, args) = self.filtered(query, &terms, &folders, None)?;
            self.connection.query_row(
                &format!("SELECT count(*) FROM catalog_families{filter}"),
                params_from_iter(args),
                |r| r.get(0),
            )?
        } else {
            self.count(query, &terms, &folders, expression.as_deref())?
        };
        let mut corrections = Vec::new();
        if total == 0 && query.fuzzy && !tokens.is_empty() {
            let (fuzzy, changes) = self.fuzzy(&tokens)?;
            if !changes.is_empty() {
                expression = Some(fuzzy);
                total = self.count(query, &terms, &folders, expression.as_deref())?;
                corrections = changes;
            }
        }
        ensure!(total <= 2_000_000, "Catalogue exceeds its row bound");
        let (filter, mut parameters) =
            self.filtered(query, &terms, &folders, expression.as_deref())?;
        let mut base = if query.grouped {
            format!(
                "SELECT row_json FROM parts WHERE part_id IN (SELECT min(part_id) FROM parts{filter} GROUP BY family_id)"
            )
        } else {
            format!("SELECT row_json FROM parts{filter}")
        };
        let order = match query.sort.as_str() {
            "newest" if self.version >= 7 => "first_seen DESC,part_id",
            "modified" if self.version >= 7 => "modified DESC,part_id",
            "id" => "part_id",
            "package" => "json_extract(row_json,'$.package_name') COLLATE NOCASE,part_id",
            "creator" if self.version >= 6 => "creator COLLATE NOCASE,title COLLATE NOCASE,part_id",
            "creator" => "json_extract(row_json,'$.creator_hint') COLLATE NOCASE,part_id",
            _ if self.version >= 6 => "title COLLATE NOCASE,part_id",
            _ => "json_extract(row_json,'$.preferred_name') COLLATE NOCASE,part_id",
        };
        if fast {
            let fast_order =
                order.replace("json_extract(row_json,'$.package_name')", "package_name");
            base = format!(
                "SELECT row_json FROM parts WHERE part_id IN (SELECT part_id FROM catalog_families{filter} ORDER BY {fast_order} LIMIT ? OFFSET ?)"
            );
        }
        parameters.push(Sql::Integer(query.limit.into()));
        parameters.push(Sql::Integer(query.offset.into()));
        let mut statement = self.connection.prepare(&format!(
            "{base} ORDER BY {order}{}",
            if fast { "" } else { " LIMIT ? OFFSET ?" }
        ))?;
        let mut items = Vec::new();
        for row in statement.query_map(params_from_iter(parameters), |r| r.get::<_, String>(0))? {
            let mut item: Value = serde_json::from_str(&row?)?;
            item.as_object_mut()
                .context("Invalid catalogue row")?
                .remove("package_path");
            let field = match query.name_mode.as_str() {
                "package" => "package_name",
                "code" => "code_name",
                _ => "preferred_name",
            };
            item["name"] = item[field].clone();
            item["favorite"] = json!(false);
            if terms.usage.active() {
                item["used_by"] = crate::usage::used_by(
                    &self.connection,
                    item["part_id"].as_str().context("Invalid item identity")?,
                    &terms.usage,
                )?;
            }
            items.push(item);
        }
        let next = query.offset + items.len() as u32;
        Ok(
            json!({"ok":true,"index_sha256":self.sha256,"query":original,"snapshot":self.snapshot,
            "grouped":query.grouped,"items":items,"categories":self.categories,"total":total,"offset":query.offset,
            "next_offset":if next<total{Some(next)}else{None},"search_mode":if corrections.is_empty(){"prefix"}else{"fuzzy"},
            "corrections":corrections,"folder_matches":folders.suggestions,"folder_corrected":folders.corrected,
            "added_clock":"first indexed content; initial baseline excluded from added: filters",
            "equipped_snapshot":if terms.usage.active(){self.usage.as_ref().map(|p|&p.snapshot)}else{None},
            "worker_elapsed_ms":started.elapsed().as_micros() as f64/1000.0,
            "network_contacted":false,"package_scan_performed":false,"service_required":false}),
        )
    }
}
