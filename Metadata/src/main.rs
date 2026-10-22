use anyhow::{Context, Result, ensure};
use apex_catalog::{
    catalog::{Catalog, Query},
    enrich, identity,
};
use clap::{Parser, Subcommand};
use serde_json::{Value, json};
use std::path::PathBuf;

#[derive(Parser)]
#[command(
    about = "Explicit one-off metadata jobs and local catalogue queries. No watcher, daemon, telemetry or file renaming."
)]
struct Args {
    #[command(subcommand)]
    command: Command,
}
#[derive(Subcommand)]
enum Command {
    /// Prepare small swatch-family lookup tables once, without scanning packages.
    Optimize {
        #[arg(long)]
        index: PathBuf,
        #[arg(long)]
        expected_sha256: String,
        #[arg(long)]
        output: PathBuf,
    },
    /// Index a complete compact Sim/household equipped-reference capture, then exit.
    UsageImport {
        #[arg(long)]
        index: PathBuf,
        #[arg(long)]
        expected_sha256: String,
        #[arg(long)]
        capture: PathBuf,
        #[arg(long)]
        output: PathBuf,
        #[arg(long, requires = "previous_sha256")]
        previous: Option<PathBuf>,
        #[arg(long, requires = "previous")]
        previous_sha256: Option<String>,
        #[arg(long)]
        publish_config: Option<PathBuf>,
        #[arg(long, requires = "publish_config")]
        previous_config_sha256: Option<String>,
    },
    /// Explicit full WCIF creator/item metadata import; re-run the same path to resume.
    WcifImport {
        #[arg(long)]
        output: PathBuf,
        #[arg(long, default_value_t = 2)]
        workers: usize,
    },
    /// Index package filenames/sizes from imported item attachments, without downloading them.
    WcifIndex {
        #[arg(long)]
        database: PathBuf,
    },
    /// Materialize all discovered provider/social links with their original provenance.
    SourceIndex {
        #[arg(long)]
        database: PathBuf,
    },
    /// Explicit bounded direct-provider metadata reads. No login, file download or watcher.
    SourceRefresh {
        #[arg(long)]
        database: PathBuf,
        #[arg(long)]
        provider: String,
        #[arg(long, default_value_t = 20)]
        limit: usize,
    },
    /// Read packages and provider caches once, write a new immutable metadata snapshot, then exit.
    Sync {
        #[arg(long)]
        index: PathBuf,
        #[arg(long)]
        expected_sha256: String,
        #[arg(long)]
        output: PathBuf,
        #[arg(long)]
        cache: PathBuf,
        #[arg(long)]
        s4mm: Vec<PathBuf>,
        #[arg(long)]
        import: Vec<PathBuf>,
        #[arg(long)]
        creators: Vec<PathBuf>,
        /// Complete local WCIF creator/item archive(s), opened read-only.
        #[arg(long)]
        wcif_database: Vec<PathBuf>,
        /// Explicit opt-in to downloading the public GameTimeDev creator directory.
        #[arg(long)]
        public_creators: bool,
        /// Explicit opt-in to the public WCIF creator directory (no account/session).
        #[arg(long)]
        wcif_creators: bool,
        /// Optional name of an environment variable containing YOUR CurseForge API key.
        #[arg(long)]
        curseforge_key_env: Option<String>,
        #[arg(long, default_value_t = 2)]
        workers: usize,
        /// Publish only the catalogue path/digest to this explicit native-DLL config file.
        #[arg(long)]
        publish_config: Option<PathBuf>,
        /// Required digest of an existing config when explicitly replacing it.
        #[arg(long)]
        previous_config_sha256: Option<String>,
    },
    /// Read the same offline index used by the game DLL. Does not scan source packages.
    Query {
        #[arg(long)]
        index: PathBuf,
        #[arg(long)]
        expected_sha256: String,
        #[arg(long)]
        request: PathBuf,
        #[arg(long, requires_all=["usage_sha256","save_guid"])]
        usage: Option<PathBuf>,
        #[arg(long, requires = "usage")]
        usage_sha256: Option<String>,
        #[arg(long, requires = "usage")]
        save_guid: Option<String>,
    },
    /// One-off package identity probe; never modifies the source.
    Fingerprint { path: PathBuf },
}
fn write_config(path: &std::path::Path, value: &Value, previous: Option<&str>) -> Result<()> {
    use std::io::Write;
    if path.exists() {
        ensure!(
            previous
                .is_some_and(|sha| identity::file_sha256(path).is_ok_and(|actual| actual == sha)),
            "Existing config differs; supply its current --previous-config-sha256"
        );
    } else {
        ensure!(previous.is_none(), "Expected previous config is missing");
    }
    let parent = path.parent().context("Output needs a parent")?;
    std::fs::create_dir_all(parent)?;
    let mut temp = tempfile::NamedTempFile::new_in(parent)?;
    temp.write_all(&serde_json::to_vec_pretty(value)?)?;
    temp.as_file().sync_all()?;
    if let Some(sha) = previous {
        ensure!(
            identity::file_sha256(path)? == sha,
            "Config changed while the job was running"
        );
        temp.persist(path).map_err(|e| e.error)?;
    } else {
        temp.persist_noclobber(path).map_err(|e| e.error)?;
    }
    Ok(())
}
fn run() -> Result<Value> {
    match Args::parse().command {
        Command::Optimize {
            index,
            expected_sha256,
            output,
        } => apex_catalog::optimize::run(&index, &expected_sha256, &output),
        Command::UsageImport {
            index,
            expected_sha256,
            capture,
            output,
            previous,
            previous_sha256,
            publish_config,
            previous_config_sha256,
        } => {
            if let Some(config) = &publish_config {
                ensure!(
                    config != &index
                        && config != &capture
                        && config != &output
                        && previous.as_ref() != Some(config),
                    "Config cannot replace source metadata or usage inputs"
                );
                ensure!(
                    !config.exists()
                        || previous_config_sha256
                            .as_ref()
                            .is_some_and(|s| identity::file_sha256(config).is_ok_and(|v| v == *s)),
                    "Config changed; use its exact previous digest"
                );
            }
            let result = apex_catalog::usage::import(
                &index,
                &expected_sha256,
                &capture,
                &output,
                previous.as_deref().zip(previous_sha256.as_deref()),
            )?;
            if let Some(config) = publish_config {
                write_config(
                    &config,
                    &json!({"schema":1,"index":index.canonicalize()?,"index_sha256":expected_sha256,
                    "network_at_runtime":false,"equipped":{"index":output.canonicalize()?,"index_sha256":result["index_sha256"],
                    "save_guid":result["snapshot"]["save_guid"]}}),
                    previous_config_sha256.as_deref(),
                )?;
            }
            Ok(result)
        }
        Command::WcifImport { output, workers } => apex_catalog::wcif::run(&output, workers),
        Command::WcifIndex { database } => apex_catalog::wcif::index_files(&database),
        Command::SourceIndex { database } => apex_catalog::sources::index(&database),
        Command::SourceRefresh {
            database,
            provider,
            limit,
        } => apex_catalog::sources::refresh(&database, &provider, limit),
        Command::Fingerprint { path } => Ok(serde_json::to_value(identity::file_identity(&path)?)?),
        Command::Query {
            index,
            expected_sha256,
            request,
            usage,
            usage_sha256,
            save_guid,
        } => {
            ensure!(request.metadata()?.len() <= 2048, "Query file is too large");
            let query: Query = serde_json::from_reader(std::fs::File::open(request)?)?;
            let mut c = Catalog::open(&index, &expected_sha256)?;
            if let Some(path) = usage {
                c = c.with_usage(
                    &path,
                    usage_sha256.as_deref().context("Usage digest required")?,
                    save_guid.as_deref().context("Save GUID required")?,
                )?;
            }
            c.query(&query)
        }
        Command::Sync {
            index,
            expected_sha256,
            output,
            cache,
            s4mm,
            import,
            creators,
            wcif_database,
            public_creators,
            wcif_creators,
            curseforge_key_env,
            workers,
            publish_config,
            previous_config_sha256,
        } => {
            if let Some(path) = &publish_config {
                if path.exists() {
                    ensure!(previous_config_sha256.as_ref().is_some_and(|sha|identity::file_sha256(path).is_ok_and(|v|v==*sha)),"Existing config needs its exact previous digest");
                }
                ensure!(
                    path != &index && path != &output && path != &cache,
                    "Config cannot replace catalogue or cache"
                );
            }
            let key = curseforge_key_env
                .map(|name| {
                    std::env::var(name).context(
                        "The configured CurseForge API-key environment variable is unavailable",
                    )
                })
                .transpose()?;
            eprintln!(
                "{}",
                json!({"event":"metadata-job-started","network_opt_in":public_creators||wcif_creators||key.is_some(),"service_installed":false,"workers":workers})
            );
            let result = enrich::run(enrich::Options {
                index: &index,
                expected_sha256: &expected_sha256,
                output: &output,
                cache: &cache,
                s4mm: &s4mm,
                imports: &import,
                creator_imports: &creators,
                wcif_databases: &wcif_database,
                online_creators: public_creators,
                wcif_creators,
                curseforge_key: key.as_deref(),
                workers,
            })?;
            if let Some(path) = publish_config {
                write_config(
                    &path,
                    &json!({"schema":1,"index":output.canonicalize()?,"index_sha256":result["index_sha256"],"network_at_runtime":false}),
                    previous_config_sha256.as_deref(),
                )?;
            }
            Ok(result)
        }
    }
}
fn main() {
    match run() {
        Ok(value) => {
            println!("{}", value);
            if value.get("ok") == Some(&Value::Bool(false)) {
                std::process::exit(2);
            }
        }
        Err(error) => {
            // Never print configured headers, credentials or request bodies.
            eprintln!(
                "{}",
                json!({"ok":false,"error":error.to_string(),"job_complete":true,"service_installed":false})
            );
            std::process::exit(1);
        }
    }
}
