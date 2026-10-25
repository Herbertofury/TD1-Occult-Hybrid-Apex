//! Typed CAS PreparePlan storage. All JSON/file work owns its bytes off-owner.
//! A durable receipt is never native-call authority. No game/Python pointers.
use crate::bank_json::{self as j, Node, Value, check, parse, sha};
use rayon::{ThreadPool, ThreadPoolBuilder};
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::{collections::BTreeMap, ffi::{CString,c_char}, fs::{self,OpenOptions}, io::{Read,Write},
    path::{Path,PathBuf}, sync::{Arc,Mutex,OnceLock}, time::Instant};

const MAX_JOBS:usize=4;
const MAX_RETAINED:usize=256;
const MAX_HEADER:usize=4096;
#[derive(Clone,Debug,PartialEq,Eq,Deserialize,Serialize)]
#[serde(deny_unknown_fields)]
pub struct Identity {pub runtime_pid:u32,pub save_guid:String,pub household_id:String,pub sim_id:String}
#[derive(Clone,Debug,PartialEq,Eq,Deserialize,Serialize)]
#[serde(deny_unknown_fields)]
pub struct Request {
    pub request_id:String,pub transaction_id:String,pub identity:Identity,
    pub operation:String,pub sequence:u32,
    pub expected_file_sha256:Option<String>,pub expected_record_sha256:Option<String>,
    pub expected_journal_sha256:Option<String>,pub document_sha256:Option<String>,
}
fn hash(s:&str)->bool {s.len()==64 && s.bytes().all(|c|c.is_ascii_digit() || (b'a'..=b'f').contains(&c))}
fn token(s:&str)->bool {s.len()==32 && s.bytes().all(|c|c.is_ascii_digit() || (b'a'..=b'f').contains(&c))}
impl Request {
    fn validate(&self)->j::Result<()> {
        check(token(&self.request_id)&&token(&self.transaction_id),"Exact request/transaction UUID required")?;
        check(self.identity.runtime_pid>0 && [&self.identity.save_guid,&self.identity.household_id,&self.identity.sim_id].iter().all(|v|j::id(v)),"Exact runtime/save/household/Sim required")?;
        check(matches!(self.operation.as_str(),"read-selected"|"plan-base"|"plan-hair"|"plan-named"),"Typed PreparePlan operation required")?;
        if self.operation=="read-selected" {check(self.sequence==0 && self.expected_file_sha256.is_none() && self.expected_record_sha256.is_none() && self.expected_journal_sha256.is_none() && self.document_sha256.is_none(),"Read accepts no replacement evidence")?;}
        else {check(self.sequence>0 && [&self.expected_file_sha256,&self.expected_record_sha256,&self.expected_journal_sha256,&self.document_sha256].iter().all(|v|v.as_ref().is_some_and(|v|hash(v))),"Prepare requires all exact predecessor hashes")?;}
        Ok(())
    }
    fn key(&self)->String {format!("{}:{}",self.identity.save_guid,self.identity.sim_id)}
}

fn encoded_string(units:&[u16])->Vec<u8> {
    let mut out=vec![b'"'];
    for &c in units {match c {34=>out.extend_from_slice(b"\\\""),92=>out.extend_from_slice(b"\\\\"),8=>out.extend_from_slice(b"\\b"),9=>out.extend_from_slice(b"\\t"),10=>out.extend_from_slice(b"\\n"),12=>out.extend_from_slice(b"\\f"),13=>out.extend_from_slice(b"\\r"),32..=126=>out.push(c as u8),_=>out.extend_from_slice(format!("\\u{c:04x}").as_bytes())}}
    out.push(b'"');out
}
fn sort_key(units:&[u16])->Vec<u32> {std::char::decode_utf16(units.iter().copied()).map(|r|r.map_or_else(|e|u32::from(e.unpaired_surrogate()),u32::from)).collect()}
fn canonical_number(raw:&[u8])->Vec<u8> {
    // JSON's integer/float distinction survives decoding. In particular, do
    // not round arbitrary-size integers through binary64; only integer -0
    // changes spelling when CPython decodes it to int zero.
    if !raw.iter().any(|b|matches!(b,b'.'|b'e'|b'E')) {
        return if raw==b"-0" {b"0".to_vec()} else {raw.to_vec()};
    }
    // The strict scanner already required one finite correctly rounded f64.
    // serde_json's pinned zmij formatter chooses nearest shortest digits with
    // ties to even. Rust Debug chooses different digits for some exact ties;
    // changing its exponent typography alone is NOT Python-compatible.
    let value=std::str::from_utf8(raw).expect("validated ASCII number")
        .parse::<f64>().expect("validated binary64 number");
    assert!(value.is_finite(),"strict scanner must reject nonfinite numbers");
    let shortest=serde_json::to_string(&value).expect("finite binary64 formatter");
    let sign=if value.is_sign_negative(){"-"}else{""};
    if value==0.0{return format!("{sign}0.0").into_bytes()}
    let unsigned=shortest.strip_prefix('-').unwrap_or(&shortest);
    let (mantissa,exponent)=unsigned.split_once('e').map_or((unsigned,0),|(m,e)|(m,e.parse::<i32>().expect("formatter exponent")));
    let mut point=mantissa.find('.').unwrap_or(mantissa.len()) as i32+exponent;
    let digits:Vec<u8>=mantissa.bytes().filter(|&b|b!=b'.').collect();
    let begin=digits.iter().position(|&b|b!=b'0').expect("nonzero shortest digits");
    let end=digits.iter().rposition(|&b|b!=b'0').unwrap()+1;
    point-=begin as i32;
    let digits=std::str::from_utf8(&digits[begin..end]).unwrap();
    let exp=point-1;
    let mut out=String::from(sign);
    // CPython 3.7 repr/JSON uses scientific notation below 1e-4 and at 1e16,
    // includes an exponent sign and at least two exponent digits, and retains
    // .0 for integral floating-point values rendered in fixed notation.
    if !(-4..16).contains(&exp) {
        out.push_str(&digits[..1]);
        if digits.len()>1 {out.push('.');out.push_str(&digits[1..]);}
        out.push_str(&format!("e{exp:+03}"));
    } else if point<=0 {
        out.push_str("0.");out.push_str(&"0".repeat((-point) as usize));out.push_str(digits);
    } else if point as usize>=digits.len() {
        out.push_str(digits);out.push_str(&"0".repeat(point as usize-digits.len()));out.push_str(".0");
    } else {
        out.push_str(&digits[..point as usize]);out.push('.');out.push_str(&digits[point as usize..]);
    }
    out.into_bytes()
}
fn canonical(raw:&[u8],node:&Node)->Vec<u8> {
    match &node.value {
        Value::Object(rows)=>{let mut ordered=rows.iter().collect::<Vec<_>>();ordered.sort_by_key(|(k,_)|sort_key(k));let mut out=vec![b'{'];for (i,(k,v)) in ordered.iter().enumerate(){if i>0{out.push(b',')}out.extend(encoded_string(k));out.push(b':');out.extend(canonical(raw,v));}out.push(b'}');out},
        Value::Array(rows)=>{let mut out=vec![b'['];for(i,v)in rows.iter().enumerate(){if i>0{out.push(b',')}out.extend(canonical(raw,v));}out.push(b']');out},
        Value::String(s)=>encoded_string(s),Value::Number=>canonical_number(&raw[node.span.clone()]),_=>raw[node.span.clone()].to_vec()
    }
}
fn field<'a>(node:&'a Node,name:&str)->j::Result<&'a Node>{node.field(name).ok_or_else(||format!("Missing exact {name}"))}
fn equal(raw:&[u8],a:&Node,other:&[u8],b:&Node)->bool {canonical(raw,a)==canonical(other,b)}
fn regular(path:&Path,directory:bool)->j::Result<()> {
    let m=fs::symlink_metadata(path).map_err(|e|e.to_string())?;
    check(!m.file_type().is_symlink() && if directory{m.is_dir()}else{m.is_file()},"Regular non-symlink bank path required")?;
    #[cfg(windows)] {use std::os::windows::fs::MetadataExt;check(m.file_attributes()&0x400==0,"Windows reparse point refused")?;}
    Ok(())
}
fn read_bank(path:&Path)->j::Result<Vec<u8>> {
    regular(path,false)?;let mut file=std::fs::File::open(path).map_err(|e|e.to_string())?;
    let before=file.metadata().map_err(|e|e.to_string())?;
    check(before.len()>0&&before.len()<=j::MAX_DOCUMENT as u64,"Complete bank exceeds explicit bound")?;
    let mut raw=Vec::new();Read::by_ref(&mut file).take(j::MAX_DOCUMENT as u64+1).read_to_end(&mut raw).map_err(|e|e.to_string())?;
    let after=file.metadata().map_err(|e|e.to_string())?;
    check(raw.len()<=j::MAX_DOCUMENT && raw.len()==before.len() as usize && before.len()==after.len() && before.modified().ok()==after.modified().ok(),"Bank changed during complete read")?;
    parse(&raw)?;Ok(raw)
}
fn selected<'a>(raw:&[u8],node:&'a Node,req:&Request)->j::Result<&'a Node>{
    check(&raw[field(node,"schema")?.span.clone()]==b"1","Exact bank schema1 required")?;
    let record=field(field(node,"records")?,&req.key())?;record.members()?;
    let tx=field(record,"cas_transaction")?;
    check(field(tx,"transaction_id")?.string_eq(&req.transaction_id),"Transaction UUID differs")?;
    let id=field(tx,"identity")?;
    for (key,wanted) in [("save_guid",&req.identity.save_guid),("household_id",&req.identity.household_id),("sim_id",&req.identity.sim_id)] {check(field(id,key)?.string_eq(wanted),"Native save/household/Sim identity differs")?;}
    check(&raw[field(id,"runtime_pid")?.span.clone()]==req.identity.runtime_pid.to_string().as_bytes(),"Native runtime differs")?;
    check(record.field("switch_pending").is_none_or(|n|matches!(n.value,Value::Null)),"Foreign switch WAL retained")?;
    check(record.field("automatic_cas_preservation_failure").is_none_or(|n|matches!(n.value,Value::Null)),"Household recovery retained")?;
    check(!matches!(field(record,"pending")?.value,Value::Null),"CAS pending checkpoint was consumed")?;
    Ok(record)
}
fn patch(raw:&[u8],req:&Request,document:&[u8])->j::Result<Vec<u8>> {
    req.validate()?;let whole=parse(raw)?;let record=selected(raw,&whole,req)?;
    check(Some(sha(raw))==req.expected_file_sha256,"Whole bank revision differs")?;
    check(Some(sha(&raw[record.span.clone()]))==req.expected_record_sha256,"Selected record revision differs")?;
    let tx=field(record,"cas_transaction")?;let before=field(tx,"journal")?;
    check(Some(sha(&canonical(raw,before)))==req.expected_journal_sha256,"Exact journal predecessor differs")?;
    let after=parse(document)?;check(Some(sha(&canonical(document,&after)))==req.document_sha256,"Complete journal input differs")?;
    let planned=field(&after,"state")?.string_eq("planned");check(planned,"Prepare cannot issue native writes")?;
    let prior_state=field(before,"state")?;
    check(if req.operation=="plan-base" {prior_state.string_eq("observed")}else{prior_state.string_eq("planned")},"Skipped or repeated PreparePlan barrier")?;
    check(field(&after,"native_write_attempted")?.value==Value::Bool(false),"Prepare cannot claim a native attempt")?;
    let reviewed=|key:&[u16]|["state","plan","plan_sha256"].iter().any(|name|key.iter().copied().eq(name.encode_utf16()));
    for (key,value) in before.members()? {
        if !reviewed(key) {let wanted=after.members()?.iter().find(|(k,_)|k==key).map(|(_,v)|v).ok_or("Unreviewed journal field removed")?;check(equal(raw,value,document,wanted),"Unreviewed journal field changed")?;}
    }
    for (key,_) in after.members()? {check(before.members()?.iter().any(|(k,_)|k==key)||reviewed(key),"Unreviewed journal field inserted")?;}
    let plan=field(&after,"plan")?;
    check(field(&after,"plan_sha256")?.string_eq(&sha(&canonical(document,plan))),"Plan hash differs")?;
    for name in ["identity","pending_sha256","raw_return_sha256","pre_write_owners_sha256"] {
        check(equal(document,field(plan,name)?,raw,field(before,name)?),"Plan before-image/identity differs")?;
    }
    let originals=field(field(before,"original_owners")?,"stored")?;
    let returned=field(field(before,"raw_return")?,"stored")?;
    let desired=field(plan,"desired")?;
    let same_keys=|a:&Node,b:&Node|->j::Result<bool>{let aa=a.members()?;let bb=b.members()?;Ok(aa.len()==bb.len()&&aa.iter().all(|(k,_)|bb.iter().any(|(other,_)|other==k)))};
    check(same_keys(originals,desired)?&&same_keys(originals,returned)?,"Plan omitted or added a complete appearance owner")?;
    for (lane,fields) in originals.members()? {
        let planned=desired.members()?.iter().find(|(key,_)|key==lane).map(|(_,value)|value).ok_or("Desired owner missing")?;
        let observed=returned.members()?.iter().find(|(key,_)|key==lane).map(|(_,value)|value).ok_or("Returned owner missing")?;
        check(same_keys(fields,planned)?&&same_keys(fields,observed)?,"Complete captured appearance field coverage differs")?;
    }
    if req.operation=="plan-hair" {check(field(field(tx,"hair_checkpoint")?,"enabled")?.value==Value::Bool(true),"Hair barrier requires enabled policy")?;field(plan,"hair_policy_contract")?;}
    if req.operation=="plan-named" {check(field(tx,"native_owner_return_required")?.value==Value::Bool(true),"Named barrier requires captured native graph")?;for n in ["native_owner_return_sha256","named_document_sha256","named_dispositions"]{field(plan,n)?;}}
    // Patch only the three reviewed journal values and transaction phase.
    // In particular, unknown journal values/formatting are never reserialized.
    let mut changes=vec![(field(tx,"phase")?.span.clone(),b"\"planned\"".to_vec())];
    let mut additions=Vec::new();
    for name in ["state","plan","plan_sha256"] {
        let value=field(&after,name)?;let bytes=document[value.span.clone()].to_vec();
        if let Some(old)=before.field(name){changes.push((old.span.clone(),bytes));}
        else {additions.push(b',');additions.extend(encoded_string(&name.encode_utf16().collect::<Vec<_>>()));additions.push(b':');additions.extend(bytes);}
    }
    if !additions.is_empty(){let end=before.span.end-1;changes.push((end..end,additions));}
    changes.sort_by_key(|(span,_)|span.start);
    let mut out=Vec::with_capacity(raw.len()+document.len());let mut at=0;for(span,value)in changes{out.extend_from_slice(&raw[at..span.start]);out.extend(value);at=span.end;}out.extend_from_slice(&raw[at..]);
    let final_node=parse(&out)?;let final_record=selected(&out,&final_node,req)?;
    let final_journal=field(field(final_record,"cas_transaction")?,"journal")?;
    check(Some(sha(&canonical(&out,final_journal)))==req.document_sha256,"Complete patched journal differs from exact requested document")?;
    Ok(out)
}

#[derive(Clone,Copy,Debug,Default,PartialEq,Eq)]
pub enum Fault {#[default] None,BeforeWrite,AfterSync,AfterReplace,LostReceipt}
struct Lease {path:PathBuf,raw:Vec<u8>,keep:bool}
impl Lease {
    fn take(root:&Path,req:&Request)->j::Result<Self>{let path=root.join(".form_bank.json.cas-writer.lock");let raw=serde_json::to_vec(&json!({"schema":1,"pid":req.identity.runtime_pid,"token":req.request_id})).map_err(|e|e.to_string())?;let mut f=OpenOptions::new().write(true).create_new(true).open(&path).map_err(|_|"Existing writer lease retained")?;f.write_all(&raw).and_then(|_|f.sync_all()).map_err(|e|e.to_string())?;Ok(Self{path,raw,keep:false})}
    fn verify(&self)->j::Result<()> {regular(&self.path,false)?;check(fs::read(&self.path).map_err(|e|e.to_string())?==self.raw,"Writer lease changed")}
}
impl Drop for Lease {fn drop(&mut self){if !self.keep&&self.verify().is_ok(){let _=fs::remove_file(&self.path);}}}
fn receipt(raw:&[u8],req:&Request,worker_ms:f64)->j::Result<String> {
    let node=parse(raw)?;let record=selected(raw,&node,req)?;let tx=field(record,"cas_transaction")?;
    let mut meta=serde_json::to_string(&json!({"ok":true,"state":"ready","request_id":req.request_id,"transaction_id":req.transaction_id,"sequence":req.sequence,"identity":req.identity,"file_sha256":sha(raw),"record_sha256":sha(&raw[record.span.clone()]),"journal_sha256":sha(&canonical(raw,field(tx,"journal")?)),"durable":req.operation!="read-selected","native_call_authorized":false,"worker_ms":worker_ms})).map_err(|e|e.to_string())?;
    meta.pop();meta.push_str(",\"record\":");meta.push_str(std::str::from_utf8(&raw[record.span.clone()]).map_err(|e|e.to_string())?);meta.push('}');Ok(meta)
}
fn perform(root:&Path,req:&Request,payload:&[u8],fault:Fault)->j::Result<String>{
    req.validate()?;for p in root.ancestors(){regular(p,true)?;}let path=root.join("form_bank.json");let started=Instant::now();
    if req.operation=="read-selected" {check(payload.is_empty(),"Read cannot carry replacement bytes")?;let raw=read_bank(&path)?;return receipt(&raw,req,started.elapsed().as_secs_f64()*1000.0);}
    let mut lease=Lease::take(root,req)?;lease.verify()?;let before=read_bank(&path)?;let after=patch(&before,req,payload)?;
    check(fault!=Fault::BeforeWrite,"Injected before-write failure")?;
    let pending=root.join("form_bank.pending");let mut f=OpenOptions::new().write(true).create_new(true).open(&pending).map_err(|_|"Pending evidence already exists")?;
    // Once our candidate exists, retain the shared lease on EVERY failure.
    // Legacy participating writers must not overwrite even pre-replace evidence.
    lease.keep=true;
    f.write_all(&after).and_then(|_|f.sync_all()).map_err(|e|e.to_string())?;drop(f);check(fault!=Fault::AfterSync,"Injected after-sync failure")?;lease.verify()?;
    check(sha(&read_bank(&path)?)==sha(&before),"Bank changed before replacement")?;
    fs::rename(&pending,&path).map_err(|e|e.to_string())?;lease.keep=true;
    #[cfg(not(windows))] {std::fs::File::open(root).and_then(|d|d.sync_all()).map_err(|e|e.to_string())?;}
    check(fault!=Fault::AfterReplace,"Injected after-replacement failure")?;
    let observed=read_bank(&path)?;check(observed==after,"Complete durable readback differs")?;lease.verify()?;
    check(fault!=Fault::LostReceipt,"Injected lost receipt")?;let result=receipt(&observed,req,started.elapsed().as_secs_f64()*1000.0)?;lease.keep=false;Ok(result)
}

struct Job {request:Request,payload_sha:Option<String>,file_sha:Option<String>,result:Option<Arc<String>>}
#[derive(Default)]struct State {next:u64,inflight:usize,jobs:BTreeMap<u64,Job>}
pub struct Worker {root:PathBuf,pool:ThreadPool,state:Arc<Mutex<State>>,writer:Arc<Mutex<()>>}
fn pin_own_module()->j::Result<()> {
    #[cfg(windows)] {
        use std::ffi::c_void;
        #[link(name="kernel32")]
        unsafe extern "system" {fn GetModuleHandleExW(flags:u32,address:*const u16,module:*mut *mut c_void)->i32;}
        static PIN:OnceLock<j::Result<()>>=OnceLock::new();
        return PIN.get_or_init(||{
            let mut module=std::ptr::null_mut();
            // Resolve OUR executable address. An untrusted ABI caller cannot
            // supply a foreign HMODULE or release code still running on Rayon.
            let address=ApexBankBind as *const () as *const u16;
            let ok=unsafe{GetModuleHandleExW(0x00000004|0x00000001,address,&mut module)};
            check(ok!=0&&!module.is_null(),"Could not lifetime-pin the worker's own module")
        }).clone();
    }
    #[cfg(not(windows))] {Ok(())}
}
impl Worker {
    pub fn open(root:PathBuf)->j::Result<Self>{Self::open_after_pin(root,pin_own_module)}
    fn open_after_pin(root:PathBuf,pin:impl FnOnce()->j::Result<()>)->j::Result<Self>{check(root.is_absolute(),"Absolute authenticated root required")?;pin()?;Ok(Self{root,pool:ThreadPoolBuilder::new().num_threads(2).build().map_err(|e|e.to_string())?,state:Arc::new(Mutex::new(State::default())),writer:Arc::new(Mutex::new(()))})}
    pub fn submit(&self,req:Request,payload:Vec<u8>,fault:Fault)->j::Result<u64>{
        req.validate()?;check(payload.len()<=j::MAX_DOCUMENT,"Bounded immutable journal required")?;
        let mut state=self.state.lock().map_err(|_|"Worker state unavailable")?;
        // Exact UUID+sequence retains its original ticket and adopts no replacement input.
        for (&ticket,job) in &state.jobs {if job.request.request_id==req.request_id&&job.request.sequence==req.sequence {check(job.request==req,"UUID context/phase changed")?;return Ok(ticket)}}
        check(state.inflight<MAX_JOBS && state.jobs.len()<MAX_RETAINED,"Worker capacity retained; no accepted job evicted")?;
        if req.sequence>0 {let prior=state.jobs.values().find(|j|j.request.request_id==req.request_id&&j.request.sequence==req.sequence-1).ok_or("No exact preceding worker phase")?;check(prior.request.transaction_id==req.transaction_id&&prior.request.identity==req.identity,"Phase context changed")?;check(prior.result.is_some(),"Prior phase still pending")?;check(prior.file_sha.is_some() && prior.file_sha==req.expected_file_sha256,"Prior durable receipt differs")?;}
        state.next+=1;let ticket=state.next;state.inflight+=1;state.jobs.insert(ticket,Job{request:req.clone(),payload_sha:None,file_sha:None,result:None});drop(state);
        let state=Arc::clone(&self.state);let writer=Arc::clone(&self.writer);let root=self.root.clone();
        self.pool.spawn_fifo(move||{let result=std::panic::catch_unwind(||{let _lane=writer.lock().map_err(|_|"Writer lane unavailable")?;perform(&root,&req,&payload,fault)});let result=match result{Ok(Ok(v))=>v,Ok(Err(e))=>json!({"ok":false,"state":"failed","message":e,"outcome_may_be_durable":true,"native_call_authorized":false}).to_string(),Err(_)=>json!({"ok":false,"state":"failed","message":"Worker panic retained","outcome_may_be_durable":true,"native_call_authorized":false}).to_string()};let payload_sha=sha(&payload);let file_sha=parse(result.as_bytes()).ok().and_then(|node|node.field("file_sha256").and_then(|n|if let Value::String(s)=&n.value{String::from_utf16(s).ok()}else{None}));let result=Arc::new(result);if let Ok(mut s)=state.lock(){s.inflight-=1;if let Some(job)=s.jobs.get_mut(&ticket){job.payload_sha=Some(payload_sha);job.file_sha=file_sha;job.result=Some(result);}}});Ok(ticket)
    }
    pub fn poll(&self,req:&Request,ticket:u64)->j::Result<Arc<String>>{let state=self.state.lock().map_err(|_|"Worker state unavailable")?;let job=state.jobs.get(&ticket).ok_or("Unknown retained ticket")?;check(job.request==*req,"Poll context differs")?;Ok(job.result.clone().unwrap_or_else(||Arc::new("{\"ok\":true,\"state\":\"pending\"}".into())))}
}

fn registry()->&'static Mutex<BTreeMap<u64,Arc<Worker>>>{static VALUE:OnceLock<Mutex<BTreeMap<u64,Arc<Worker>>>>=OnceLock::new();VALUE.get_or_init(||Mutex::new(BTreeMap::new()))}
/// # Safety
/// Root must be caller-authenticated UTF-8, readable for length bytes during this call.
#[unsafe(no_mangle)]pub unsafe extern "C" fn ApexBankBind(root:*const u8,length:usize)->u64{
    std::panic::catch_unwind(||->j::Result<u64>{check(!root.is_null()&&length>0&&length<=32768,"Bounded root required")?;let root=std::str::from_utf8(unsafe{std::slice::from_raw_parts(root,length)}).map_err(|_|"Root UTF-8 invalid")?;let worker=Arc::new(Worker::open(PathBuf::from(root))?);let mut r=registry().lock().map_err(|_|"Worker registry failed")?;check(r.len()<4,"Runtime root capacity full")?;let id=r.keys().next_back().copied().unwrap_or(0)+1;r.insert(id,worker);Ok(id)}).ok().and_then(Result::ok).unwrap_or(0)
}
/// # Safety
/// Complete inputs are copied before returning. Header is bounded primitive JSON.
#[unsafe(no_mangle)]pub unsafe extern "C" fn ApexBankSubmit(handle:u64,header:*const u8,header_len:usize,payload:*const u8,payload_len:usize)->u64 {
    std::panic::catch_unwind(||->j::Result<u64>{check(!header.is_null()&&header_len>0&&header_len<=MAX_HEADER&&payload_len<=j::MAX_DOCUMENT&&(!payload.is_null()||payload_len==0),"Invalid ABI bounds")?;let req:Request=serde_json::from_slice(unsafe{std::slice::from_raw_parts(header,header_len)}).map_err(|_|"Invalid typed header")?;let worker=registry().lock().map_err(|_|"Worker registry unavailable")?.get(&handle).cloned().ok_or("Unknown root capability")?;let raw=if payload_len==0{Vec::new()}else{unsafe{std::slice::from_raw_parts(payload,payload_len)}.to_vec()};worker.submit(req,raw,Fault::None)}).ok().and_then(Result::ok).unwrap_or(0)
}
/// # Safety
/// Header is readable bounded primitive JSON. Free returned allocation exactly once.
#[unsafe(no_mangle)]pub unsafe extern "C" fn ApexBankPoll(handle:u64,header:*const u8,length:usize,ticket:u64)->*mut c_char {
    let result=std::panic::catch_unwind(||->j::Result<Arc<String>>{check(!header.is_null()&&length>0&&length<=MAX_HEADER,"Invalid poll header")?;let req:Request=serde_json::from_slice(unsafe{std::slice::from_raw_parts(header,length)}).map_err(|_|"Invalid poll context")?;let worker=registry().lock().map_err(|_|"Worker registry unavailable")?.get(&handle).cloned().ok_or("Unknown root capability")?;worker.poll(&req,ticket)}).ok().and_then(Result::ok).unwrap_or_else(||Arc::new("{\"ok\":false,\"state\":\"failed\",\"message\":\"Unverified bank ticket/context\"}".into()));CString::new(result.as_bytes()).map_or(std::ptr::null_mut(),CString::into_raw)
}
/// # Safety
/// Argument is null or an unfreed ApexBankPoll allocation, exactly once.
#[unsafe(no_mangle)]pub unsafe extern "C" fn ApexBankFree(value:*mut c_char){if !value.is_null(){drop(unsafe{CString::from_raw(value)});}}

thread_local! {static LAST_POLL:std::cell::RefCell<Option<CString>>=const{std::cell::RefCell::new(None)};}
/// # Safety
/// Same bounded header contract as Poll. Result is valid until the next call
/// on THIS caller thread. The game's low-level _ctypes String copies it before
/// returning to Python; it must never be freed or retained as a borrowed pointer.
#[unsafe(no_mangle)]pub unsafe extern "C" fn ApexBankPollCopy(handle:u64,header:*const u8,length:usize,ticket:u64)->*const c_char {
    let raw=unsafe{ApexBankPoll(handle,header,length,ticket)};
    if raw.is_null(){return std::ptr::null()}
    let owned=unsafe{CString::from_raw(raw)};
    LAST_POLL.with(|slot|{*slot.borrow_mut()=Some(owned);slot.borrow().as_ref().map_or(std::ptr::null(),|value|value.as_ptr())})
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicU64,Ordering};
    static NEXT:AtomicU64=AtomicU64::new(1);
    #[test]fn module_pin_failure_refuses_before_constructing_workers(){
        let root=std::env::temp_dir().join("apex-pin-refusal-never-opened");
        assert!(Worker::open_after_pin(root,||Err("injected own-module pin refusal".into())).err().unwrap().contains("pin refusal"));
    }
    #[test]fn python37_numeric_canonical_vectors_preserve_json_number_types_and_shortest_even_ties(){
        for (raw,wanted) in [("-0","0"),("-0.00","-0.0"),("1e+03","1000.0"),("1000.00","1000.0"),
            ("1.00000E+0003","1000.0"),("1e-5","1e-05"),("1e-4","0.0001"),("1e15","1000000000000000.0"),
            ("1e16","1e+16"),("1e-400","0.0"),("-1e-400","-0.0"),("5e-324","5e-324"),
            ("2.4703282292062327e-324","0.0"),("2.4703282292062328e-324","5e-324"),
            ("1.7976931348623157e308","1.7976931348623157e+308"),("9007199254740993","9007199254740993"),
            ("9007199254740993.0","9007199254740992.0"),("1000000000000000128.0","1.0000000000000001e+18"),
            ("-134338078858785.625","-134338078858785.62"),("1556276550665566.25","1556276550665566.2"),
            ("1.00000000000000011102230246251565404236316680908203125","1.0"),
            ("1.00000000000000033306690738754696212708950042724609375","1.0000000000000004")]{
            let node=parse(raw.as_bytes()).unwrap();assert_eq!(canonical(raw.as_bytes(),&node),wanted.as_bytes(),"{raw}");
        }
        for sign in ["","-"] {let integer=format!("{sign}{}","9".repeat(5000));assert_eq!(canonical_number(integer.as_bytes()),integer.as_bytes());}
    }
    #[test]fn actual_private_python37_numeric_oracle_corpus_matches_every_canonical_byte(){
        let Ok(path)=std::env::var("APEX_PY37_NUMBER_ORACLE")else{return};
        let rows=fs::read_to_string(path).unwrap();let mut count=0;
        for line in rows.trim_start_matches('\u{feff}').lines(){let row:serde_json::Value=serde_json::from_str(line).unwrap();let raw=row["lexeme"].as_str().unwrap().as_bytes();let wanted=row["canonical"].as_str().unwrap().as_bytes();let node=parse(raw).unwrap();assert_eq!(canonical(raw,&node),wanted,"Oracle numeric row {count}");count+=1;}
        assert!(count>80000,"Actual CPython 3.7 corpus was not supplied");
    }
    struct Temp(PathBuf);
    impl Temp {fn new()->Self{let path=std::env::temp_dir().join(format!("apex-prepare-test-{}-{}",std::process::id(),NEXT.fetch_add(1,Ordering::Relaxed)));fs::create_dir(&path).unwrap();Self(path)}}
    impl Drop for Temp {fn drop(&mut self){assert!(self.0.starts_with(std::env::temp_dir()));let _=fs::remove_dir_all(&self.0);}}
    fn read_request()->Request {Request{request_id:"a".repeat(32),transaction_id:"b".repeat(32),identity:Identity{runtime_pid:std::process::id(),save_guid:"30".into(),household_id:"20".into(),sim_id:"10".into()},operation:"read-selected".into(),sequence:0,expected_file_sha256:None,expected_record_sha256:None,expected_journal_sha256:None,document_sha256:None}}
    fn initial(req:&Request)->Vec<u8>{
        let fields=json!({"physique":{"kind":"value","value":"original"},"__outfits__":{"kind":"protobuf","value":"CAA="}});
        let journal=json!({"schema":1,"state":"observed","identity":req.identity,"pending_sha256":"c".repeat(64),"raw_return_sha256":"d".repeat(64),"pre_write_owners_sha256":"e".repeat(64),"original_owners":{"stored":{"1":fields.clone()}},"raw_return":{"stored":{"1":fields}},"native_write_attempted":false,"bank_committed":false,"unknown":[7,8]});
        let record=json!({"pending":{"originals":"kept"},"unknown":{"nested":[1,2]},"cas_transaction":{"transaction_id":req.transaction_id,"identity":req.identity,"journal":journal,"phase":"observed","hair_checkpoint":{"enabled":true},"native_owner_return_required":true}});
        let mut raw=serde_json::to_vec(&json!({"schema":1,"records":{"30:10":record,"30:99":{"unknown":"foreign"}}})).unwrap();
        // Unknown raw numeric spelling/surrogates outside the selected patch
        // must survive without serde_json Value conversion.
        raw.pop();raw.extend_from_slice(br#", "unknown": [1e+03,184467440737095516160,-0.00,"\ud800"] }"#);raw
    }
    fn prepare(req:&Request,raw:&[u8])->(Request,Vec<u8>){
        let whole=parse(raw).unwrap();let selected=selected(raw,&whole,req).unwrap();let tx=field(selected,"cas_transaction").unwrap();let prior=field(tx,"journal").unwrap();
        let mut doc:serde_json::Value=serde_json::from_slice(&raw[prior.span.clone()]).unwrap();
        let plan=json!({"schema":1,"identity":req.identity,"pending_sha256":"c".repeat(64),"raw_return_sha256":"d".repeat(64),"pre_write_owners_sha256":"e".repeat(64),"desired":doc["original_owners"]["stored"].clone(),"hair_targets":{},"active_lane":"1","dispositions":[],"changed_lanes":[],"accepted_lanes":[],"automatic_intent_classification":false});
        let p=serde_json::to_vec(&plan).unwrap();doc["state"]="planned".into();doc["plan"]=plan;doc["plan_sha256"]=sha(&canonical(&p,&parse(&p).unwrap())).into();
        let payload=serde_json::to_vec(&doc).unwrap();let request=Request{operation:"plan-base".into(),sequence:1,expected_file_sha256:Some(sha(raw)),expected_record_sha256:Some(sha(&raw[selected.span.clone()])),expected_journal_sha256:Some(sha(&canonical(raw,prior))),document_sha256:Some(sha(&canonical(&payload,&parse(&payload).unwrap()))),..req.clone()};(request,payload)
    }
    fn wait(worker:&Worker,req:&Request,ticket:u64)->Arc<String>{let deadline=Instant::now()+std::time::Duration::from_secs(5);loop{let result=worker.poll(req,ticket).unwrap();if !result.contains("\"state\":\"pending\""){return result}assert!(Instant::now()<deadline);std::thread::sleep(std::time::Duration::from_millis(1));}}

    #[test]fn typed_prepare_changes_only_reviewed_journal_phase_and_keeps_unknown_other_bytes(){
        let req=read_request();let raw=initial(&req);let(plan,payload)=prepare(&req,&raw);let after=patch(&raw,&plan,&payload).unwrap();
        let before_node=parse(&raw).unwrap();let after_node=parse(&after).unwrap();
        for name in ["unknown","schema"]{assert_eq!(canonical(&raw,field(&before_node,name).unwrap()),canonical(&after,field(&after_node,name).unwrap()));}
        let b=field(field(&before_node,"records").unwrap(),"30:99").unwrap();let a=field(field(&after_node,"records").unwrap(),"30:99").unwrap();assert_eq!(&raw[b.span.clone()],&after[a.span.clone()]);
        assert!(after.windows(br#"1e+03,184467440737095516160,-0.00,"\ud800""#.len()).any(|w|w==br#"1e+03,184467440737095516160,-0.00,"\ud800""#));
    }
    #[test]fn unknown_changed_field_wrong_revision_and_skipped_barrier_are_refused(){
        let req=read_request();let raw=initial(&req);let(plan,payload)=prepare(&req,&raw);
        let mut wrong=plan.clone();wrong.expected_file_sha256=Some("0".repeat(64));assert!(patch(&raw,&wrong,&payload).is_err());
        let mut doc:serde_json::Value=serde_json::from_slice(&payload).unwrap();doc["original_owners"]="discarded".into();let forged=serde_json::to_vec(&doc).unwrap();wrong=plan.clone();wrong.document_sha256=Some(sha(&canonical(&forged,&parse(&forged).unwrap())));assert!(patch(&raw,&wrong,&forged).is_err());
        wrong=plan;wrong.operation="plan-hair".into();assert!(patch(&raw,&wrong,&payload).is_err());
    }
    #[test]fn every_prepare_storage_fault_retains_original_or_uncertain_durable_evidence(){
        for fault in [Fault::BeforeWrite,Fault::AfterSync,Fault::AfterReplace,Fault::LostReceipt]{let root=Temp::new();let req=read_request();let before=initial(&req);fs::write(root.0.join("form_bank.json"),&before).unwrap();let(plan,payload)=prepare(&req,&before);assert!(perform(&root.0,&plan,&payload,fault).is_err());let after=fs::read(root.0.join("form_bank.json")).unwrap();if matches!(fault,Fault::BeforeWrite|Fault::AfterSync){assert_eq!(after,before);}else{assert_eq!(after,patch(&before,&plan,&payload).unwrap());assert!(root.0.join(".form_bank.json.cas-writer.lock").is_file());}assert!(parse(&after).is_ok());if fault!=Fault::BeforeWrite{assert!(root.0.join(".form_bank.json.cas-writer.lock").is_file());assert!(Lease::take(&root.0,&req).is_err());}}
    }
    #[test]fn same_uuid_returns_original_ticket_and_replacement_input_is_not_adopted(){
        let root=Temp::new();let req=read_request();let raw=initial(&req);fs::write(root.0.join("form_bank.json"),&raw).unwrap();let worker=Worker::open(root.0.clone()).unwrap();let first=worker.submit(req.clone(),vec![],Fault::None).unwrap();assert!(wait(&worker,&req,first).contains("\"ok\":true"));
        let(plan,payload)=prepare(&req,&raw);let ticket=worker.submit(plan.clone(),payload.clone(),Fault::None).unwrap();assert_eq!(worker.submit(plan.clone(),b"not adopted".to_vec(),Fault::None).unwrap(),ticket);assert!(wait(&worker,&plan,ticket).contains("\"durable\":true"));assert_eq!(fs::read(root.0.join("form_bank.json")).unwrap(),patch(&raw,&plan,&payload).unwrap());let mut forged=plan.clone();forged.identity.household_id="21".into();assert!(worker.submit(forged,vec![],Fault::None).is_err());
    }
    #[test]fn foreign_lease_and_pending_evidence_are_never_stolen(){
        for foreign in [".form_bank.json.cas-writer.lock","form_bank.pending"]{let root=Temp::new();let req=read_request();let raw=initial(&req);fs::write(root.0.join("form_bank.json"),&raw).unwrap();fs::write(root.0.join(foreign),b"foreign evidence").unwrap();let(plan,payload)=prepare(&req,&raw);assert!(perform(&root.0,&plan,&payload,Fault::None).is_err());assert_eq!(fs::read(root.0.join(foreign)).unwrap(),b"foreign evidence");assert_eq!(fs::read(root.0.join("form_bank.json")).unwrap(),raw);}
    }
    #[test]fn held_disk_lane_never_blocks_submit_poll_or_unrelated_caller_work(){
        let root=Temp::new();let req=read_request();fs::write(root.0.join("form_bank.json"),initial(&req)).unwrap();let worker=Worker::open(root.0.clone()).unwrap();let held=worker.writer.lock().unwrap();let mut jobs=vec![];
        for i in 0..MAX_JOBS{let request=Request{request_id:format!("{i:032x}"),..req.clone()};let ticket=worker.submit(request.clone(),vec![],Fault::None).unwrap();jobs.push((request,ticket));}
        let extra=Request{request_id:"f".repeat(32),..req};assert!(worker.submit(extra,vec![],Fault::None).is_err());for _ in 0..1000{for(r,t)in &jobs{assert!(worker.poll(r,*t).unwrap().contains("pending"));}}drop(held);for(r,t)in jobs{assert!(wait(&worker,&r,t).contains("\"ok\":true"));}
    }
    #[test]fn strict_scanner_rejects_duplicate_unicode_alias_nonfinite_and_trailing_json(){
        for raw in [br#"{"a":1,"\u0061":2}"#.as_slice(),br#"{"n":NaN}"#,br#"{"n":Infinity}"#,br#"{"n":01}"#,br#"{} false"#]{assert!(parse(raw).is_err());}
    }
    #[test]fn rehashed_incomplete_desired_fields_are_rejected_before_storage(){
        let req=read_request();let raw=initial(&req);let(mut plan,payload)=prepare(&req,&raw);let mut doc:serde_json::Value=serde_json::from_slice(&payload).unwrap();doc["plan"]["desired"]["1"].as_object_mut().unwrap().remove("physique");let value=serde_json::to_vec(&doc["plan"]).unwrap();doc["plan_sha256"]=sha(&canonical(&value,&parse(&value).unwrap())).into();let payload=serde_json::to_vec(&doc).unwrap();plan.document_sha256=Some(sha(&canonical(&payload,&parse(&payload).unwrap())));assert!(patch(&raw,&plan,&payload).unwrap_err().contains("coverage"));
    }
    #[test]fn ffi_copies_all_header_and_payload_bytes_before_returning(){
        use std::ffi::CStr;
        let root=Temp::new();let req=read_request();let raw=initial(&req);fs::write(root.0.join("form_bank.json"),&raw).unwrap();let path=root.0.to_str().unwrap().as_bytes();
        let handle=unsafe{ApexBankBind(path.as_ptr(),path.len())};assert_ne!(handle,0);
        let poll=|request:&Request,ticket:u64|{let header=serde_json::to_vec(request).unwrap();let deadline=Instant::now()+std::time::Duration::from_secs(5);loop{let result=unsafe{ApexBankPoll(handle,header.as_ptr(),header.len(),ticket)};assert!(!result.is_null());let text=unsafe{CStr::from_ptr(result)}.to_str().unwrap().to_owned();unsafe{ApexBankFree(result)};if !text.contains("\"state\":\"pending\""){return text}assert!(Instant::now()<deadline);std::thread::sleep(std::time::Duration::from_millis(1));}};
        let mut header=serde_json::to_vec(&req).unwrap();let ticket=unsafe{ApexBankSubmit(handle,header.as_ptr(),header.len(),std::ptr::null(),0)};header.fill(b'x');assert!(poll(&req,ticket).contains("\"ok\":true"));
        let(plan,mut payload)=prepare(&req,&raw);let expected=patch(&raw,&plan,&payload).unwrap();let mut header=serde_json::to_vec(&plan).unwrap();let ticket=unsafe{ApexBankSubmit(handle,header.as_ptr(),header.len(),payload.as_ptr(),payload.len())};header.fill(b'x');payload.fill(b'x');assert!(poll(&plan,ticket).contains("\"durable\":true"));assert_eq!(fs::read(root.0.join("form_bank.json")).unwrap(),expected);
        assert_eq!(unsafe{ApexBankSubmit(handle,std::ptr::null(),4097,std::ptr::null(),0)},0);
    }
}
