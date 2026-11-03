//! Optional one-shot private CAS status probe. No import or activation API.
//! Linux only; trusted immutable deployment paths. Not descendant containment.
use sha2::{Digest, Sha256};
use std::{fs::{self, File}, io::{Read, Write}, path::{Path, PathBuf},
    sync::{Arc, Mutex}, thread::{self, JoinHandle}, time::{Duration, Instant}};
const ROOT_SHA: &str = "b1b0550fd27a31fe82eacfc583ee681de7c436536461143bb78b200e758c8306";
const STARTUP: Duration = Duration::from_secs(30);
const COMMAND: Duration = Duration::from_secs(3);
const TICK: Duration = Duration::from_millis(10);
const NAMES: [&str; 11] = ["PYTHON", "PYTHON_SHA256", "ROOT", "CONFIG", "CONFIG_SHA256",
    "SIDECAR_RUNTIME", "DEADLINE_STREAMS", "RUNTIME_SHUTDOWN", "TRUSTED_BOOTSTRAP", "IMPORT_FRAMES", "STREAM_DISPATCHER"];
type Result<T> = std::result::Result<T, &'static str>;
#[derive(Clone, Copy, PartialEq, Eq)]
enum Phase { Starting, Checking, Complete, Unavailable, Stopped }
struct State { phase: Phase, stop: bool, deadline: Instant, cleanup_pending: bool }
struct Shared { state: Mutex<State> }
fn lock(s: &Shared) -> std::sync::MutexGuard<'_, State> {
    s.state.lock().unwrap_or_else(std::sync::PoisonError::into_inner)
}
fn hex(bytes: &[u8]) -> String { bytes.iter().map(|v| format!("{v:02x}")).collect() }
fn valid_sha(s: &str) -> bool { s.len() == 64 && s.bytes().all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b)) }
fn absolute(s: &str) -> bool {
    s.starts_with('/') && s.len() <= 4096 && s != "/" && !s.ends_with('/') &&
    !s.chars().any(char::is_control) && !s.split('/').skip(1).any(|p| p.is_empty() || p == "." || p == "..")
}
struct Config { values: [String; 11], epoch: [u8; 16] }
fn config(values: [Option<String>; 11]) -> Result<Option<Config>> {
    if values.iter().all(Option::is_none) { return Ok(None); }
    if values.iter().any(Option::is_none) { return Err("CAS status configuration incomplete"); }
    let values = values.map(Option::unwrap);
    for (i, value) in values.iter().enumerate() {
        if !(if i == 1 || i == 4 { valid_sha(value) } else { absolute(value) }) { return Err("CAS status configuration invalid"); }
    }
    Ok(Some(Config { values, epoch: [0; 16] }))
}
/// Public DTO exposes only parent-owned probe state, not imported catalog state.
pub(super) struct ImportStatus { shared: Arc<Shared>, worker: Mutex<Option<JoinHandle<()>>> }
impl ImportStatus {
    pub(super) fn from_env() -> Result<Option<Self>> {
        let mut values: [Option<String>; 11] = std::array::from_fn(|_| None);
        for (slot, name) in values.iter_mut().zip(NAMES) {
            *slot = match std::env::var(format!("APEX_CAS_STATUS_{name}")) {
                Ok(v) => Some(v), Err(std::env::VarError::NotPresent) => None,
                Err(_) => return Err("CAS status configuration encoding"),
            };
        }
        let Some(mut cfg) = config(values)? else { return Ok(None); };
        if !cfg!(target_os = "linux") { return Err("CAS status requires Linux"); }
        File::open("/dev/urandom").and_then(|mut f| f.read_exact(&mut cfg.epoch)).map_err(|_| "CAS status epoch unavailable")?;
        let shared = Arc::new(Shared { state: Mutex::new(State { phase: Phase::Starting, stop: false,
            deadline: Instant::now() + STARTUP, cleanup_pending: false }) });
        let owner = Arc::clone(&shared);
        let worker = thread::Builder::new().name("cas-status-owner".into()).stack_size(512 * 1024)
            .spawn(move || run(&owner, cfg)).map_err(|_| "CAS status owner unavailable")?;
        Ok(Some(Self { shared, worker: Mutex::new(Some(worker)) }))
    }
    pub(super) fn status_json(&self) -> String {
        let _ = check(&self.shared);
        let s = lock(&self.shared);
        let phase = match s.phase { Phase::Starting => "starting", Phase::Checking => "checking",
            Phase::Complete => "complete", Phase::Unavailable => "unavailable", Phase::Stopped => "stopped" };
        format!("{{\"schema\":1,\"enabled\":true,\"status_only\":true,\"mutation_enabled\":false,\"activation_enabled\":false,\"probe_state\":\"{phase}\",\"cleanup_pending\":{},\"active_selection_verified\":false,\"containment_scope\":\"direct_child_only\",\"descendant_containment_verified\":false,\"parent_death_cleanup_verified\":false}}", s.cleanup_pending)
    }
    pub(super) fn stop(&self) {
        { let mut s = lock(&self.shared); s.stop = true; if !matches!(s.phase, Phase::Complete | Phase::Unavailable) { s.phase = Phase::Stopped; } }
        // Never block app shutdown on filesystem/spawn/kernel teardown. The
        // worker retains ownership until its child is reaped. This is NOT a
        // guarantee of cleanup if the entire Rust application is killed.
        let mut worker = self.worker.lock().unwrap_or_else(std::sync::PoisonError::into_inner);
        if worker.as_ref().is_some_and(JoinHandle::is_finished) {
            if let Some(handle) = worker.take() { let _ = handle.join(); }
        }
    }
}
impl Drop for ImportStatus { fn drop(&mut self) { self.stop(); } }
fn check(shared: &Shared) -> Result<()> {
    let mut s = lock(shared);
    if s.stop { return Err("stopped"); }
    if s.phase == Phase::Complete { return Ok(()); }
    if Instant::now() >= s.deadline { s.stop = true; s.phase = Phase::Unavailable; return Err("deadline"); }
    Ok(())
}
fn fail(shared: &Shared) {
    let mut s = lock(shared); if !s.stop { s.phase = Phase::Unavailable; } s.stop = true;
}
#[cfg(target_os = "linux")]
type FileIdentity = (u64, u64, u64, i64, i64, i64, i64);
#[cfg(target_os = "linux")]
fn metadata_identity(m: &fs::Metadata) -> Result<FileIdentity> {
    use std::os::unix::fs::MetadataExt;
    if !m.is_file() || m.file_type().is_symlink() || m.nlink() != 1 { return Err("pin identity"); }
    Ok((m.dev(), m.ino(), m.len(), m.mtime(), m.mtime_nsec(), m.ctime(), m.ctime_nsec()))
}
#[cfg(target_os = "linux")]
fn identity(path: &Path) -> Result<FileIdentity> {
    metadata_identity(&fs::symlink_metadata(path).map_err(|_| "pin unavailable")?)
}
#[cfg(target_os = "linux")]
fn open_pinned(path: &Path, expected: FileIdentity) -> Result<File> {
    use std::os::unix::fs::OpenOptionsExt;
    // Refuse final-component symlinks and FIFO substitution at open time.
    // This does not establish ancestor trust or a hard filesystem deadline.
    let file = fs::OpenOptions::new().read(true)
        .custom_flags(libc::O_NOFOLLOW | libc::O_NONBLOCK).open(path).map_err(|_| "pin open")?;
    if metadata_identity(&file.metadata().map_err(|_| "pin metadata")?)? != expected {
        return Err("pin changed");
    }
    Ok(file)
}
#[cfg(target_os = "linux")]
fn pinned(shared: &Shared, path: &str, expected: &str, maximum: usize, capture: bool) -> Result<Vec<u8>> {
    check(shared)?;
    let path = PathBuf::from(path); let before = identity(&path)?;
    if before.2 == 0 || before.2 > maximum as u64 { return Err("pin size"); }
    let mut f = open_pinned(&path, before)?;
    let mut hash = Sha256::new(); let mut bytes = Vec::new(); let mut block = [0u8; 16384]; let mut total = 0;
    loop {
        check(shared)?; let n = f.read(&mut block).map_err(|_| "pin read")?; if n == 0 { break; }
        total += n; if total > maximum { return Err("pin size"); }
        hash.update(&block[..n]); if capture { bytes.extend_from_slice(&block[..n]); }
    }
    check(shared)?;
    if total as u64 != before.2 || hex(&hash.finalize()) != expected || metadata_identity(&f.metadata().map_err(|_| "pin metadata")?)? != before || identity(&path)? != before { return Err("pin changed"); }
    Ok(bytes)
}
fn header(kind: u8, epoch: &[u8; 16], ticket: u64, length: usize) -> Vec<u8> {
    let mut h = Vec::with_capacity(40); h.extend_from_slice(b"APXIMP01"); h.extend_from_slice(&[1, kind, 0, 0]);
    h.extend_from_slice(epoch); h.extend_from_slice(&ticket.to_be_bytes()); h.extend_from_slice(&(length as u32).to_be_bytes()); h
}
fn extent(raw: &[u8; 40], epoch: &[u8; 16], kind: u8, ticket: u64) -> Result<usize> {
    if raw[..8] != *b"APXIMP01" || raw[8..12] != [1, kind, 0, 0] || raw[12..28] != epoch[..] ||
        raw[28..36] != ticket.to_be_bytes() { return Err("frame identity"); }
    let n = u32::from_be_bytes(raw[36..40].try_into().unwrap()) as usize;
    if (kind == 1 && ticket == 0 && n == 48) || (kind == 3 && ticket == 1 && (1..=4096).contains(&n)) { Ok(n) }
    else { Err("frame extent") }
}
#[cfg(target_os = "linux")]
fn exact(shared: &Shared, stream: &mut impl Read, bytes: &mut [u8]) -> Result<()> {
    let mut at = 0;
    while at < bytes.len() {
        check(shared)?;
        match stream.read(&mut bytes[at..]) {
            Ok(0) => return Err("EOF"), Ok(n) => at += n,
            Err(e) if e.kind() == std::io::ErrorKind::WouldBlock => thread::sleep(TICK),
            Err(e) if e.kind() == std::io::ErrorKind::Interrupted => (), Err(_) => return Err("read"),
        }
    }
    check(shared)
}
#[cfg(target_os = "linux")]
fn send(shared: &Shared, stream: &mut impl Write, bytes: &[u8]) -> Result<()> {
    let mut at = 0;
    while at < bytes.len() {
        check(shared)?;
        match stream.write(&bytes[at..]) {
            Ok(0) => return Err("write zero"), Ok(n) => at += n,
            Err(e) if e.kind() == std::io::ErrorKind::WouldBlock => thread::sleep(TICK),
            Err(e) if e.kind() == std::io::ErrorKind::Interrupted => (), Err(_) => return Err("write"),
        }
    }
    check(shared)
}
#[cfg(target_os = "linux")]
fn frame(shared: &Shared, output: &mut impl Read, epoch: &[u8; 16], kind: u8, ticket: u64) -> Result<()> {
    let mut h = [0u8; 40]; exact(shared, output, &mut h)?;
    let n = extent(&h, epoch, kind, ticket)?;
    // READY token/capability are not needed for status. Discard without logging.
    // RESPONSE is opaque private evidence; no claim about its JSON semantics.
    let mut payload = vec![0u8; n]; exact(shared, output, &mut payload)?; payload.fill(0); Ok(())
}
#[cfg(target_os = "linux")]
fn run(shared: &Shared, cfg: Config) {
    use std::{os::{fd::OwnedFd, unix::net::UnixStream}, process::{Command, Stdio}};
    let result = (|| -> Result<()> {
        let v = &cfg.values;
        pinned(shared, &v[0], &v[1], 64 * 1024 * 1024, false)?;
        let executable = identity(Path::new(&v[0]))?;
        let source = pinned(shared, &v[2], ROOT_SHA, 131072, true)?;
        let source = String::from_utf8(source).map_err(|_| "root encoding")?;
        pinned(shared, &v[3], &v[4], 16384, false)?;
        let (mut input, child_input) = UnixStream::pair().map_err(|_| "pipe")?;
        let (mut output, child_output) = UnixStream::pair().map_err(|_| "pipe")?;
        for socket in [&input, &child_input, &output, &child_output] { socket.set_nonblocking(true).map_err(|_| "nonblocking")?; }
        let input_fd: OwnedFd = child_input.into(); let output_fd: OwnedFd = child_output.into();
        check(shared)?;
        let mut cmd = Command::new(&v[0]);
        cmd.env_clear().args(["-I", "-S", "-B", "-c", &source, "--config", &v[3], "--config-sha256", &v[4],
            "--epoch", &hex(&cfg.epoch), "--input-fd", "0", "--output-fd", "1", "--max-commands", "1", "--io-seconds", "5", "--join-seconds", "1"]);
        for (flag, path) in ["sidecar-runtime", "deadline-streams", "runtime-shutdown", "trusted-bootstrap", "import-frames", "stream-dispatcher"].iter().zip(&v[5..]) {
            cmd.arg(format!("--{flag}")).arg(path);
        }
        let mut child = cmd.stdin(Stdio::from(input_fd)).stdout(Stdio::from(output_fd)).stderr(Stdio::null()).spawn().map_err(|_| "spawn")?;
        // Command retains configured Stdio descriptors after spawn. Release
        // the parent copies now, so child exit can produce EOF immediately.
        drop(cmd);
        lock(shared).cleanup_pending = true;
        let exchange = (|| -> Result<()> {
            check(shared)?;
            if identity(Path::new(&v[0]))? != executable { return Err("executable changed"); }
            frame(shared, &mut output, &cfg.epoch, 1, 0)?;
            { let mut s = lock(shared); if s.stop || Instant::now() >= s.deadline { return Err("startup expired"); }
                s.phase = Phase::Checking; s.deadline = Instant::now() + COMMAND; }
            let body = b"{\"version\":1,\"action\":\"status\"}";
            let mut request = header(2, &cfg.epoch, 1, body.len()); request.extend_from_slice(body);
            send(shared, &mut input, &request)?;
            frame(shared, &mut output, &cfg.epoch, 3, 1)?;
            // Count boundary causes graceful shutdown and exit. EOF must follow
            // the sole response, with no trailing bytes and successful exit.
            loop {
                check(shared)?;
                let mut byte = [0u8; 1];
                match output.read(&mut byte) {
                    Ok(0) => break, Ok(_) => return Err("extra frame"),
                    Err(e) if e.kind() == std::io::ErrorKind::WouldBlock => thread::sleep(TICK),
                    Err(e) if e.kind() == std::io::ErrorKind::Interrupted => (), Err(_) => return Err("EOF check"),
                }
            }
            loop {
                check(shared)?;
                match child.try_wait() { Ok(Some(status)) if status.success() => return Ok(()),
                    Ok(Some(_)) | Err(_) => return Err("child failed"), Ok(None) => thread::sleep(TICK) }
            }
        })();
        if exchange.is_err() { fail(shared); let _ = child.kill(); }
        // All post-spawn paths retain the Child and attempt reap, including pin
        // recheck failure. No joins on inherited pipes or child descendants.
        drop(input); drop(output);
        loop {
            match child.try_wait() {
                Ok(Some(_)) => { lock(shared).cleanup_pending = false; break; }
                Ok(None) => { let _ = child.kill(); thread::sleep(TICK); }
                Err(_) => return Err("reap uncertain"),
            }
        }
        exchange?;
        let mut s = lock(shared);
        if s.stop || Instant::now() >= s.deadline { return Err("completion expired"); }
        s.phase = Phase::Complete; Ok(())
    })();
    if result.is_err() { fail(shared); }
}
#[cfg(not(target_os = "linux"))]
fn run(shared: &Shared, _: Config) { fail(shared); }

#[cfg(test)]
mod tests {
    use super::*;
    #[test] fn public_expiry_and_completed_snapshot() {
        for phase in [Phase::Starting, Phase::Checking, Phase::Complete] {
            let probe = ImportStatus { shared: Arc::new(Shared { state: Mutex::new(State { phase, stop: false,
                deadline: Instant::now() - Duration::from_secs(1), cleanup_pending: false }) }), worker: Mutex::new(None) };
            let value = probe.status_json();
            assert!(value.contains(if phase == Phase::Complete { "\"probe_state\":\"complete\"" } else { "\"probe_state\":\"unavailable\"" }));
        }
    }
    #[test] fn absent_is_disabled_partial_refused() {
        assert!(config(std::array::from_fn(|_| None)).unwrap().is_none());
        let mut v = std::array::from_fn(|_| None); v[0] = Some("/python".into()); assert!(config(v).is_err());
    }
    #[test] fn paths_are_normalized() {
        for p in ["x", "/a/../b", "/a//b", "/a/./b", "/a/", "/a\nb"] { assert!(!absolute(p)); }
        assert!(absolute("/trusted/python"));
    }
    #[test] fn exact_v2_identity_and_bounds() {
        let epoch = [7; 16];
        for (kind, ticket, n) in [(1, 0, 48), (3, 1, 4096)] {
            let h: [u8; 40] = header(kind, &epoch, ticket, n).try_into().unwrap();
            assert_eq!(extent(&h, &epoch, kind, ticket), Ok(n));
            assert!(extent(&h, &[8; 16], kind, ticket).is_err());
        }
        for (kind, ticket, n) in [(1, 0, 47), (3, 1, 4097), (3, 1, 0), (3, 2, 1)] {
            let h = header(kind, &epoch, ticket, n).try_into().unwrap(); assert!(extent(&h, &epoch, kind, ticket).is_err());
        }
    }
}

#[cfg(all(test, target_os = "linux"))]
mod adversarial_tests {
    use super::*;
    use std::{io::Cursor, os::unix::net::UnixStream};
    fn shared(ms: u64) -> Shared {
        Shared { state: Mutex::new(State { phase: Phase::Checking, stop: false,
            deadline: Instant::now()+Duration::from_millis(ms), cleanup_pending: false }) }
    }
    #[test] fn every_header_identity_byte_is_checked() {
        let epoch=[7;16]; let good: [u8;40]=header(3,&epoch,1,1).try_into().unwrap();
        for index in 0..36 { let mut h=good; h[index]^=1; assert!(extent(&h,&epoch,3,1).is_err(),"byte {index}"); }
        for n in [0,4097,u32::MAX as usize] { let h=header(3,&epoch,1,n).try_into().unwrap(); assert!(extent(&h,&epoch,3,1).is_err()); }
    }
    #[test] fn every_truncated_ready_fails_closed() {
        let epoch=[7;16]; let mut bytes=header(1,&epoch,0,48); bytes.extend_from_slice(&[0;48]);
        for n in 0..bytes.len() { assert!(frame(&shared(1000),&mut Cursor::new(&bytes[..n]),&epoch,1,0).is_err(),"length {n}"); }
        assert!(frame(&shared(1000),&mut Cursor::new(bytes),&epoch,1,0).is_ok());
    }
    #[test] fn payload_bounds_precede_body_read() {
        let epoch=[7;16]; let h=header(3,&epoch,1,u32::MAX as usize);
        let mut stream=Cursor::new(h); assert_eq!(frame(&shared(1000),&mut stream,&epoch,3,1),Err("frame extent"));
        assert_eq!(stream.position(),40);
    }
    #[test] fn frame_does_not_consume_trailing_bytes() {
        let epoch=[7;16];let mut bytes=header(3,&epoch,1,1); bytes.extend_from_slice(b"xy");
        let mut stream=Cursor::new(bytes); frame(&shared(1000),&mut stream,&epoch,3,1).unwrap();
        assert_eq!(stream.position(),41);let mut trailing=[0];assert_eq!(stream.read(&mut trailing).unwrap(),1);assert_eq!(trailing,[b'y']);
    }
    #[test] fn nonblocking_idle_read_deadline_is_terminal() {
        let (mut read,_write)=UnixStream::pair().unwrap();read.set_nonblocking(true).unwrap();
        let s=shared(40);let start=Instant::now();assert_eq!(exact(&s,&mut read,&mut [0]),Err("deadline"));
        assert!(start.elapsed()<Duration::from_secs(2));assert!(lock(&s).stop);assert!(lock(&s).phase==Phase::Unavailable);
    }
    #[test] fn dripped_bytes_do_not_extend_absolute_deadline() {
        let (mut read,mut write)=UnixStream::pair().unwrap();read.set_nonblocking(true).unwrap();write.set_nonblocking(true).unwrap();
        let writer=thread::spawn(move || {for _ in 0..12 {let _=write.write(&[1]);thread::sleep(Duration::from_millis(10));}});
        let s=shared(40);let start=Instant::now();assert_eq!(exact(&s,&mut read,&mut [0;100]),Err("deadline"));
        assert!(start.elapsed()<Duration::from_secs(2));drop(read);writer.join().unwrap();
    }
    #[test] fn backpressured_write_honors_deadline() {
        let (mut write,_read)=UnixStream::pair().unwrap();write.set_nonblocking(true).unwrap();
        let s=shared(40);let start=Instant::now();assert_eq!(send(&s,&mut write,&vec![0;4*1024*1024]),Err("deadline"));
        assert!(start.elapsed()<Duration::from_secs(2));assert!(lock(&s).stop);
    }
    #[test] fn concurrent_stop_and_snapshot_never_report_complete() {
        for _ in 0..64 {
            let probe=Arc::new(ImportStatus {shared:Arc::new(shared(1000)),worker:Mutex::new(None)});
            let other=probe.clone();let stop=thread::spawn(move || other.stop());
            let value=probe.status_json();assert!(!value.contains("\"probe_state\":\"complete\""));stop.join().unwrap();
            assert!(probe.status_json().contains("\"probe_state\":\"stopped\""));assert_eq!(check(&probe.shared),Err("stopped"));
        }
    }
    #[test] fn overdue_snapshot_preserves_pending_cleanup_truth() {
        let s=shared(0);lock(&s).cleanup_pending=true;
        let probe=ImportStatus {shared:Arc::new(s),worker:Mutex::new(None)};
        let value=probe.status_json();assert!(value.contains("\"probe_state\":\"unavailable\""));assert!(value.contains("\"cleanup_pending\":true"));
    }
}

#[cfg(test)]
mod containment_status_tests {
 use super::*;
 #[test] fn all_probe_phases_disclose_containment_limits() {
  for phase in [Phase::Starting,Phase::Checking,Phase::Complete,Phase::Unavailable,Phase::Stopped] {
   let probe=ImportStatus {shared:Arc::new(Shared {state:Mutex::new(State {phase,stop:false,deadline:Instant::now()+Duration::from_secs(5),cleanup_pending:false})}),worker:Mutex::new(None)};
   let json=probe.status_json();
   assert!(json.contains("\"containment_scope\":\"direct_child_only\""));
   assert!(json.contains("\"descendant_containment_verified\":false"));
   assert!(json.contains("\"parent_death_cleanup_verified\":false"));
   assert!(json.contains("\"mutation_enabled\":false"));
  }
 }
}

#[cfg(all(test,target_os="linux"))]
mod pin_open_tests {
 use super::*;
 struct Fixture {dir:PathBuf,path:PathBuf}
 impl Fixture {
  fn new()->Self {let dir=std::env::temp_dir().join(format!("cas-pin-open-{}-{}",std::process::id(),std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos()));fs::create_dir(&dir).unwrap();let path=dir.join("pin");fs::write(&path,b"pinned bytes").unwrap();Self{dir,path}}
 }
 impl Drop for Fixture {fn drop(&mut self){let _=fs::remove_dir_all(&self.dir);}}
 #[test] fn unchanged_opened_file_matches_identity() {let f=Fixture::new();let expected=identity(&f.path).unwrap();assert!(open_pinned(&f.path,expected).is_ok());}
 #[test] fn same_bytes_replacement_is_not_original_object() {
  let f=Fixture::new();let expected=identity(&f.path).unwrap();fs::rename(&f.path,f.dir.join("old")).unwrap();fs::write(&f.path,b"pinned bytes").unwrap();assert!(matches!(open_pinned(&f.path,expected),Err("pin changed")));
 }
 #[test] fn symlink_substitution_refused_at_open() {
  let f=Fixture::new();let expected=identity(&f.path).unwrap();let old=f.dir.join("old");fs::rename(&f.path,&old).unwrap();std::os::unix::fs::symlink(&old,&f.path).unwrap();assert!(matches!(open_pinned(&f.path,expected),Err("pin open")));
 }
 #[test] fn fifo_substitution_does_not_wait_for_writer() {
  use std::os::unix::ffi::OsStrExt;
  let f=Fixture::new();let expected=identity(&f.path).unwrap();fs::rename(&f.path,f.dir.join("old")).unwrap();let name=std::ffi::CString::new(f.path.as_os_str().as_bytes()).unwrap();
  // Own uniquely-created test path only; no process or permission-policy changes.
  assert_eq!(unsafe{libc::mkfifo(name.as_ptr(),0o600)},0);
  let start=Instant::now();assert!(matches!(open_pinned(&f.path,expected),Err("pin identity")));assert!(start.elapsed()<Duration::from_secs(1));
 }
 #[test] fn hardlink_addition_invalidates_pin() {
  let f=Fixture::new();let expected=identity(&f.path).unwrap();fs::hard_link(&f.path,f.dir.join("alias")).unwrap();assert!(matches!(open_pinned(&f.path,expected),Err("pin identity")));
 }
}
