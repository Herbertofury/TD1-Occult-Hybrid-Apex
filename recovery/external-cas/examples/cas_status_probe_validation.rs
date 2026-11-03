#[path = "cas_import_status.rs"]
mod cas_import_status;
fn main() {
 let probe = cas_import_status::ImportStatus::from_env().expect("valid fixture config").expect("enabled fixture");
 let begin = std::time::Instant::now();
 let deadline = std::time::Instant::now() + std::time::Duration::from_secs(35);
 let mut last = String::new();
 let stop_registered=std::env::var_os("CAS_TEST_STOP_REGISTERED").is_some();
 let mut stop_issued=false;
 loop {
  let value = probe.status_json();
  if value != last { eprintln!("state_ms={} {}",begin.elapsed().as_millis(),value); last=value.clone(); }
  if stop_registered && !stop_issued && value.contains("\"cleanup_pending\":true") { probe.stop(); stop_issued=true; eprintln!("stop_requested_ms={}",begin.elapsed().as_millis()); }
  if (value.contains("\"probe_state\":\"unavailable\"") || value.contains("\"probe_state\":\"complete\"") || (stop_issued && value.contains("\"probe_state\":\"stopped\""))) && value.contains("\"cleanup_pending\":false") {
   eprintln!("elapsed_ms={}",begin.elapsed().as_millis()); println!("{}", value); probe.stop(); return;
  }
  if std::time::Instant::now() >= deadline {
   probe.stop(); eprintln!("bounded observation expired: {}",probe.status_json()); std::process::exit(2);
  }
  std::thread::sleep(std::time::Duration::from_millis(10));
 }
}
