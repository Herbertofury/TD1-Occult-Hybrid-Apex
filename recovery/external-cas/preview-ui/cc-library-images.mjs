// Optional prepared-source companion. Metadata's thumbnail projection remains untouched.
import {readLimited,abortable} from './frame-client.mjs';
const HEX=/^[a-f0-9]{64}$/;
const FAILURES=['disabled','missing','unqualified','changed','unsupported','overbudget','conflicting','wrong-catalog','unavailable'];
const fault=state=>Object.assign(Error('Source image '+state),{state});
const check=(condition,state='unqualified')=>{if(!condition)throw fault(state);};
const integer=v=>Number.isSafeInteger(v)&&v>=0;
const discard=r=>{try{r.body?.cancel().catch(()=>{});}catch{}};
const headersMatch=(headers,index)=>headers.get('X-Catalog-SHA256')===index.catalog_sha256&&headers.get('X-Source-Image-Index-SHA256')===index.index_sha256&&headers.get('X-Source-Image-Manifest-SHA256')===index.manifest_sha256;
export function validateSourceIndex(value,headers,catalog){
 check(value&&value.schema===1&&value.enabled===true&&value.state==='ready'&&value.coverage==='PreparedSnapshot'&&value.inspect_only===true&&value.equip_allowed===false&&value.missing_descriptor_state==='unqualified');
 check(value.catalog_sha256===catalog&&HEX.test(catalog)&&HEX.test(value.index_sha256)&&HEX.test(value.manifest_sha256)&&headersMatch(headers,value),'changed');
 check(Array.isArray(value.items)&&value.items.length>=1&&value.items.length<=64&&value.row_count===value.items.length&&integer(value.total_png_bytes)&&value.total_png_bytes<=4*1024*1024,'overbudget');
 const assets=new Set();let last='',total=0;
 for(const row of value.items){check(row&&HEX.test(row.part_id)&&HEX.test(row.asset_id)&&HEX.test(row.png_sha256)&&row.state==='ready'&&row.part_id>last&&!assets.has(row.asset_id));check(row.width===104&&row.height===148,'unsupported');check(integer(row.byte_count)&&row.byte_count>=57&&row.byte_count<=128*1024,'overbudget');check(row.url===`/cc-source-image/${row.asset_id}.png?catalog=${catalog}`);last=row.part_id;assets.add(row.asset_id);total+=row.byte_count;}
 check(total===value.total_png_bytes,'changed');return value;
}
export function validateSourcePNG(bytes,row){
 check(bytes instanceof Uint8Array&&bytes.length===row.byte_count&&bytes.length<=128*1024,'changed');
 check(row.width===104&&row.height===148&&bytes.length>=57,'unsupported');
 const view=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);
 check([137,80,78,71,13,10,26,10].every((v,i)=>bytes[i]===v)&&view.getUint32(8)===13&&String.fromCharCode(...bytes.slice(12,16))==='IHDR'&&view.getUint32(16)===row.width&&view.getUint32(20)===row.height&&[8,6,0,0,0].every((v,i)=>bytes[24+i]===v),'unsupported');
 let at=8,idat=false,end=false,chunks=0;while(at<bytes.length){check(++chunks<=4096&&bytes.length-at>=12,'unsupported');const size=view.getUint32(at);check(size<=bytes.length-at-12,'unsupported');const type=String.fromCharCode(...bytes.slice(at+4,at+8));check((type==='IHDR'&&at===8&&size===13)||(type==='IDAT'&&!end)||(type==='IEND'&&size===0&&idat&&at+12===bytes.length),'unsupported');if(type==='IDAT')idat=true;if(type==='IEND')end=true;at+=size+12;}check(end,'unsupported');return row.width*row.height*4;
}
async function sha256(bytes){if(!globalThis.crypto?.subtle)throw fault('unsupported');return Array.from(new Uint8Array(await globalThis.crypto.subtle.digest('SHA-256',bytes)),v=>v.toString(16).padStart(2,'0')).join('');}
export class SourceImages{
 constructor({fetchImpl=globalThis.fetch,onChange=()=>{},makeURL=bytes=>URL.createObjectURL(new Blob([bytes],{type:'image/png'})),revokeURL=url=>URL.revokeObjectURL(url),digest=sha256,workers=2,maxBytes=3*1024*1024,maxDecodedBytes=2*1024*1024,timeoutMs=10000}={}){
  check(Number.isInteger(workers)&&workers>=1&&workers<=2&&Number.isInteger(maxBytes)&&maxBytes>=57&&maxBytes<=3*1024*1024&&Number.isInteger(maxDecodedBytes)&&maxDecodedBytes>=4&&maxDecodedBytes<=2*1024*1024&&Number.isInteger(timeoutMs)&&timeoutMs>=1&&timeoutMs<=30000,'overbudget');
  Object.assign(this,{fetchImpl,onChange,makeURL,revokeURL,digest,workers,maxBytes,maxDecodedBytes,timeoutMs});this.entries=new Map();this.jobs=new Set();this.generation=0;this.active=0;this.usedBytes=0;this.usedDecodedBytes=0;this.catalog=null;this.key=null;this.index=null;this.indexState=null;this.closed=false;
 }
 emit(part,state){if(!this.closed)this.onChange(part,state);}
 release(entry){if(entry?.url){this.revokeURL(entry.url);this.usedBytes-=entry.bytes;this.usedDecodedBytes-=entry.pixels;entry.url=null;}}
 setPage(catalog,partIds){
  if(this.closed)return;check(HEX.test(catalog)&&Array.isArray(partIds)&&partIds.length<=24&&partIds.every(id=>HEX.test(id))&&new Set(partIds).size===partIds.length);
  const key=JSON.stringify([catalog,partIds]);if(key===this.key){for(const [part,entry] of this.entries)this.emit(part,entry);return;}
  this.generation++;for(const job of this.jobs)job.abort();const previous=this.entries;this.entries=new Map();const changed=catalog!==this.catalog;
  if(changed){this.index=null;this.indexState=null;}this.catalog=catalog;this.key=key;
  for(const part of partIds){const old=previous.get(part);if(!changed&&old&&old.state!=='loading'&&old.state!=='pending'){this.entries.set(part,old);previous.delete(part);}else this.entries.set(part,{state:'pending'});}
  for(const entry of previous.values())this.release(entry);for(const [part,entry] of this.entries)this.emit(part,entry);this.pump();
 }
 reset(){if(this.closed)return;this.generation++;for(const job of this.jobs)job.abort();for(const entry of this.entries.values())this.release(entry);this.entries.clear();this.key=null;this.index=null;this.indexState=null;}
 async response(path,signal){const fetchImpl=this.fetchImpl;return abortable(fetchImpl(path,{signal,cache:'no-store',redirect:'error',credentials:'same-origin'}),signal);}
 async failure(response,signal,{index=false}={}){
  if(response.status===404){discard(response);throw fault(index?'disabled':'unqualified');}
  if(response.status===409){discard(response);throw fault('changed');}
  if(response.status===503){try{check((response.headers.get('content-type')||'').split(';')[0]==='application/json');const bytes=await readLimited(response,{maxBytes:4096,signal});const p=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));check(p.schema===1&&p.enabled===true&&p.coverage==='PreparedSnapshot'&&p.inspect_only===true&&p.equip_allowed===false&&FAILURES.includes(p.state));throw fault(p.state);}catch(error){if(error.state)throw error;throw fault('unavailable');}}
  discard(response);throw fault(response.status===400?'unqualified':'unavailable');
 }
 async readIndex(signal,catalog){const response=await this.response(`/cc-source-images?catalog=${catalog}`,signal);if(response.status!==200)return this.failure(response,signal,{index:true});if((response.headers.get('content-type')||'').split(';')[0]!=='application/json'){discard(response);throw fault('unsupported');}let bytes;try{bytes=await readLimited(response,{maxBytes:64*1024,signal});}catch(error){if(signal.aborted)throw error;throw fault(/budget|exceeds/.test(error.message)?'overbudget':'changed');}let parsed;try{parsed=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));}catch{throw fault('unsupported');}return validateSourceIndex(parsed,response.headers,catalog);}
 async readImage(row,index,signal){const response=await this.response(row.url,signal);if(response.status!==200)return this.failure(response,signal);if((response.headers.get('content-type')||'').split(';')[0]!=='image/png'){discard(response);throw fault('unsupported');}if(!headersMatch(response.headers,index)||response.headers.get('X-Source-Image-SHA256')!==row.png_sha256||response.headers.get('X-Source-Image-Part-ID')!==row.part_id||response.headers.get('X-Source-Image-Asset-ID')!==row.asset_id){discard(response);throw fault('changed');}let bytes;try{bytes=await readLimited(response,{maxBytes:row.byte_count,exact:true,signal});}catch(error){if(signal.aborted)throw error;const length=response.headers.get('content-length');throw fault((length!==null&&/^\d+$/.test(length)&&BigInt(length)>BigInt(row.byte_count))||/byte\/chunk budget exceeded/.test(error.message)?'overbudget':'changed');}const pixels=validateSourcePNG(bytes,row);const digest=this.digest;check(await abortable(digest(bytes),signal)===row.png_sha256,'changed');return {bytes,pixels};}
 run(kind,part=null,row=null){const generation=this.generation,catalog=this.catalog,index=this.index,abort=new AbortController();this.jobs.add(abort);this.active++;const timer=setTimeout(()=>abort.abort(fault('unavailable')),this.timeoutMs);const current=()=>!this.closed&&generation===this.generation&&!abort.signal.aborted;
  (async()=>{try{if(kind==='index'){const value=await this.readIndex(abort.signal,catalog);if(!current())return;this.index=value;this.indexState='ready';}
   else{const {bytes,pixels}=await this.readImage(row,index,abort.signal);if(!current())return;check(this.usedBytes+bytes.length<=this.maxBytes&&this.usedDecodedBytes+pixels<=this.maxDecodedBytes,'overbudget');const makeURL=this.makeURL,url=makeURL(bytes);check(typeof url==='string'&&url.startsWith('blob:'),'unsupported');if(!current()){this.revokeURL(url);return;}const entry={state:'ready',url,row,index,bytes:bytes.length,pixels};this.usedBytes+=bytes.length;this.usedDecodedBytes+=pixels;this.entries.set(part,entry);this.emit(part,entry);}
  }catch(error){if(!this.closed&&generation===this.generation){const state=FAILURES.includes(error.state)?error.state:'unavailable';if(kind==='index')this.indexState=state;else{const entry={state,row,index};this.entries.set(part,entry);this.emit(part,entry);}}}
  finally{clearTimeout(timer);abort.abort();this.jobs.delete(abort);this.active--;if(!this.closed)this.pump();}})();
 }
 pump(){if(this.closed||!this.entries.size)return;if(!this.index){if(this.indexState&&this.indexState!=='loading'){for(const [part,entry] of this.entries)if(entry.state==='pending'||entry.state==='loading'){const value={state:this.indexState};this.entries.set(part,value);this.emit(part,value);}return;}if(this.active===0){this.indexState='loading';this.run('index');}return;}
  for(const [part,entry] of this.entries){if(entry.state!=='pending')continue;const row=this.index.items.find(item=>item.part_id===part);if(!row){const value={state:'unqualified',index:this.index};this.entries.set(part,value);this.emit(part,value);continue;}if(this.active>=this.workers)break;this.entries.set(part,{state:'loading',row,index:this.index});this.emit(part,this.entries.get(part));this.run('image',part,row);}
 }
 failDecode(part,url){const entry=this.entries.get(part);if(this.closed||entry?.url!==url)return;this.release(entry);const value={state:'unsupported',row:entry.row,index:entry.index};this.entries.set(part,value);this.emit(part,value);}
 close(){if(this.closed)return;this.closed=true;this.generation++;for(const job of this.jobs)job.abort();for(const entry of this.entries.values())this.release(entry);this.entries.clear();this.key=null;this.index=null;}
}
