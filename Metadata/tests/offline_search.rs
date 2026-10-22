#![cfg(feature = "cli")]
use apex_catalog::{
    catalog::{Catalog, Query},
    enrich, folders,
    identity::{file_identity, file_sha256, fingerprint},
};
use rusqlite::{Connection, params};
use serde_json::{Value, json};
use std::{
    fs,
    path::{Path, PathBuf},
    time::{SystemTime, UNIX_EPOCH},
};

fn query(text: &str) -> Query {
    serde_json::from_value(json!({"text":text,"body_type":null,"origin":null,"name_mode":"preferred","offset":0,"limit":24,"view":"all","fuzzy":true})).unwrap()
}

#[test]
fn old_fts_schema_is_migrated_without_mutating_the_original_index() {
    let f = fixture();
    let root = f._temp.path();
    let input = root.join("legacy.sqlite");
    source(&input, &f.rows[..1], false);
    let legacy = Connection::open(&input).unwrap();
    legacy.execute_batch("DROP TABLE names;CREATE VIRTUAL TABLE names USING fts5(preferred_name,package_name,code_name);PRAGMA user_version=4;").unwrap();
    drop(legacy);
    let before = file_sha256(&input).unwrap();
    let output = root.join("upgraded.sqlite");
    let cache = root.join("cache.sqlite");
    let receipt = enrich::run(enrich::Options {
        index: &input,
        expected_sha256: &before,
        output: &output,
        cache: &cache,
        s4mm: &[],
        imports: &[],
        creator_imports: &[],
        wcif_databases: &[],
        online_creators: false,
        wcif_creators: false,
        curseforge_key: None,
        workers: 1,
    })
    .unwrap();
    let c = Catalog::open(&output, receipt["index_sha256"].as_str().unwrap()).unwrap();
    assert_eq!(c.query(&query("cherry folder:Makeup")).unwrap()["total"], 1);
    assert_eq!(file_sha256(&input).unwrap(), before);
}
fn row(at: usize, path: &Path, title: &str, origin: &str, body: u32) -> Value {
    let identity = file_identity(path).unwrap();
    json!({"part_id":format!("{at:064x}"),"resource_sha256":"b".repeat(64),"package_sha256":identity.sha256,
        "resource_tgi":format!("034AEECB:00000000:{at:016X}"),"body_type":body,"status":"indexed","origin":origin,
        "package_path":path.to_str().unwrap(),"package_name":path.file_name().unwrap().to_str().unwrap(),"preferred_name":title,"code_name":title.replace(' ',"_"),"creator_hint":"Magic Hand"})
}
fn source(path: &Path, rows: &[Value], v7: bool) {
    let c = Connection::open(path).unwrap();
    c.execute_batch("PRAGMA user_version=5;CREATE TABLE parts(part_id TEXT PRIMARY KEY,family_id TEXT,body_type INTEGER,origin TEXT,row_json TEXT);
      CREATE VIRTUAL TABLE names USING fts5(preferred_name,package_name,code_name,search_aliases);CREATE TABLE snapshot(value TEXT);").unwrap();
    c.execute(
        "INSERT INTO snapshot VALUES(?)",
        [json!({"parts":rows.len(),"complete":true}).to_string()],
    )
    .unwrap();
    if v7 {
        c.execute_batch("PRAGMA user_version=7;ALTER TABLE parts ADD COLUMN creator TEXT;ALTER TABLE parts ADD COLUMN title TEXT;ALTER TABLE parts ADD COLUMN package_sha256 TEXT;ALTER TABLE parts ADD COLUMN creator_key TEXT;ALTER TABLE parts ADD COLUMN folder_key TEXT;ALTER TABLE parts ADD COLUMN first_seen INTEGER;ALTER TABLE parts ADD COLUMN baseline INTEGER;ALTER TABLE parts ADD COLUMN modified INTEGER;").unwrap();
        folders::create(&c).unwrap();
    }
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs() as i64;
    for (i, row) in rows.iter().enumerate() {
        c.execute(
            "INSERT INTO parts(part_id,family_id,body_type,origin,row_json) VALUES(?,?,?,?,?)",
            params![
                row["part_id"].as_str(),
                row["part_id"].as_str(),
                row["body_type"].as_i64(),
                row["origin"].as_str(),
                row.to_string()
            ],
        )
        .unwrap();
        c.execute("INSERT INTO names(rowid,preferred_name,package_name,code_name,search_aliases) VALUES(?,?,?,?,?)",params![(i+1) as i64,row["preferred_name"].as_str(),row["package_name"].as_str(),row["code_name"].as_str(),"magic hand"]).unwrap();
        if v7 {
            let folder = folders::relative(row["package_path"].as_str().unwrap());
            folders::insert(&c, &folder).unwrap();
            c.execute("UPDATE parts SET creator='Magic Hand',title=?,creator_key='magichand',folder_key=?,first_seen=?,baseline=?,modified=? WHERE part_id=?",params![row["preferred_name"].as_str(),folders::normalize(&folder),now-i as i64*86400,i==1,now+i as i64,row["part_id"].as_str()]).unwrap();
        }
    }
    if v7 {
        c.execute_batch("CREATE VIRTUAL TABLE apex_vocab USING fts5vocab(names,'row');CREATE TABLE spelling(deleted TEXT,term TEXT,PRIMARY KEY(deleted,term)) WITHOUT ROWID;").unwrap();
        let terms: Vec<String> = c
            .prepare("SELECT term FROM apex_vocab")
            .unwrap()
            .query_map([], |r| r.get(0))
            .unwrap()
            .collect::<Result<_, _>>()
            .unwrap();
        for term in terms {
            for deleted in apex_catalog::text::deletions(&term) {
                c.execute(
                    "INSERT OR IGNORE INTO spelling VALUES(?,?)",
                    params![deleted, term],
                )
                .unwrap();
            }
        }
    }
}
struct Fixture {
    _temp: tempfile::TempDir,
    index: PathBuf,
    rows: Vec<Value>,
}
fn fixture() -> Fixture {
    let temp = tempfile::tempdir().unwrap();
    let mut rows = Vec::new();
    for (i, (folder, file, title, body)) in [
        ("Makeup/Lips", "Cherry.package", "Cherry Lipstick", 29),
        ("Makeup/Tattoos", "Ink.package", "Cherry Tattoo", 31),
        ("Makeup2", "Gloss.package", "Cherry Gloss", 29),
        ("Hair", "Bob.package", "Bob Hair", 2),
        ("头发", "Étoile.package", "Étoile Hair", 2),
    ]
    .iter()
    .enumerate()
    {
        let path = temp.path().join("Mods").join(folder).join(file);
        fs::create_dir_all(path.parent().unwrap()).unwrap();
        fs::write(&path, format!("package fixture {i}")).unwrap();
        rows.push(row(i + 1, &path, title, "mod", *body));
    }
    let index = temp.path().join("catalog.sqlite");
    source(&index, &rows, true);
    Fixture {
        _temp: temp,
        index,
        rows,
    }
}
fn run(f: &Fixture, text: &str) -> Value {
    Catalog::open(&f.index, &file_sha256(&f.index).unwrap())
        .unwrap()
        .query(&query(text))
        .unwrap()
}

fn usage_document(f: &Fixture) -> Value {
    let owner = |id: &str, form: &str, instance: &str, body: u32| {
        json!({"owner_id":id,"form":form,"outfits":[
        {"category":0,"ordinal":0,"outfit_id":"18446744073709551615","parts":[{"instance":instance,"body_type":body,"layer":null}]},
        {"category":0,"ordinal":1,"outfit_id":"22","parts":[{"instance":"1","body_type":29,"layer":2}]}]})
    };
    json!({"schema":1,"catalog_sha256":file_sha256(&f.index).unwrap(),"save_guid":"987",
        "captured_at":1000,"source":"native-cas-committed","source_epoch":"session-a","complete":true,"households":[
        {"household_id":"10","name":"Goth Family","members":[
            {"sim_id":"100","name":"Bella Goth","generation":12,"owners":[owner("native/2","Alien","2",31),owner("native/4","Vampire","4",2)]},
            {"sim_id":"101","name":"Mortimer Goth","generation":4,"owners":[owner("native/1","Human","1",29)]}]},
        {"household_id":"20","name":"Other Household","members":[
            {"sim_id":"200","name":"Bella Goth","generation":2,"owners":[owner("native/1","Human","5",2)]}]}]})
}
fn import_usage(
    f: &Fixture,
    value: &Value,
    name: &str,
    previous: Option<(&Path, &str)>,
) -> PathBuf {
    let root = f._temp.path();
    let raw = root.join(format!("{name}.json"));
    let output = root.join(format!("{name}.sqlite"));
    fs::write(&raw, serde_json::to_vec(value).unwrap()).unwrap();
    apex_catalog::usage::import(
        &f.index,
        &file_sha256(&f.index).unwrap(),
        &raw,
        &output,
        previous,
    )
    .unwrap();
    output
}
fn usage_catalog(f: &Fixture, usage: &Path) -> Catalog {
    Catalog::open(&f.index, &file_sha256(&f.index).unwrap())
        .unwrap()
        .with_usage(usage, &file_sha256(usage).unwrap(), "987")
        .unwrap()
}

#[test]
fn sim_household_form_and_outfit_filters_intersect_on_the_same_owner() {
    let f = fixture();
    let path = import_usage(&f, &usage_document(&f), "usage", None);
    let c = usage_catalog(&f, &path);
    let r = c
        .query(&query(
            "sim:\"Bella Goth\" household:Goth form:Alien outfit:everyday/1",
        ))
        .unwrap();
    assert_eq!(r["total"], 1);
    assert_eq!(r["items"][0]["name"], "Cherry Tattoo");
    assert_eq!(r["items"][0]["used_by"]["rows"][0]["sim_id"], "100");
    assert_eq!(r["items"][0]["used_by"]["rows"][0]["form"], "Alien");
    let r = c
        .query(&query("household:\"Goth Family\" outfit:everyday/2"))
        .unwrap();
    assert_eq!(r["total"], 1);
    assert_eq!(
        r["items"][0]["used_by"]["rows"].as_array().unwrap().len(),
        3
    );
    assert_eq!(
        c.query(&query("sim-id:200 household-id:10")).unwrap()["total"],
        0
    );
    assert_eq!(
        c.query(&query("sim:\"Bella Goth\" household-id:20 form:Vampire"))
            .unwrap()["total"],
        0
    );
    assert_eq!(
        c.query(&query("sim-id:100 form:Vampire outfit:0/1"))
            .unwrap()["items"][0]["name"],
        "Bob Hair"
    );
    assert_eq!(
        c.query(&query(
            "household:Goth author:\"Magic Hand\" folder:Makeup type:31"
        ))
        .unwrap()["total"],
        1
    );
    assert_eq!(r["package_scan_performed"], false);
}
#[test]
fn equipped_snapshots_require_exact_save_catalogue_and_an_explicit_refresh() {
    let f = fixture();
    let path = import_usage(&f, &usage_document(&f), "usage", None);
    assert!(
        Catalog::open(&f.index, &file_sha256(&f.index).unwrap())
            .unwrap()
            .query(&query("sim:Bella"))
            .is_err()
    );
    assert!(
        Catalog::open(&f.index, &file_sha256(&f.index).unwrap())
            .unwrap()
            .with_usage(&path, &file_sha256(&path).unwrap(), "988")
            .is_err()
    );
    let c = usage_catalog(&f, &path);
    fs::remove_dir_all(f._temp.path().join("Mods")).unwrap();
    assert_eq!(
        c.query(&query("sim-id:100 form:Alien outfit:0/1")).unwrap()["total"],
        1
    );
    let before = file_sha256(&path).unwrap();
    c.query(&query("household:Goth")).unwrap();
    assert_eq!(before, file_sha256(&path).unwrap());
    drop(c);
}

#[test]
fn native_empty_zero_outfits_are_retained_and_ambiguous_resource_instances_are_not_guessed() {
    let f = fixture();
    let mut d = usage_document(&f);
    d["households"][0]["members"][0]["owners"][0]["outfits"]
        .as_array_mut()
        .unwrap()
        .push(json!({"category":1,"ordinal":0,"outfit_id":"0","parts":[]}));
    let c = Connection::open(&f.index).unwrap();
    c.execute("INSERT INTO parts SELECT ?,family_id,body_type,origin,row_json,creator,title,package_sha256,creator_key,folder_key,first_seen,baseline,modified FROM parts WHERE part_id=?",
        params!["f".repeat(64),f.rows[0]["part_id"].as_str()]).unwrap();
    drop(c);
    d["catalog_sha256"] = json!(file_sha256(&f.index).unwrap());
    let path = import_usage(&f, &d, "ambiguous", None);
    let c = usage_catalog(&f, &path);
    let r = c
        .query(&query("household-id:10 outfit:everyday/2"))
        .unwrap();
    assert_eq!(r["total"], 0);
    assert_eq!(r["equipped_snapshot"]["ambiguous_unique"], 1);
    assert_eq!(
        c.query(&query("sim-id:100 form:Alien outfit:formal/1"))
            .unwrap()["total"],
        0
    );
}
#[test]
fn refresh_replaces_a_household_atomically_and_retains_other_households() {
    let f = fixture();
    let mut d = usage_document(&f);
    let path = import_usage(&f, &d, "first", None);
    let old_sha = file_sha256(&path).unwrap();
    d["captured_at"] = json!(2000);
    d["households"].as_array_mut().unwrap().truncate(1);
    d["households"][0]["name"] = json!("Renamed Family");
    d["households"][0]["members"]
        .as_array_mut()
        .unwrap()
        .truncate(1);
    d["households"][0]["members"][0]["name"] = json!("Étoile 新名");
    let fresh = import_usage(&f, &d, "second", Some((&path, &old_sha)));
    let c = usage_catalog(&f, &fresh);
    assert_eq!(c.query(&query("sim:Mortimer")).unwrap()["total"], 0);
    assert_eq!(
        c.query(&query("sim:Étoile household:Renamed")).unwrap()["total"],
        3
    );
    assert_eq!(c.query(&query("household-id:20")).unwrap()["total"], 2);
    assert_eq!(old_sha, file_sha256(&path).unwrap());
    // A stale actor cannot move back from a newer household, even if the old
    // household no longer has any members in the latest snapshot.
    let mut moved = d.clone();
    moved["captured_at"] = json!(3000);
    moved["households"][0]["household_id"] = json!("30");
    let third = import_usage(
        &f,
        &moved,
        "third",
        Some((&fresh, &file_sha256(&fresh).unwrap())),
    );
    let raw = f._temp.path().join("stale.json");
    fs::write(&raw, serde_json::to_vec(&d).unwrap()).unwrap();
    let failed = f._temp.path().join("must-not-publish.sqlite");
    assert!(
        apex_catalog::usage::import(
            &f.index,
            &file_sha256(&f.index).unwrap(),
            &raw,
            &failed,
            Some((&third, &file_sha256(&third).unwrap()))
        )
        .is_err()
    );
    assert!(!failed.exists());
}
#[test]
fn malformed_partial_or_ambiguous_usage_never_silently_selects_a_package() {
    let f = fixture();
    let mut d = usage_document(&f);
    d["complete"] = json!(false);
    let raw = f._temp.path().join("bad.json");
    let out = f._temp.path().join("bad.sqlite");
    fs::write(&raw, serde_json::to_vec(&d).unwrap()).unwrap();
    assert!(
        apex_catalog::usage::import(&f.index, &file_sha256(&f.index).unwrap(), &raw, &out, None)
            .is_err()
    );
    assert!(!out.exists());
    d["complete"] = json!(true);
    d["households"][0]["members"][0]["owners"][0]["outfits"][0]["parts"][0]["instance"] =
        json!("18446744073709551615");
    let path = import_usage(&f, &d, "missing", None);
    let r = usage_catalog(&f, &path)
        .query(&query("sim-id:100 form:Alien outfit:0/1"))
        .unwrap();
    assert_eq!(r["total"], 0);
    assert_eq!(r["equipped_snapshot"]["unresolved_unique"], 1);
    assert!(
        usage_catalog(&f, &path)
            .query(&query("outfit:everyday/0"))
            .is_err()
    );
    assert!(
        usage_catalog(&f, &path)
            .query(&query("sim-id:00100"))
            .is_err()
    );
}

#[test]
fn thousand_sim_reference_library_deduplicates_items_and_bounds_use_provenance() {
    let f = fixture();
    let mut d = usage_document(&f);
    let template = d["households"][0]["members"][0].clone();
    let mut households = Vec::new();
    for h in 0..50 {
        let mut members = Vec::new();
        for s in 0..20 {
            let mut a = template.clone();
            let n = h * 20 + s;
            a["sim_id"] = json!((1000 + n).to_string());
            a["name"] = json!(format!("Sim Number {n}"));
            members.push(a);
        }
        households.push(json!({"household_id":(100+h).to_string(),"name":format!("Family {h}"),"members":members}));
    }
    d["households"] = json!(households);
    let path = import_usage(&f, &d, "thousand", None);
    let c = usage_catalog(&f, &path);
    let r = c.query(&query("household-id:149")).unwrap();
    assert_eq!(r["total"], 3);
    assert_eq!(r["equipped_snapshot"]["sims"], 1000);
    assert!(
        r["items"]
            .as_array()
            .unwrap()
            .iter()
            .all(|i| i["used_by"]["rows"].as_array().unwrap().len() <= 8
                && i["used_by"]["complete"] == false)
    );
    assert_eq!(
        c.query(&query("sim-id:1998 form:Vampire outfit:everyday/1"))
            .unwrap()["total"],
        1
    );
    assert!(path.metadata().unwrap().len() < 16 * 1024 * 1024);
    assert_eq!(r["package_scan_performed"], false);
}

#[test]
fn prepared_family_pages_keep_general_query_order_scope_and_pagination() {
    let f = fixture();
    let output = f._temp.path().join("fast.sqlite");
    let sha = file_sha256(&f.index).unwrap();
    let result = apex_catalog::optimize::run(&f.index, &sha, &output).unwrap();
    assert_eq!(file_sha256(&f.index).unwrap(), sha);
    let a = Catalog::open(&f.index, &sha).unwrap();
    let b = Catalog::open(&output, result["index_sha256"].as_str().unwrap()).unwrap();
    for sort in ["name", "package", "creator", "id", "newest", "modified"] {
        for body in [None, Some(2), Some(29), Some(999)] {
            for offset in [0, 1, 5] {
                let mut q = query("");
                q.grouped = true;
                q.sort = sort.into();
                q.body_type = body;
                q.limit = 2;
                q.offset = offset;
                let left = a.query(&q).unwrap();
                let right = b.query(&q).unwrap();
                assert_eq!(left["total"], right["total"], "{sort} {body:?}");
                assert_eq!(left["items"], right["items"]);
                assert_eq!(left["next_offset"], right["next_offset"]);
            }
        }
    }
    let mut q = query("Cherry folder:Makeup -Tattoo");
    q.grouped = true;
    assert_eq!(a.query(&q).unwrap()["items"], b.query(&q).unwrap()["items"]);
}

#[test]
fn folder_exact_includes_descendants_but_not_similar_sibling() {
    let f = fixture();
    let r = run(&f, "folder:Makeup");
    assert_eq!(r["total"], 2);
    assert_eq!(r["folder_matches"], json!(["Makeup"]));
}
#[test]
fn folder_prefix_and_typo_offer_actual_paths() {
    let f = fixture();
    let r = run(&f, "folder:mak");
    assert_eq!(r["total"], 3);
    assert_eq!(run(&f, "folder:Makepu")["folder_corrected"], true);
    assert_eq!(run(&f, "folder:unknown")["total"], 0);
}
#[test]
fn folders_names_authors_types_and_origin_intersect() {
    let f = fixture();
    let r = run(
        &f,
        "chery folder:Makeup author:\"Magic Hand\" type:29 origin:cc",
    );
    assert_eq!(r["total"], 1);
    assert_eq!(r["items"][0]["preferred_name"], "Cherry Lipstick");
    assert!(
        !r["items"][0]
            .as_object()
            .unwrap()
            .contains_key("package_path")
    );
}
#[test]
fn wildcard_filename_is_not_sql_and_literal_percent_is_escaped() {
    let f = fixture();
    assert_eq!(run(&f, "package:Ch?rr*.package")["total"], 1);
    assert_eq!(run(&f, "package:%")["total"], 0);
    assert_eq!(run(&f, "package:\"' OR 1=1 --\"")["total"], 0);
}
#[test]
fn quoted_phrase_and_exclusion_are_respected() {
    let f = fixture();
    assert_eq!(run(&f, "\"Cherry Lipstick\"")["total"], 1);
    assert_eq!(run(&f, "cherry -tattoo")["total"], 2);
    assert_eq!(run(&f, "name:*hair code:Bob*")["total"], 1);
}
#[test]
fn unicode_and_windows_separators_are_lossless() {
    let f = fixture();
    assert_eq!(run(&f, "folder:头发")["total"], 1);
    assert_eq!(run(&f, "folder:Makeup\\Lips")["total"], 1);
    assert_eq!(run(&f, "étoile")["total"], 1);
}
#[test]
fn added_excludes_initial_baseline_and_can_combine_with_category() {
    let f = fixture();
    assert_eq!(run(&f, "added:7d")["total"], 4);
    assert_eq!(run(&f, "added:1d type:29")["total"], 1);
    assert_eq!(
        run(&f, "added:7d sort:newest")["items"][0]["preferred_name"],
        "Cherry Lipstick"
    );
    assert_eq!(
        run(&f, "sort:modified")["items"][0]["preferred_name"],
        "Étoile Hair"
    );
}
#[test]
fn invalid_filters_are_explicit_errors_not_silent_ignored_text() {
    let f = fixture();
    let c = Catalog::open(&f.index, &file_sha256(&f.index).unwrap()).unwrap();
    for text in [
        "folder:",
        "added:0d",
        "added:tomorrow",
        "origin:nope",
        "author:\"unclosed",
        "sort:danger",
        "typo:foo",
    ] {
        assert!(c.query(&query(text)).is_err(), "{text}");
    }
}
#[test]
fn moving_or_deleting_original_packages_does_not_affect_offline_search() {
    let f = fixture();
    for row in &f.rows {
        fs::remove_file(row["package_path"].as_str().unwrap()).unwrap();
    }
    let r = run(&f, "folder:Makeup");
    assert_eq!(r["total"], 2);
    assert_eq!(r["package_scan_performed"], false);
    assert_eq!(r["network_contacted"], false);
}
#[test]
fn pin_and_mutation_checks_reject_changed_index() {
    use std::io::Write;
    let f = fixture();
    assert!(Catalog::open(&f.index, &"0".repeat(64)).is_err());
    let c = Catalog::open(&f.index, &file_sha256(&f.index).unwrap()).unwrap();
    fs::OpenOptions::new()
        .append(true)
        .open(&f.index)
        .unwrap()
        .write_all(b"changed")
        .unwrap();
    assert!(c.query(&query("cherry")).is_err());
}
#[test]
fn streaming_fingerprints_match_reference_at_buffer_boundaries() {
    let t = tempfile::tempdir().unwrap();
    for n in [0, 1, 3, 4, 5, 262143, 262144, 262145, 600001] {
        let bytes: Vec<_> = (0..n).map(|i| ((i * 17) % 256) as u8).collect();
        let p = t.path().join("large.package");
        fs::write(&p, &bytes).unwrap();
        let identity = file_identity(&p).unwrap();
        assert_eq!(identity.curseforge_fingerprint, fingerprint(&bytes));
        assert_eq!(identity.bytes, n as u64);
        assert_eq!(identity.sha256, file_sha256(&p).unwrap());
    }
}
#[test]
fn explicit_sync_retains_history_after_move_and_identifies_new_content() {
    let f = fixture();
    let root = f._temp.path();
    let first = root.join("source1.sqlite");
    source(&first, &f.rows[..1], false);
    let cache = root.join("history.sqlite");
    let out1 = root.join("enriched1.sqlite");
    let sync = |input: &Path, output: &Path| {
        enrich::run(enrich::Options {
            index: input,
            expected_sha256: &file_sha256(input).unwrap(),
            output,
            cache: &cache,
            s4mm: &[],
            imports: &[],
            creator_imports: &[],
            wcif_databases: &[],
            online_creators: false,
            wcif_creators: false,
            curseforge_key: None,
            workers: 1,
        })
        .unwrap()
    };
    let original_digest = file_sha256(&first).unwrap();
    let receipt = sync(&first, &out1);
    assert_eq!(receipt["baseline_created"], true);
    assert_eq!(
        Catalog::open(&out1, receipt["index_sha256"].as_str().unwrap())
            .unwrap()
            .query(&query("added:7d"))
            .unwrap()["total"],
        0
    );
    let mut moved = f.rows[0].clone();
    let destination = root.join("Mods/Moved/Cherry.package");
    fs::create_dir_all(destination.parent().unwrap()).unwrap();
    fs::rename(moved["package_path"].as_str().unwrap(), &destination).unwrap();
    moved["package_path"] = json!(destination);
    let second = root.join("source2.sqlite");
    source(&second, &[moved, f.rows[1].clone()], false);
    let out2 = root.join("enriched2.sqlite");
    let r = sync(&second, &out2);
    assert_eq!(r["fingerprints_reused"], 1);
    assert_eq!(r["baseline_created"], false);
    let c = Catalog::open(&out2, r["index_sha256"].as_str().unwrap()).unwrap();
    assert_eq!(c.query(&query("added:7d")).unwrap()["total"], 1);
    assert_eq!(c.query(&query("folder:Moved")).unwrap()["total"], 1);
    assert_eq!(
        file_sha256(&destination).unwrap(),
        f.rows[0]["package_sha256"]
    );
    assert_eq!(file_sha256(&first).unwrap(), original_digest);
}
