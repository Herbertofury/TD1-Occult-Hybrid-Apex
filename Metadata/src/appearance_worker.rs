//! Owned byte snapshots only. No game pointers, Python, GFx, renderer or disk
//! access crosses this boundary. The UI submits/polls; it never joins a worker.
use anyhow::{Result, bail, ensure};
use rayon::{ThreadPool, ThreadPoolBuilder};
use serde_json::json;
use sha2::{Digest, Sha256};
use std::{collections::BTreeMap, ffi::{CStr, CString, c_char}, sync::{Arc, Mutex, OnceLock}, time::Instant};

const LIMIT: usize = 8 * 1024 * 1024;
const MAX_JOBS: usize = 4;
#[derive(Clone, Copy, PartialEq)]
enum Schema { Root, Outfits, Outfit, Genetics, Parts, Part, Array, FixedArray, Morph, Opaque }
struct Field<'a> { number: u32, kind: u8, raw: &'a [u8], value: &'a [u8] }

fn var(raw: &[u8], at: &mut usize) -> Result<u64> {
    let mut value=0;
    for shift in (0..70).step_by(7) {
        let b=*raw.get(*at).ok_or_else(||anyhow::anyhow!("Truncated varint"))?;*at+=1;
        ensure!(shift!=63 || b<=1,"Varint overflow");value|=u64::from(b&127)<<shift;
        if b&128==0{return Ok(value)}
    }
    bail!("Unbounded varint")
}
fn write_var(mut value:u64,out:&mut Vec<u8>) {
    while value>127 {out.push((value as u8&127)|128);value>>=7;}out.push(value as u8);
}
fn skip(raw:&[u8],at:&mut usize,kind:u8,number:u32,depth:u32)->Result<()> {
    ensure!(depth<=32,"Group depth exceeds bound");
    if kind==0 {var(raw,at)?;return Ok(())}
    if kind==3 {
        while *at<raw.len() {
            let key=var(raw,at)?;let child=key>>3;let wire=(key&7) as u8;
            ensure!((1..=536870911).contains(&child),"Invalid group key");
            if wire==4 {ensure!(child==u64::from(number),"Mismatched group end");return Ok(())}
            skip(raw,at,wire,child as u32,depth+1)?;
        }
        bail!("Unterminated group")
    }
    let size=match kind {1=>8,5=>4,2=>var(raw,at)?,_=>bail!("Invalid wire type")};
    ensure!(size<=raw.len().saturating_sub(*at) as u64,"Truncated field");*at+=size as usize;Ok(())
}
fn fields(raw:&[u8])->Result<Vec<Field<'_>>> {
    ensure!(raw.len()<=LIMIT,"Packet exceeds bound");let mut at=0;let mut result=Vec::new();
    while at<raw.len() {
        let begin=at;let key=var(raw,&mut at)?;let number=key>>3;let kind=(key&7) as u8;
        ensure!((1..=536870911).contains(&number) && kind!=4,"Invalid field key");
        let payload;
        if kind==2 {let size=var(raw,&mut at)?;payload=at;ensure!(size<=raw.len().saturating_sub(at) as u64,"Truncated bytes");at+=size as usize;}
        else {payload=at;skip(raw,&mut at,kind,number as u32,0)?;}
        ensure!(result.len()<65536,"Too many fields");
        result.push(Field{number:number as u32,kind,raw:&raw[begin..at],value:&raw[payload..at]});
    }
    Ok(result)
}
fn canonical(raw:&[u8],schema:Schema)->Result<Vec<u8>> {
    if schema==Schema::Opaque {return Ok(raw.to_vec())}
    let mut rows=fields(raw)?;rows.sort_by_key(|f|f.number);let mut out=Vec::with_capacity(raw.len());
    if matches!(schema,Schema::Array|Schema::FixedArray) {
        let fixed=schema==Schema::FixedArray;let mut packed=Vec::new();let mut count=0;
        for f in &rows {
            if f.number!=1 {out.extend_from_slice(f.raw);continue}
            match (fixed,f.kind) {
                (false,0)=>{let mut at=0;write_var(var(f.value,&mut at)?,&mut packed);count+=1;},
                (true,1)=>{packed.extend_from_slice(f.value);count+=1;},
                (true,2)=>{ensure!(f.value.len()%8==0,"Misaligned fixed64 array");packed.extend_from_slice(f.value);count+=f.value.len()/8;},
                (false,2)=>{let mut at=0;while at<f.value.len(){write_var(var(f.value,&mut at)?,&mut packed);count+=1;ensure!(count<=4096,"Too many array values");}},
                _=>bail!("Unsupported array encoding")
            }
            ensure!(count<=4096,"Too many array values");
        }
        if !packed.is_empty(){write_var(10,&mut out);write_var(packed.len() as u64,&mut out);out.extend(packed)}return Ok(out)
    }
    for f in rows {
        let child=match (schema,f.number) {
            (Schema::Root,21)=>Schema::Outfits,(Schema::Root,28)=>Schema::Genetics,(Schema::Root,18)=>Schema::Morph,
            (Schema::Root,9|10|11|12|54|62|63|67|75|76)=>Schema::Opaque,(Schema::Root,_)=>continue,
            (Schema::Outfits,1)=>Schema::Outfit,(Schema::Outfit,5)=>Schema::FixedArray,
            (Schema::Outfit,7|12|14|15)=>Schema::Array,(Schema::Genetics,5|6)=>Schema::Parts,
            (Schema::Genetics,1)=>Schema::Morph,(Schema::Parts,1)=>Schema::Part,_=>Schema::Opaque
        };
        if f.kind==2 {let value=canonical(f.value,child)?;write_var((u64::from(f.number)<<3)|2,&mut out);write_var(value.len() as u64,&mut out);out.extend(value)}
        else {out.extend_from_slice(f.raw)}
    }
    Ok(out)
}

struct Job {context:String,result:Option<String>}
#[derive(Default)]
struct State {next:u64,inflight:usize,jobs:BTreeMap<u64,Job>,completed:u64,superseded:u64}
struct Runtime {pool:ThreadPool,state:Arc<Mutex<State>>,threads:usize}
fn runtime()->Result<&'static Runtime> {
    static VALUE:OnceLock<Result<Runtime,String>>=OnceLock::new();
    VALUE.get_or_init(||{
        let available=std::thread::available_parallelism().map_or(1,usize::from);
        let threads=available.saturating_sub(2).clamp(1,2);
        ThreadPoolBuilder::new().num_threads(threads).thread_name(|n|format!("ApexPureCPU-{n}"))
            .build().map(|pool|Runtime{pool,state:Arc::new(Mutex::new(State::default())),threads}).map_err(|e|e.to_string())
    }).as_ref().map_err(|e|anyhow::anyhow!(e.clone()))
}
fn context(raw:*const c_char)->Result<String> {
    ensure!(!raw.is_null(),"Missing context");
    // Caller contract: valid NUL-terminated string for this call only.
    let value=unsafe {CStr::from_ptr(raw)}.to_str()?;ensure!(!value.is_empty() && value.len()<=512,"Invalid context");Ok(value.to_owned())
}
fn reply(value:serde_json::Value)->*mut c_char {
    CString::new(value.to_string()).map_or(std::ptr::null_mut(),CString::into_raw)
}
/// # Safety
/// Context is NUL-terminated UTF-8; bytes points to `length` readable bytes.
/// The complete input is copied before returning. Zero means busy/refused.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn ApexAppearanceSubmit(owner:*const c_char,bytes:*const u8,length:usize)->u64 {
    std::panic::catch_unwind(||->Result<u64>{
        ensure!(!bytes.is_null() && length<=LIMIT,"Invalid packet");let owner=context(owner)?;let rt=runtime()?;
        let ticket;
        {let mut state=rt.state.lock().map_err(|_|anyhow::anyhow!("Worker state failed"))?;
         ensure!(state.inflight<MAX_JOBS && state.next<u64::MAX,"Worker busy");
         // Replace this context's unobserved publication, never accumulate a
         // typing/input queue. In-flight obsolete snapshots still count.
         state.jobs.retain(|_,j|j.context!=owner);
         while state.jobs.len()>=MAX_JOBS {if let Some(key)=state.jobs.keys().next().copied(){state.jobs.remove(&key);}}
         state.next+=1;ticket=state.next;state.inflight+=1;state.jobs.insert(ticket,Job{context:owner.clone(),result:None});}
        let raw=unsafe {std::slice::from_raw_parts(bytes,length)}.to_vec();let state=Arc::clone(&rt.state);let threads=rt.threads;
        rt.pool.spawn_fifo(move||{
            let started=Instant::now();
            let result=std::panic::catch_unwind(||canonical(&raw,Schema::Root).map(|v|format!("{:x}",Sha256::digest(v))));
            let value=match result {Ok(Ok(sha))=>json!({"state":"ready","sha256":sha,"compute_ms":started.elapsed().as_secs_f64()*1000.0,"worker_threads":threads}),
                Ok(Err(e))=>json!({"state":"failed","message":e.to_string()}),Err(_)=>json!({"state":"failed","message":"Appearance worker failed"})}.to_string();
            if let Ok(mut state)=state.lock(){state.inflight-=1;if let Some(job)=state.jobs.get_mut(&ticket){if job.context==owner {job.result=Some(value);state.completed+=1;}}else{state.superseded+=1;}}
        });Ok(ticket)
    }).ok().and_then(Result::ok).unwrap_or(0)
}
/// # Safety
/// Context is a valid NUL-terminated UTF-8 string. Free the independent result
/// exactly once with ApexCatalogFree. Poll never waits for computation.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn ApexAppearancePoll(owner:*const c_char,ticket:u64)->*mut c_char {
    let result=std::panic::catch_unwind(||->Result<serde_json::Value>{
        let owner=context(owner)?;let rt=runtime()?;let state=rt.state.lock().map_err(|_|anyhow::anyhow!("Worker state failed"))?;
        let mut value=match state.jobs.get(&ticket){Some(j) if j.context==owner=>match &j.result {Some(v)=>serde_json::from_str(v)?,None=>json!({"state":"pending"})},_=>json!({"state":"stale"})};
        value["ticket"]=ticket.into();value["inflight"]=state.inflight.into();value["worker_threads"]=rt.threads.into();Ok(value)
    });
    reply(result.ok().and_then(Result::ok).unwrap_or_else(||json!({"state":"failed","message":"Appearance worker unavailable"})))
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test] fn canonical_rejects_bad_fields_and_preserves_unknown_nested_bytes(){
        assert!(canonical(&[0],Schema::Root).is_err());assert!(canonical(&[0xff;11],Schema::Root).is_err());
        assert_eq!(canonical(&[0xe8,4,7,0x48,1],Schema::Root).unwrap(),[0x48,1]);
        let raw=[0x92,1,3,0x98,6,9];assert_eq!(canonical(&raw,Schema::Root).unwrap(),raw);
    }
    #[test] fn arrays_preserve_order_and_extensions_across_encoding(){
        let packed=[10,3,1,0xac,2,0x90,3,7];let mixed=[8,1,10,2,0xac,2,0x90,3,7];
        assert_eq!(canonical(&packed,Schema::Array).unwrap(),canonical(&mixed,Schema::Array).unwrap());
        assert!(canonical(&[10,1,9],Schema::FixedArray).is_err());
        assert_ne!(canonical(&[8,1,8,2],Schema::Array).unwrap(),canonical(&[8,2,8,1],Schema::Array).unwrap());
    }
}
