import {readLimited,abortable} from './frame-client.mjs';
export const PAGE_SIZE=24, SCHEMA='inspect-only-subset-v1';
const hex=(v,n)=>typeof v==='string'&&new RegExp(`^[a-f0-9]{${n}}$`,'i').test(v);
const uint=v=>Number.isSafeInteger(v)&&v>=0;
const nullableBool=v=>v===null||typeof v==='boolean';
const safeText=v=>v===null||(typeof v==='string'&&[...v].length<=512&&!/[\x00-\x1f\x7f/\\:%&\u2215\u2044]/.test(v)&&!v.startsWith('~'));
const sourceStates=['unidentified','ea-resource','filename-or-internal-prefix-hint','ambiguous-prefix-review','conflicting-hash-review','conflicting-filename-or-fingerprint-review','unknown'];
function requireValue(ok){if(!ok)throw Error('Unrecognized catalog response; last good results retained.');}
export function validateIdentity(p){requireValue(p&&p.schema===SCHEMA&&p.inspect_only===true&&p.equip_allowed===false&&hex(p.epoch,32)&&hex(p.catalog_sha256,64));return p;}
export function validatePage(p,identity,q){
 validateIdentity(p);requireValue(p.ok===true&&p.epoch===identity.epoch&&p.catalog_sha256===identity.catalog_sha256&&uint(p.ticket)&&p.ticket>0&&uint(p.total)&&p.offset===q.offset&&p.grouped===q.grouped&&(p.next_offset===null||(uint(p.next_offset)&&p.next_offset>p.offset))&&Array.isArray(p.items)&&p.items.length<=q.limit);
 requireValue(Array.isArray(p.categories)&&p.categories.length<=4096&&p.categories.every(x=>(x.body_type===null||(uint(x.body_type)&&x.body_type<=0xffffffff))&&uint(x.count)));
 requireValue(typeof p.creators_included==='boolean'&&p.creators_included===(q.limit>=60)&&nullableBool(p.creators_complete)&&nullableBool(p.snapshot_complete)&&uint(p.projection_redactions)&&['authoritative','unknown'].includes(p.package_inventory_coverage)&&(p.source_errors_count===null||uint(p.source_errors_count)));
 requireValue(Array.isArray(p.creators)&&p.creators.length<=512&&p.creators.every(x=>safeText(x.name)&&['present','unknown','redacted'].includes(x.name_state)&&uint(x.count)));
 for(const x of p.items){requireValue(hex(x.part_id,64)&&['family_id','package_sha256','resource_sha256'].every(k=>x[k]===null||hex(x[k],64))&&(x.resource_tgi===null||/^[a-f0-9]{8}:[a-f0-9]{8}:[a-f0-9]{16}$/i.test(x.resource_tgi))&&['name','preferred_name','package_name','code_name'].every(k=>safeText(x[k]))&&[null,'mod','ea'].includes(x.origin)&&(x.body_type===null||(uint(x.body_type)&&x.body_type<=0xffffffff))&&x.equip_allowed===false);
 requireValue(x.author&&safeText(x.author.name)&&['present','unknown','redacted'].includes(x.author.state)&&nullableBool(x.author.verified)&&x.creator_verified===x.author.verified&&sourceStates.includes(x.creator_source)&&x.thumbnail?.state==='not_projected'&&x.thumbnail.url===null&&x.image_state==='not-projected'&&x.image_available===null&&(x.swatch_colors_argb===null||(Array.isArray(x.swatch_colors_argb)&&x.swatch_colors_argb.length<=256&&x.swatch_colors_argb.every(v=>uint(v)&&v<=0xffffffff))));}
 return p;
}
export const defaultQuery=()=>({text:'',body_type:null,origin:null,name_mode:'preferred',offset:0,limit:PAGE_SIZE,view:'all',author:'',sort:'name',grouped:false,fuzzy:false,folder:'',added_days:null});
export function validateQuery(input){const q={...defaultQuery(),...input,limit:PAGE_SIZE,view:'all'};for(const [k,max] of [['text',200],['author',80],['folder',512]])if(typeof q[k]!=='string'||[...q[k]].length>max||/[\x00-\x1f\x7f]/.test(q[k]))throw Error('Filter text is too long or contains control characters.');if(!uint(q.offset)||q.offset>0xffffffff||!(q.body_type===null||(uint(q.body_type)&&q.body_type<=0xffffffff))||![null,'mod','ea'].includes(q.origin)||!['preferred','package','code'].includes(q.name_mode)||!['name','package','creator','id','newest','modified','folder'].includes(q.sort)||typeof q.grouped!=='boolean'||typeof q.fuzzy!=='boolean'||!(q.added_days===null||(uint(q.added_days)&&q.added_days>=1&&q.added_days<=36500)))throw Error('Complete the numeric filters with a valid whole number.');encodeQuery(q);return q;}
export function encodeQuery(q){const bytes=new TextEncoder().encode(JSON.stringify(q));if(bytes.length>2048)throw Error('Combined filters exceed the query budget.');return btoa(String.fromCharCode(...bytes)).replaceAll('+','-').replaceAll('/','_').replace(/=+$/,'');}
export function itemTitle(x,mode='preferred'){return (mode==='package'?x.package_name:mode==='code'?x.code_name:x.preferred_name)||x.name||x.package_name||x.code_name||`Part ${x.part_id.slice(0,12)}`;}
export class CatalogBrowser {
 constructor({fetchImpl=globalThis.fetch,onChange=()=>{},timeoutMs=15000}={}){Object.assign(this,{fetchImpl,onChange,timeoutMs});this.generation=0;this.active=null;this.pending=null;this.disposed=false;this.identity=null;this.page=null;this.facets=null;this.folderSort='unknown';this.query=defaultQuery();this.state='unavailable';this.message='Checking catalog availability…';}
 emit(){if(!this.disposed)this.onChange(this);}
 recheck(){this.enqueue({kind:'status'});}
 request(input){if(this.disposed)return;let q;try{q=validateQuery(input);}catch(e){this.generation++;this.pending=null;this.state='invalid';this.message=e.message;this.emit();return;}if(!this.identity){this.message='Catalog is not ready. Recheck status before searching.';this.emit();return;}this.query=q;if(q.sort==='folder'&&this.folderSort==='unsupported'){this.generation++;this.pending=null;this.state='unsupported';this.message='Folder sorting unavailable for this index/helper. Choose another sort or use an updated indexed catalog. Last good results retained.';this.emit();return;}this.enqueue({kind:'query',q,identity:this.identity});}
 enqueue(job){if(this.disposed)return;job.generation=++this.generation;this.pending=job;this.state='loading';this.message=this.page?'Updating… Last good results remain visible.':'Loading bounded catalog page…';this.emit();this.pump();}
 async read(path,signal,{identity=null,limit=0}={}){
  const fetchImpl=this.fetchImpl; // Free call: native Window.fetch must not receive this controller as its receiver.
  const r=await abortable(fetchImpl(path,{signal,cache:'no-store',redirect:'error',credentials:'same-origin'}),signal);
  const discard=()=>{try{r.body?.cancel().catch(()=>{});}catch{}};
  if(r.status!==200){discard();const e=Error(r.status===409?'Catalog changed. Recheck status; last good results retained.':r.status===400?'Filter rejected. Edit filters and try again.':'Catalog unavailable. Recheck status when ready.');e.status=r.status;throw e;}
  let ticket=null;
  try{requireValue((r.headers.get('content-type')||'').split(';')[0].trim()==='application/json');
   if(identity){ticket=r.headers.get('X-Catalog-Ticket');requireValue(r.headers.get('X-Catalog-Epoch')===identity.epoch&&r.headers.get('X-Catalog-SHA256')===identity.catalog_sha256&&r.headers.get('X-Catalog-Policy')===String(identity.policy)&&typeof ticket==='string'&&/^[1-9][0-9]{0,19}$/.test(ticket));}
  }catch(error){discard();throw error;}
  const maxBytes=identity?(limit<=24?120*1024:512*1024):8*1024;
  const bytes=await readLimited(r,{maxBytes,signal});const parsed=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));
  if(identity)requireValue(parsed&&parsed.epoch===identity.epoch&&parsed.catalog_sha256===identity.catalog_sha256&&uint(parsed.ticket)&&String(parsed.ticket)===ticket);
  return parsed;
 }
 async pump(){if(this.active||!this.pending||this.disposed)return;const job=this.pending;this.pending=null;const abort=new AbortController();this.active=abort;const timer=setTimeout(()=>abort.abort(Error('Catalog request timed out. Recheck or edit filters to retry.')),this.timeoutMs);const current=()=>!this.disposed&&job.generation===this.generation;
 try{if(job.kind==='status'){const p=await this.read('/cc-catalog-state',abort.signal);if(!current())return;requireValue(p&&p.schema===1&&p.enabled===true&&p.inspect_only===true&&p.equip_allowed===false&&hex(p.epoch,32)&&hex(p.catalog_sha256,64)&&[1,2].includes(p.policy)&&['starting','ready','unavailable','stopped'].includes(p.state));if(p.state!=='ready'){this.folderSort='unknown';this.identity=null;this.state='unavailable';this.message='Catalog is not ready. No queries will run until status is ready.';return;}if(this.identity?.epoch!==p.epoch||this.identity?.catalog_sha256!==p.catalog_sha256){this.facets=null;this.folderSort='unknown';}this.identity=p;this.request({...this.query,offset:0});}
 else{const id=job.identity;const query=async q=>validatePage(await this.read(`/cc-catalog/query?epoch=${id.epoch}&q=${encodeQuery(q)}`,abort.signal,{identity:id,limit:q.limit}),id,q);if(!this.facets){const bootstrap=await query({...defaultQuery(),limit:60});if(!current())return;this.facets={creators:bootstrap.creators,included:bootstrap.creators_included,complete:bootstrap.creators_complete,categories:bootstrap.categories};}
 // A known-valid bounded engine probe is capability evidence, never a displayed page.
 if(job.q.sort==='folder'&&this.folderSort!=='supported'){
  try{await query({...defaultQuery(),sort:'folder'});}catch(error){if(error.status===400&&current()){this.folderSort='unsupported';error.folderSortUnavailable=true;}throw error;}
  if(!current())return;this.folderSort='supported';
 }
 const p=await query(job.q);if(!current()||this.identity?.epoch!==id.epoch)return;this.page=p;this.pageQuery=job.q;this.state=p.items.length?'ready':'empty';this.message=p.items.length?'Inspect-only metadata. Selecting results never equips a Sim.':'No results for these filters.';}
 }catch(e){if(current()){if(job.kind==='status')this.folderSort='unknown';if([404,409,502,503,504].includes(e.status)){this.identity=null;this.facets=null;this.folderSort='unknown';}this.state=e.folderSortUnavailable?'unsupported':e.status===400?'invalid':e.status===404?'unavailable':'error';this.message=e.folderSortUnavailable?'Folder sorting unavailable for this index/helper. Choose another sort or use an updated indexed catalog. Last good results retained.':e.status===404?'Catalog access is disabled on this server.':e.status||e.message?.startsWith('Catalog')||e.message?.startsWith('Filter')?e.message:'Unrecognized catalog response; last good results retained.';}}
 finally{clearTimeout(timer);abort.abort();this.active=null;if(!this.disposed){this.emit();this.pump();}}}
 dispose(){this.disposed=true;this.generation++;this.pending=null;this.active?.abort();}
}
