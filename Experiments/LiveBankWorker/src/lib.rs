//! Isolated disk/JSON worker prototype. Nothing in Sims or Apex routes here.
//! The owner supplies primitive immutable JSON patches, never game objects.
//! A Ready receipt proves durable bytes only: it grants no native mutation.
use rayon::{ThreadPool, ThreadPoolBuilder};
use sha2::{Digest, Sha256};
use std::{
    collections::{BTreeMap, HashSet},
    fs::{self, File, OpenOptions},
    io::{Read, Write},
    ops::Range,
    path::{Path, PathBuf},
    sync::{Arc, Mutex},
    time::Instant,
};

pub type Result<T> = std::result::Result<T, String>;
pub const MAX_DOCUMENT: usize = 48 * 1024 * 1024;
pub const MAX_JOBS: usize = 4;
pub const MAX_DEPTH: usize = 128;
pub const MAX_NODES: usize = 2_000_000;
pub const MAX_RETAINED_PHASES: usize = 256;
const RESERVATION: usize = MAX_DOCUMENT * 5;
const MAX_RESERVED: usize = RESERVATION * MAX_JOBS;

fn check(ok: bool, message: &str) -> Result<()> {
    if ok { Ok(()) } else { Err(message.into()) }
}
pub fn sha(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}
fn id(text: &str) -> bool {
    !text.is_empty()
        && text.len() <= 20
        && text.as_bytes()[0] != b'0'
        && text.bytes().all(|b| b.is_ascii_digit())
        && text.parse::<u64>().is_ok()
}

#[derive(Clone, Debug)]
enum Value {
    Object(Vec<(Vec<u16>, Node)>),
    Array(Vec<Node>),
    String(Vec<u16>),
    Number,
    Bool(bool),
    Null,
}
#[derive(Clone, Debug)]
struct Node {
    span: Range<usize>,
    value: Value,
}
impl Node {
    fn field(&self, key: &str) -> Option<&Node> {
        match &self.value {
            Value::Object(rows) => rows
                .iter()
                .find(|(k, _)| k.iter().copied().eq(key.encode_utf16()))
                .map(|(_, v)| v),
            _ => None,
        }
    }
    fn string_eq(&self, text: &str) -> bool {
        match &self.value {
            Value::String(s) => s.iter().copied().eq(text.encode_utf16()),
            _ => false,
        }
    }
    fn members(&self) -> Result<&Vec<(Vec<u16>, Node)>> {
        match &self.value {
            Value::Object(rows) => Ok(rows),
            _ => Err("Expected JSON object".into()),
        }
    }
}
struct Parser<'a> {
    raw: &'a [u8],
    at: usize,
    nodes: usize,
}
impl<'a> Parser<'a> {
    fn ws(&mut self) {
        while self
            .raw
            .get(self.at)
            .is_some_and(|b| matches!(*b, b' ' | b'\n' | b'\r' | b'\t'))
        {
            self.at += 1
        }
    }
    fn next(&mut self, b: u8) -> Result<()> {
        check(self.raw.get(self.at) == Some(&b), "Invalid JSON token")?;
        self.at += 1;
        Ok(())
    }
    fn string(&mut self) -> Result<Vec<u16>> {
        self.next(b'"')?;
        let mut decoded = Vec::new();
        loop {
            let b = *self.raw.get(self.at).ok_or("Unterminated JSON string")?;
            self.at += 1;
            match b {
                b'"' => break,
                b'\\' => {
                    let escape = *self.raw.get(self.at).ok_or("Truncated JSON escape")?;
                    self.at += 1;
                    if escape == b'u' {
                        let mut unit = 0u16;
                        for _ in 0..4 {
                            let h = *self.raw.get(self.at).ok_or("Truncated Unicode escape")?;
                            let value = (h as char).to_digit(16).ok_or("Invalid Unicode escape")?;
                            unit = (unit << 4) | value as u16;
                            self.at += 1;
                        }
                        decoded.push(unit);
                    } else {
                        decoded.push(match escape {
                            b'"' => 34,
                            b'\\' => 92,
                            b'/' => 47,
                            b'b' => 8,
                            b'f' => 12,
                            b'n' => 10,
                            b'r' => 13,
                            b't' => 9,
                            _ => return Err("Invalid JSON escape".into()),
                        });
                    }
                }
                0..=31 => return Err("Unescaped control character".into()),
                128..=255 => {
                    let ch = std::str::from_utf8(&self.raw[self.at - 1..])
                        .map_err(|_| "Invalid UTF-8 string")?
                        .chars()
                        .next()
                        .ok_or("Truncated Unicode string")?;
                    self.at += ch.len_utf8() - 1;
                    let mut units = [0u16; 2];
                    decoded.extend_from_slice(ch.encode_utf16(&mut units));
                }
                _ => decoded.push(b as u16),
            }
        }
        // UTF16 units preserve Python's accepted escaped lone surrogates too.
        // Valid pairs and literal astral Unicode compare as the same key.
        Ok(decoded)
    }
    fn number(&mut self) -> Result<()> {
        let start = self.at;
        if self.raw.get(self.at) == Some(&b'-') {
            self.at += 1;
        }
        if self.raw.get(self.at) == Some(&b'0') {
            self.at += 1;
        } else {
            check(
                self.raw
                    .get(self.at)
                    .is_some_and(|b| matches!(*b, b'1'..=b'9')),
                "Invalid JSON number",
            )?;
            while self.raw.get(self.at).is_some_and(u8::is_ascii_digit) {
                self.at += 1;
            }
        }
        let mut float = false;
        if self.raw.get(self.at) == Some(&b'.') {
            float = true;
            self.at += 1;
            let begin = self.at;
            while self.raw.get(self.at).is_some_and(u8::is_ascii_digit) {
                self.at += 1;
            }
            check(self.at > begin, "Missing fractional digits")?;
        }
        if self
            .raw
            .get(self.at)
            .is_some_and(|b| matches!(*b, b'e' | b'E'))
        {
            float = true;
            self.at += 1;
            if self
                .raw
                .get(self.at)
                .is_some_and(|b| matches!(*b, b'+' | b'-'))
            {
                self.at += 1;
            }
            let begin = self.at;
            while self.raw.get(self.at).is_some_and(u8::is_ascii_digit) {
                self.at += 1;
            }
            check(self.at > begin, "Missing exponent digits")?;
        }
        if float {
            let text =
                std::str::from_utf8(&self.raw[start..self.at]).map_err(|_| "Invalid number")?;
            check(
                text.parse::<f64>().is_ok_and(f64::is_finite),
                "Nonfinite JSON number",
            )?;
        }
        // Integers stay raw, including values larger than u64. No f64 conversion.
        Ok(())
    }
    fn value(&mut self, depth: usize) -> Result<Node> {
        check(depth <= MAX_DEPTH, "Explicit JSON depth budget exceeded")?;
        self.nodes += 1;
        check(
            self.nodes <= MAX_NODES,
            "Explicit JSON node budget exceeded",
        )?;
        self.ws();
        let start = self.at;
        let value = match self
            .raw
            .get(self.at)
            .copied()
            .ok_or("Truncated JSON value")?
        {
            b'{' => {
                self.at += 1;
                self.ws();
                let mut rows = Vec::new();
                let mut keys = HashSet::new();
                if self.raw.get(self.at) != Some(&b'}') {
                    loop {
                        self.ws();
                        let key = self.string()?;
                        check(keys.insert(key.clone()), "Duplicate decoded JSON key")?;
                        self.ws();
                        self.next(b':')?;
                        rows.push((key, self.value(depth + 1)?));
                        self.ws();
                        if self.raw.get(self.at) == Some(&b'}') {
                            break;
                        }
                        self.next(b',')?;
                    }
                }
                self.next(b'}')?;
                Value::Object(rows)
            }
            b'[' => {
                self.at += 1;
                self.ws();
                let mut rows = Vec::new();
                if self.raw.get(self.at) != Some(&b']') {
                    loop {
                        rows.push(self.value(depth + 1)?);
                        self.ws();
                        if self.raw.get(self.at) == Some(&b']') {
                            break;
                        }
                        self.next(b',')?;
                    }
                }
                self.next(b']')?;
                Value::Array(rows)
            }
            b'"' => Value::String(self.string()?),
            b't' => {
                check(
                    self.raw.get(self.at..self.at + 4) == Some(b"true"),
                    "Invalid JSON literal",
                )?;
                self.at += 4;
                Value::Bool(true)
            }
            b'f' => {
                check(
                    self.raw.get(self.at..self.at + 5) == Some(b"false"),
                    "Invalid JSON literal",
                )?;
                self.at += 5;
                Value::Bool(false)
            }
            b'n' => {
                check(
                    self.raw.get(self.at..self.at + 4) == Some(b"null"),
                    "Invalid JSON literal",
                )?;
                self.at += 4;
                Value::Null
            }
            b'-' | b'0'..=b'9' => {
                self.number()?;
                Value::Number
            }
            _ => return Err("Invalid JSON value".into()),
        };
        Ok(Node {
            span: start..self.at,
            value,
        })
    }
}
fn parse(raw: &[u8]) -> Result<Node> {
    check(
        !raw.is_empty() && raw.len() <= MAX_DOCUMENT,
        "Explicit JSON byte budget exceeded",
    )?;
    std::str::from_utf8(raw).map_err(|_| "Invalid UTF-8")?;
    let mut p = Parser {
        raw,
        at: 0,
        nodes: 0,
    };
    let value = p.value(0)?;
    p.ws();
    check(p.at == raw.len(), "Trailing JSON bytes")?;
    Ok(value)
}
pub fn validate_json(raw: &[u8]) -> Result<()> {
    parse(raw).map(|_| ())
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub enum Phase {
    Captured,
    Issued,
    Complete,
}
impl Phase {
    fn next(self) -> Option<Self> {
        match self {
            Self::Captured => Some(Self::Issued),
            Self::Issued => Some(Self::Complete),
            Self::Complete => None,
        }
    }
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Context {
    pub uuid: String,
    pub save: String,
    pub sim: String,
}
impl Context {
    fn validate(&self) -> Result<()> {
        check(
            self.uuid.len() == 32
                && self
                    .uuid
                    .bytes()
                    .all(|b| b.is_ascii_digit() || matches!(b, b'a'..=b'f')),
            "Context needs exact UUID",
        )?;
        check(
            id(&self.save) && id(&self.sim),
            "Context needs exact save/Sim uint64 IDs",
        )
    }
    fn key(&self) -> String {
        format!("{}:{}", self.save, self.sim)
    }
}
#[derive(Clone, Debug)]
pub struct Update {
    pub key: String,
    pub raw: Vec<u8>,
}
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum Fault {
    #[default]
    None,
    BeforeRead,
    BeforeWrite,
    AfterTempSync,
    BeforeReplace,
    AfterReplace,
    AfterReadback,
    WrongReadback,
    LostReceipt,
}
#[derive(Clone, Debug)]
pub struct Request {
    pub context: Context,
    pub phase: Phase,
    pub expected_sha: String,
    pub updates: Vec<Update>,
    pub fault: Fault,
}
impl Request {
    fn validate(&self) -> Result<()> {
        self.context.validate()?;
        check(
            self.expected_sha.len() == 64
                && self
                    .expected_sha
                    .bytes()
                    .all(|b| b.is_ascii_digit() || matches!(b, b'a'..=b'f')),
            "Expected SHA invalid",
        )?;
        check(
            !self.updates.is_empty() && self.updates.len() <= 7,
            "Explicit patch count budget exceeded",
        )?;
        let mut keys = HashSet::new();
        let mut total = 0;
        for u in &self.updates {
            check(keys.insert(&u.key), "Duplicate patch key")?;
            check(
                if self.phase == Phase::Complete {
                    matches!(
                        u.key.as_str(),
                        "switch_pending"
                            | "bank"
                            | "active_lane"
                            | "runtime_pid"
                            | "switch_history"
                            | "hair_policy"
                    )
                } else {
                    u.key == "switch_pending"
                },
                "Unreviewed record field patch",
            )?;
            total += u.raw.len();
            check(
                total <= MAX_DOCUMENT,
                "Explicit aggregate patch byte budget exceeded",
            )?;
            parse(&u.raw)?;
        }
        check(
            keys.contains(&"switch_pending".to_string()),
            "Every phase must explicitly retain or clear its WAL",
        )?;
        Ok(())
    }
}

fn valid_phase(record: &Node, ctx: &Context, phase: Phase) -> Result<()> {
    let pending = record.field("switch_pending").ok_or("Missing phase WAL")?;
    let witness = if phase == Phase::Complete {
        check(
            matches!(pending.value, Value::Null),
            "Complete phase must clear its WAL",
        )?;
        let history = record
            .field("switch_history")
            .ok_or("Missing completion history")?;
        match &history.value {
            Value::Array(rows) => rows.last().ok_or("Empty completion history")?,
            _ => return Err("History must be an array".into()),
        }
    } else {
        pending
    };
    check(
        witness
            .field("request_id")
            .is_some_and(|n| n.string_eq(&ctx.uuid)),
        "WAL UUID differs",
    )?;
    let expected = match phase {
        Phase::Captured => "captured",
        Phase::Issued => "native-operation-issued",
        Phase::Complete => "immediate-native-readback-verified",
    };
    check(
        witness
            .field("state")
            .is_some_and(|n| n.string_eq(expected)),
        "WAL phase differs",
    )?;
    if phase == Phase::Complete {
        for key in ["all_stored_owners_verified", "active_owner_verified"] {
            check(
                witness
                    .field(key)
                    .is_some_and(|n| matches!(n.value, Value::Bool(true))),
                "Complete phase lacks full owner verification",
            )?;
        }
    }
    Ok(())
}

/// Preserve every untouched raw byte, including unknown keys and numeric spelling.
/// Only the selected existing record's reviewed top-level value spans may change.
pub fn patch_document(raw: &[u8], request: &Request) -> Result<Vec<u8>> {
    request.validate()?;
    let document = parse(raw)?;
    let schema = document.field("schema").ok_or("Bank schema absent")?;
    check(
        matches!(schema.value, Value::Number) && &raw[schema.span.clone()] == b"1",
        "Exact bank schema1 required",
    )?;
    let records = document.field("records").ok_or("Bank records absent")?;
    records.members()?;
    let record = records
        .field(&request.context.key())
        .ok_or("Selected existing record is absent")?;
    match request.phase {
        Phase::Captured => {
            check(
                record
                    .field("switch_pending")
                    .is_none_or(|n| matches!(n.value, Value::Null)),
                "Another switch WAL is retained",
            )?;
            check(
                record
                    .field("pending")
                    .is_none_or(|n| matches!(n.value, Value::Null)),
                "A legacy CAS WAL is retained",
            )?;
        }
        Phase::Issued => valid_phase(record, &request.context, Phase::Captured)?,
        Phase::Complete => valid_phase(record, &request.context, Phase::Issued)?,
    }
    let members = record.members()?;
    let mut patches = Vec::new();
    let mut additions = Vec::new();
    for u in &request.updates {
        if let Some(old) = record.field(&u.key) {
            patches.push((old.span.clone(), u.raw.clone()));
        } else {
            additions.push(u);
        }
    }
    if !additions.is_empty() {
        let mut extra = Vec::new();
        for (i, u) in additions.iter().enumerate() {
            if i > 0 || !members.is_empty() {
                extra.push(b',');
            }
            extra.extend(serde_json::to_vec(&u.key).map_err(|_| "Patch key encoding failed")?);
            extra.push(b':');
            extra.extend(&u.raw);
        }
        let at = record.span.end - 1;
        patches.push((at..at, extra));
    }
    patches.sort_by_key(|(range, _)| range.start);
    let mut after = Vec::with_capacity(raw.len());
    let mut at = 0;
    for (range, replacement) in patches {
        check(range.start >= at, "Overlapping patch spans")?;
        after.extend(&raw[at..range.start]);
        after.extend(replacement);
        at = range.end;
    }
    after.extend(&raw[at..]);
    check(
        after.len() <= MAX_DOCUMENT,
        "Patched bank exceeds explicit byte budget",
    )?;
    let result = parse(&after)?;
    let selected = result
        .field("records")
        .and_then(|n| n.field(&request.context.key()))
        .ok_or("Patched record disappeared")?;
    valid_phase(selected, &request.context, request.phase)?;
    Ok(after)
}

fn regular(path: &Path, directory: bool) -> Result<()> {
    let info = fs::symlink_metadata(path).map_err(|e| e.to_string())?;
    check(!info.file_type().is_symlink(), "Symlink path refused")?;
    #[cfg(windows)]
    {
        use std::os::windows::fs::MetadataExt;
        check(info.file_attributes() & 0x400 == 0, "Reparse path refused")?;
    }
    check(
        if directory {
            info.is_dir()
        } else {
            info.is_file()
        },
        "Unexpected path type",
    )
}
fn read_exact_file(path: &Path) -> Result<Vec<u8>> {
    regular(path, false)?;
    let mut file = File::open(path).map_err(|e| e.to_string())?;
    let before = file.metadata().map_err(|e| e.to_string())?;
    check(
        before.len() > 0 && before.len() <= MAX_DOCUMENT as u64,
        "Bank file exceeds explicit byte budget",
    )?;
    let mut raw = Vec::new();
    Read::by_ref(&mut file)
        .take(MAX_DOCUMENT as u64 + 1)
        .read_to_end(&mut raw)
        .map_err(|e| e.to_string())?;
    let after = file.metadata().map_err(|e| e.to_string())?;
    check(
        raw.len() <= MAX_DOCUMENT
            && before.len() == after.len()
            && before.modified().ok() == after.modified().ok(),
        "Bank changed during complete read",
    )?;
    Ok(raw)
}
fn fail(actual: Fault, wanted: Fault) -> Result<()> {
    check(actual != wanted, "Injected durability fault")
}

struct Lease {
    path: PathBuf,
    raw: Vec<u8>,
    keep: bool,
}
impl Lease {
    fn acquire(root: &Path, ctx: &Context) -> Result<Self> {
        let path = root.join(".form_bank.json.cas-writer.lock");
        let raw = serde_json::to_vec(
            &serde_json::json!({"schema":1,"pid":std::process::id(),"token":ctx.uuid}),
        )
        .map_err(|e| e.to_string())?;
        let mut file = OpenOptions::new()
            .create_new(true)
            .write(true)
            .open(&path)
            .map_err(|_| "Writer lease exists or cannot be acquired")?;
        file.write_all(&raw).map_err(|e| e.to_string())?;
        file.sync_all().map_err(|e| e.to_string())?;
        Ok(Self {
            path,
            raw,
            keep: false,
        })
    }
    fn verify(&self) -> Result<()> {
        regular(&self.path, false)?;
        check(
            fs::read(&self.path).map_err(|e| e.to_string())? == self.raw,
            "Writer lease changed",
        )
    }
}
impl Drop for Lease {
    fn drop(&mut self) {
        if !self.keep && self.verify().is_ok() {
            let _ = fs::remove_file(&self.path);
        }
    }
}

#[derive(Clone, Debug)]
pub struct Receipt {
    pub context: Context,
    pub phase: Phase,
    pub before_sha: String,
    pub file_sha: String,
    pub before_bytes: usize,
    pub after_bytes: usize,
    pub worker_ms: f64,
    pub durable: bool,
    pub native_call_authorized: bool,
}
#[derive(Clone, Debug)]
pub enum Poll {
    Pending,
    Ready(Receipt),
    Failed {
        message: String,
        outcome_may_be_durable: bool,
    },
    Unknown,
    ContextMismatch,
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Submit {
    Accepted(u64),
    OriginalOnly {
        ticket: u64,
        input_not_adopted: bool,
    },
    Busy,
    Refused(String),
}
struct Job {
    context: Context,
    phase: Phase,
    result: Poll,
}
#[derive(Default)]
struct Session {
    context: Option<Context>,
    last: Option<(Phase, String)>,
    busy: bool,
    failed: bool,
}
#[derive(Default)]
struct State {
    next: u64,
    inflight: usize,
    reserved: usize,
    jobs: BTreeMap<u64, Job>,
    sessions: BTreeMap<String, Session>,
}
pub struct Worker {
    root: PathBuf,
    pool: ThreadPool,
    state: Arc<Mutex<State>>,
    writer: Arc<Mutex<()>>,
}
impl Worker {
    /// Caller must authenticate this root against its actual profile before opening.
    /// This standalone prototype authenticates regular paths, not a Sims identity.
    pub fn open(root: &Path) -> Result<Self> {
        for parent in root.ancestors() {
            regular(parent, true)?;
        }
        let root = root.canonicalize().map_err(|e| e.to_string())?;
        regular(&root, true)?;
        let pool = ThreadPoolBuilder::new()
            .num_threads(2)
            .thread_name(|i| format!("ApexBankPrototype-{i}"))
            .build()
            .map_err(|e| e.to_string())?;
        Ok(Self {
            root,
            pool,
            state: Arc::new(Mutex::new(State::default())),
            writer: Arc::new(Mutex::new(())),
        })
    }
    pub fn limits(&self) -> (usize, usize, usize, usize) {
        (2, MAX_JOBS, MAX_DOCUMENT, MAX_RESERVED)
    }
    pub fn submit(&self, request: Request) -> Submit {
        // Main-side admission checks only bounded primitives/ownership. Parsing
        // the document or a large patch belongs exclusively to the worker.
        if let Err(e) = request.context.validate() {
            return Submit::Refused(e);
        }
        if request.updates.len() > 7
            || request.updates.iter().any(|u| u.key.len() > 64)
            || request.updates.iter().map(|u| u.raw.len()).sum::<usize>() > MAX_DOCUMENT
        {
            return Submit::Refused("Explicit patch budget exceeded".into());
        }
        let mut state = match self.state.lock() {
            Ok(s) => s,
            Err(_) => return Submit::Refused("Worker state unavailable".into()),
        };
        for (&ticket, job) in &state.jobs {
            if job.context.uuid == request.context.uuid && job.phase == request.phase {
                // Never hash/compare a large input on the submitting game thread.
                // A repeated UUID adopts NO supplied bytes, even if identical.
                // Caller must poll the original ticket; it is not a new success.
                return if job.context == request.context {
                    Submit::OriginalOnly {
                        ticket,
                        input_not_adopted: true,
                    }
                } else {
                    Submit::Refused("UUID phase reused by a different owner".into())
                };
            }
        }
        if state.jobs.len() >= MAX_RETAINED_PHASES {
            return Submit::Refused(
                "Explicit retained phase budget full; no receipts were evicted".into(),
            );
        }
        if state.inflight >= MAX_JOBS || state.reserved + RESERVATION > MAX_RESERVED {
            return Submit::Busy;
        }
        let session = state
            .sessions
            .entry(request.context.uuid.clone())
            .or_default();
        if session
            .context
            .as_ref()
            .is_some_and(|c| c != &request.context)
        {
            return Submit::Refused("UUID belongs to another save or Sim".into());
        }
        if session.failed || session.busy {
            return Submit::Refused("Original phase unresolved; inspect its ticket".into());
        }
        match &session.last {
            None if request.phase == Phase::Captured => {}
            Some((phase, sha))
                if phase.next() == Some(request.phase) && sha == &request.expected_sha => {}
            _ => return Submit::Refused("Durable phase order or acknowledged SHA differs".into()),
        }
        session.context = Some(request.context.clone());
        session.busy = true;
        state.next += 1;
        let ticket = state.next;
        state.inflight += 1;
        state.reserved += RESERVATION;
        state.jobs.insert(
            ticket,
            Job {
                context: request.context.clone(),
                phase: request.phase,
                result: Poll::Pending,
            },
        );
        drop(state);
        let shared = Arc::clone(&self.state);
        let writer = Arc::clone(&self.writer);
        let root = self.root.clone();
        self.pool.spawn_fifo(move || {
            let started = Instant::now();
            let mut may_be_durable = false;
            let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
                let _writer = writer.lock().map_err(|_| "Writer queue unavailable")?;
                durable_phase(&root, &request, &mut may_be_durable)
            }));
            let result = match result {
                Ok(Ok(mut r)) => {
                    r.worker_ms = started.elapsed().as_secs_f64() * 1000.0;
                    Poll::Ready(r)
                }
                Ok(Err(e)) => Poll::Failed {
                    message: e,
                    outcome_may_be_durable: may_be_durable,
                },
                Err(_) => Poll::Failed {
                    message: "Worker panic retained as unresolved".into(),
                    outcome_may_be_durable: may_be_durable,
                },
            };
            if let Ok(mut state) = shared.lock() {
                state.inflight -= 1;
                state.reserved -= RESERVATION;
                let session = state
                    .sessions
                    .get_mut(&request.context.uuid)
                    .expect("Session retained");
                session.busy = false;
                if let Poll::Ready(r) = &result {
                    session.last = Some((r.phase, r.file_sha.clone()));
                } else {
                    session.failed = true;
                }
                if let Some(job) = state.jobs.get_mut(&ticket) {
                    job.result = result;
                }
            }
        });
        Submit::Accepted(ticket)
    }
    pub fn poll(&self, context: &Context, ticket: u64) -> Poll {
        match self.state.lock() {
            Ok(state) => match state.jobs.get(&ticket) {
                Some(job) if &job.context == context => job.result.clone(),
                Some(_) => Poll::ContextMismatch,
                None => Poll::Unknown,
            },
            Err(_) => Poll::Failed {
                message: "Worker state unavailable".into(),
                outcome_may_be_durable: true,
            },
        }
    }
}

fn durable_phase(root: &Path, request: &Request, may_be_durable: &mut bool) -> Result<Receipt> {
    request.validate()?;
    regular(root, true)?;
    fail(request.fault, Fault::BeforeRead)?;
    let mut lease = Lease::acquire(root, &request.context)?;
    lease.verify()?;
    let path = root.join("form_bank.json");
    let before = read_exact_file(&path)?;
    check(
        sha(&before) == request.expected_sha,
        "Complete bank SHA differs under writer lease",
    )?;
    let after = patch_document(&before, request)?;
    let expected = sha(&after);
    fail(request.fault, Fault::BeforeWrite)?;
    let pending = root.join("form_bank.json.pending");
    let mut file = OpenOptions::new()
        .create_new(true)
        .write(true)
        .open(&pending)
        .map_err(|_| "Pending evidence exists; no overwrite authorized")?;
    file.write_all(&after).map_err(|e| e.to_string())?;
    file.sync_all().map_err(|e| e.to_string())?;
    drop(file);
    fail(request.fault, Fault::AfterTempSync)?;
    lease.verify()?;
    // Re-read under the same cooperative lease immediately before replacement.
    // An external writer ignoring the lease is not an atomic filesystem CAS.
    check(
        sha(&read_exact_file(&path)?) == request.expected_sha,
        "Bank changed before atomic replacement",
    )?;
    fail(request.fault, Fault::BeforeReplace)?;
    fs::rename(&pending, &path).map_err(|e| e.to_string())?;
    *may_be_durable = true;
    lease.keep = true;
    #[cfg(not(windows))]
    File::open(root)
        .and_then(|d| d.sync_all())
        .map_err(|e| e.to_string())?;
    fail(request.fault, Fault::AfterReplace)?;
    let observed = read_exact_file(&path)?;
    check(
        request.fault != Fault::WrongReadback && observed == after && sha(&observed) == expected,
        "Complete durable readback differs",
    )?;
    fail(request.fault, Fault::AfterReadback)?;
    lease.verify()?;
    fail(request.fault, Fault::LostReceipt)?;
    lease.keep = false;
    Ok(Receipt {
        context: request.context.clone(),
        phase: request.phase,
        before_sha: request.expected_sha.clone(),
        file_sha: expected,
        before_bytes: before.len(),
        after_bytes: after.len(),
        worker_ms: 0.0,
        durable: true,
        native_call_authorized: false,
    })
}

#[cfg(test)]
mod scheduling_tests {
    use super::*;
    #[test]
    fn held_disk_lane_does_not_block_submit_or_poll_and_reports_backpressure() {
        let dir = tempfile::tempdir().unwrap();
        fs::write(
            dir.path().join("form_bank.json"),
            b"{\"schema\":1,\"records\":{\"10:20\":{\"switch_pending\":null}}}",
        )
        .unwrap();
        let worker = Worker::open(dir.path()).unwrap();
        let disk_guard = worker.writer.lock().unwrap();
        let mut pending = Vec::new();
        for i in 0..MAX_JOBS {
            let context = Context {
                uuid: format!("{i:032x}"),
                save: "10".into(),
                sim: "20".into(),
            };
            let request = Request {
                context: context.clone(),
                phase: Phase::Captured,
                expected_sha: "a".repeat(64),
                updates: vec![],
                fault: Fault::None,
            };
            match worker.submit(request) {
                Submit::Accepted(t) => pending.push((context, t)),
                other => panic!("{other:?}"),
            }
        }
        // Both CPU workers are waiting on the disk mutex, yet caller can submit
        // and perform thousands of status reads. It never joins a worker.
        for _ in 0..1000 {
            for (c, t) in &pending {
                assert!(matches!(worker.poll(c, *t), Poll::Pending));
            }
        }
        let context = Context {
            uuid: "f".repeat(32),
            save: "10".into(),
            sim: "20".into(),
        };
        assert_eq!(
            worker.submit(Request {
                context,
                phase: Phase::Captured,
                expected_sha: "a".repeat(64),
                updates: vec![],
                fault: Fault::None
            }),
            Submit::Busy
        );
        drop(disk_guard);
    }
}
