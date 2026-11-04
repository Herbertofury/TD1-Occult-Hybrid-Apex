//! Small, bounded catalogue language. Tokens never become SQL or filesystem operations.
use crate::catalog::Query;
use anyhow::{Result, bail, ensure};

#[derive(Default, Debug)]
pub struct Terms {
    pub include: Vec<String>,
    pub exclude: Vec<String>,
    pub package: String,
    pub name: String,
    pub code: String,
    pub usage: crate::usage::Filter,
}

pub fn parse(input: &Query) -> Result<(Query, Terms)> {
    let mut query = input.clone();
    let mut terms = Terms::default();
    let mut tokens = Vec::new();
    let mut token = String::new();
    let mut quoted = false;
    for c in input.text.chars() {
        if c == '"' {
            quoted = !quoted;
            token.push(c);
        } else if c.is_whitespace() && !quoted {
            if !token.is_empty() {
                tokens.push(std::mem::take(&mut token));
            }
        } else {
            token.push(c);
        }
    }
    ensure!(!quoted, "Close the quoted search value");
    if !token.is_empty() {
        tokens.push(token);
    }
    ensure!(tokens.len() <= 24, "Use at most twenty-four search tokens");
    for token in tokens {
        let (field, value) = token.split_once(':').unwrap_or(("", &token));
        let value = value.trim_matches('"');
        ensure!(!value.is_empty(), "A search filter needs a value");
        match field.to_ascii_lowercase().as_str() {
            "folder" => query.folder = value.into(),
            "author" | "creator" => query.author = value.into(),
            "package" | "file" => terms.package = value.into(),
            "name" => terms.name = value.into(),
            "code" => terms.code = value.into(),
            "sim" => terms.usage.sim = value.into(),
            "household" => terms.usage.household = value.into(),
            "sim-id" => terms.usage.sim_id = value.into(),
            "household-id" => terms.usage.household_id = value.into(),
            "form" => terms.usage.form = value.into(),
            "outfit" => terms.usage.outfit = value.into(),
            "type" => {
                query.body_type = Some(
                    value
                        .parse()
                        .map_err(|_| anyhow::anyhow!("type: needs a numeric CAS body type"))?,
                )
            }
            "origin" => {
                query.origin = Some(
                    match value.to_ascii_lowercase().as_str() {
                        "cc" | "mod" => "mod",
                        "ea" => "ea",
                        _ => bail!("origin: accepts cc or ea"),
                    }
                    .into(),
                )
            }
            "added" => {
                let days = value
                    .strip_suffix('d')
                    .unwrap_or(value)
                    .parse::<u32>()
                    .map_err(|_| anyhow::anyhow!("Use added:7d or added:30d"))?;
                ensure!((1..=36500).contains(&days), "added: accepts 1..36500 days");
                query.added_days = Some(days);
            }
            "sort" => query.sort = value.into(),
            "" => {
                if token.starts_with('-') && token.len() > 1 {
                    terms.exclude.push(token[1..].trim_matches('"').into());
                } else {
                    terms.include.push(token.trim_matches('"').into());
                }
            }
            _ => bail!("Unknown search filter: {field}"),
        }
    }
    query.text = terms.include.join(" ");
    terms.usage.validate()?;
    // Equipped-content searches default to CC; origin:ea remains explicit.
    if terms.usage.active() && query.origin.is_none() {
        query.origin = Some("mod".into());
    }
    query.validate()?;
    Ok((query, terms))
}

/// Shell-style * and ? in a parameterized SQLite LIKE expression. Without
/// wildcards, names match anywhere; folder prefixes are handled separately.
pub fn pattern(value: &str) -> String {
    let mut result = String::new();
    let wild = value.contains(['*', '?']);
    if !wild {
        result.push('%');
    }
    for c in value.chars() {
        match c {
            '*' => result.push('%'),
            '?' => result.push('_'),
            '%' | '_' | '\\' => {
                result.push('\\');
                result.push(c);
            }
            _ => result.push(c),
        }
    }
    if !wild {
        result.push('%');
    }
    result
}
