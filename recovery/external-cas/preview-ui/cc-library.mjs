import {CatalogBrowser,PAGE_SIZE,itemTitle} from './cc-library-model.mjs';
import {SourceImages} from './cc-library-images.mjs';
// BEGIN EXACT TESTED IMPORT WORKFLOW
// Public DTO and injected trusted transport only. No HTTP, filesystem or restart owner.
const IMPORT_WORKING=['reading_manifest','staging','indexing','preparing','verifying_sources','checking_helper'];
const IMPORT_RETRY=['failed','cancelled','incomplete','needs_preparation'];
const IMPORT_PHASES=['idle',...IMPORT_WORKING,'cancelling',...IMPORT_RETRY,'ready_to_restart'];
const IMPORT_CODES=['incomplete_sources','preparation_unavailable','import_failed','pin_refused','output_path_refused','output_budget','invalid_budget','adapter_timeout','adapter_output_bound','adapter_failed','preparation_incomplete','unsupported_platform','helper_timeout','helper_error_bound','helper_early_exit','helper_frame_bound','helper_protocol_refused','helper_ready_refused','helper_shutdown_refused','source_changed','invalid_manifest','scanner_changed','prepared_owner_refused','helper_not_ready'];
const importId=value=>typeof value==='string'&&/^[a-f0-9]{32}$/.test(value);
export function validateImportStatus(raw){
 const keys=['job','phase','staged_packages','total_packages','parts','complete','pending_restart','has_last_good','error_code','completed_phases'];
 if(!raw||![Object.prototype,null].includes(Object.getPrototypeOf(raw))||Object.keys(raw).sort().join()!==keys.sort().join()||Object.values(Object.getOwnPropertyDescriptors(raw)).some(d=>!Object.hasOwn(d,'value')))throw Error('Invalid public import status');
 const count=(value,max)=>Number.isSafeInteger(value)&&value>=0&&value<=max;
 if(!IMPORT_PHASES.includes(raw.phase)||(raw.phase==='idle'?raw.job!==null:!importId(raw.job))||!count(raw.staged_packages,100000)||(raw.total_packages!==null&&!count(raw.total_packages,100000))||(raw.parts!==null&&!count(raw.parts,2000000))||(raw.total_packages===null?raw.staged_packages!==0:raw.staged_packages>raw.total_packages)||[raw.complete,raw.pending_restart,raw.has_last_good].some(v=>typeof v!=='boolean')||(raw.error_code!==null&&!IMPORT_CODES.includes(raw.error_code))||!Array.isArray(raw.completed_phases)||raw.completed_phases.length>6)throw Error('Invalid public import status');
 let previous=-1;for(const phase of raw.completed_phases){const index=IMPORT_WORKING.indexOf(phase);if(index<=previous)throw Error('Invalid completed import phases');previous=index;}
 const ready=raw.phase==='ready_to_restart';
 if(raw.complete!==ready||raw.pending_restart!==ready||(ready&&(raw.total_packages===null||raw.total_packages===0||raw.staged_packages!==raw.total_packages||raw.parts===null||raw.error_code!==null||raw.completed_phases.join()!==IMPORT_WORKING.join())))throw Error('Incomplete import result');
 if(raw.phase==='idle'&&(raw.staged_packages!==0||raw.total_packages!==null||raw.parts!==null||raw.completed_phases.length||raw.error_code!==null))throw Error('Invalid idle import status');
 return Object.freeze({...raw,completed_phases:Object.freeze([...raw.completed_phases])});
}
function importAbortable(promise,signal){return new Promise((resolve,reject)=>{const abort=()=>finish(reject,Error('Import reception canceled'));function finish(fn,value){signal.removeEventListener('abort',abort);fn(value);}if(signal.aborted){abort();return;}signal.addEventListener('abort',abort,{once:true});Promise.resolve(promise).then(v=>finish(resolve,v),e=>finish(reject,e));});}
export function createCatalogImport({onChange=()=>{},pollMs=500,timeoutMs=15000,schedule=setTimeout,unschedule=clearTimeout}={}){
 if(!Number.isInteger(pollMs)||pollMs<100||pollMs>5000||!Number.isInteger(timeoutMs)||timeoutMs<1||timeoutMs>15000)throw Error('Invalid import timing');
 let transport=null,token=null,snapshot=null,expectedJob=null,generation=0,active=null,poll=null,pending=null,disposed=false,fresh=false,uncertain=false,cancelRequested=false,kind='unavailable';
 function view(){
  const writable=!!transport&&!disposed&&fresh&&!uncertain&&!['start','retry','cancel'].includes(pending);
  const messages={unavailable:'CC import unavailable: no trusted host transport is connected.',connecting:'Checking import status with the trusted host.',failed:'Import status could not be verified. No result was activated; refresh status to recover.',uncertain:'Command outcome is unconfirmed. Refresh status; do not repeat the command. Trusted host reconciliation may be required.',disposed:'Import panel disconnected. A host operation may continue; disposal did not send a cancel command.'};
  const phases={idle:'Ready to import the source selection already bound by the trusted host.',reading_manifest:'Reading the selected source manifest.',staging:'Staging package inventory.',indexing:'Building the candidate catalog.',preparing:'Preparing the candidate catalog.',verifying_sources:'Verifying original source identities.',checking_helper:'Checking the prepared catalog helper.',cancelling:'Cancellation requested; waiting for host confirmation.',cancelled:'Import cancelled. No pending restart proposal is active.',incomplete:'Source scan is incomplete. Repair the selected sources before retrying.',failed:'Import failed or was refused. Repair the selected sources before retrying.',needs_preparation:'Source scan needs preparation that is unavailable. This is not a completed import.',ready_to_restart:'Verified import is pending a trusted host restart. It is NOT the active catalog. No restart or activation was performed.'};
  const phase=snapshot?.phase;let message=messages[kind]??phases[phase]??messages.connecting;
  if(kind==='status'&&pending==='start')message='Starting the selected import; waiting for an opaque job identity.';
  if(kind==='status'&&pending==='retry')message='Retrying the retained source selection; waiting for a new job identity.';
  if(kind==='status'&&cancelRequested&&!['cancelled','failed','incomplete'].includes(phase))message='Cancellation requested; waiting for host confirmation.';
  message+=' Current catalog and its last-good page are unchanged.';
  if(snapshot)message+=snapshot.has_last_good?' The host reports a retained last-good catalog.':' The host reports no last-good catalog.';
  return Object.freeze({kind,phase:phase??null,message,pending:pending!==null,staged:snapshot?.staged_packages??0,total:snapshot?.total_packages??null,parts:snapshot?.parts??null,canStart:writable&&pending===null&&phase==='idle',canRetry:writable&&pending===null&&IMPORT_RETRY.includes(phase),canCancel:writable&&!cancelRequested&&snapshot?.job!==null&&(IMPORT_WORKING.includes(phase)||phase==='ready_to_restart'),canRefresh:!!transport&&!disposed&&pending===null});
 }
 function emit(){onChange(view());}
 function clearPoll(){if(poll!==null)unschedule(poll);poll=null;}
 function begin(method){generation++;clearPoll();active?.abort();active=new AbortController();pending=method;emit();return {ticket:generation,controller:active};}
 async function run(method,arg){
  const {ticket,controller}=begin(method);const deadline=schedule(()=>controller.abort(),timeoutMs);
  const owns=()=>!disposed&&ticket===generation;
  try{
   const args=method==='status'?[{signal:controller.signal}]:[arg,{signal:controller.signal}];
   const result=await importAbortable(Reflect.apply(transport[method],transport,args),controller.signal);
   if(!owns())return false;
   if(method==='status'){
    const next=validateImportStatus(result);if(expectedJob!==null&&next.job!==expectedJob)throw Error('Import job identity changed');
    snapshot=next;expectedJob??=next.job;fresh=true;
    if(cancelRequested&&next.phase==='cancelled'){cancelRequested=false;uncertain=false;}else if(cancelRequested&&!uncertain&&IMPORT_RETRY.includes(next.phase)){cancelRequested=false;}
    kind=uncertain?'uncertain':'status';pending=null;emit();
    if(IMPORT_WORKING.includes(next.phase)||next.phase==='cancelling')poll=schedule(()=>{poll=null;void refresh();},pollMs);
   }else{
    if(method==='start'||method==='retry'){if(!importId(result)||(method==='retry'&&result===expectedJob))throw Error('Invalid job acknowledgement');expectedJob=result;cancelRequested=false;fresh=false;}
    else if(result!==undefined)throw Error('Invalid cancellation acknowledgement');
    pending=null;void refresh();
   }
   return true;
  }catch{
   if(owns()){fresh=false;pending=null;if(method!=='status')uncertain=true;kind=uncertain?'uncertain':'failed';emit();}
   return false;
  }finally{unschedule(deadline);controller.abort();if(active===controller)active=null;}
 }
 function refresh(){if(!transport||disposed||pending!==null)return Promise.resolve(false);if(!snapshot)kind='connecting';return run('status');}
 function act(method){const state=view(),allowed=method==='start'?state.canStart:method==='retry'?state.canRetry:state.canCancel;if(!allowed)return Promise.resolve(false);kind='status';if(method==='cancel')cancelRequested=true;return run(method,method==='start'?token:snapshot.job);}
 const api={connect(value,manifestToken){if(transport||disposed||!importId(manifestToken)||!value||['start','retry','cancel','status'].some(k=>typeof value[k]!=='function'))return false;transport=value;token=manifestToken;kind='connecting';void refresh();return true;},start:()=>act('start'),retry:()=>act('retry'),cancel:()=>act('cancel'),refresh,dispose(){if(disposed)return;disposed=true;generation++;clearPoll();active?.abort();active=null;pending=null;fresh=false;kind='disposed';emit();},get state(){return view();},get snapshot(){return snapshot;}};
 emit();return api;
}
export function bindCatalogImport({root,transport=null,manifestToken=null,...options}){
 const get=id=>root.querySelector('[data-import="'+id+'"]');
 const status=get('status'),progress=get('progress'),counts=get('counts'),buttons={start:get('start'),retry:get('retry'),cancel:get('cancel'),refresh:get('refresh')};
 if(!status||!progress||!counts||Object.values(buttons).some(v=>!v))throw Error('Import panel controls missing');
 const controller=createCatalogImport({...options,onChange:view=>{status.textContent=view.message;status.dataset.state=view.kind;status.dataset.phase=view.phase??'none';root.setAttribute('aria-busy',String(view.pending));counts.textContent=view.total===null?'Package count not available.':`${view.staged} / ${view.total} source entries staged${view.parts===null?'':` · ${view.parts} indexed parts`}. Source admission only, not indexing or overall completion.`;if(view.total===null){progress.removeAttribute('value');progress.max=1;}else{progress.max=Math.max(1,view.total);progress.value=view.staged;}for(const [name,button]of Object.entries(buttons))button.disabled=!view['can'+name[0].toUpperCase()+name.slice(1)];}});
 const listeners=Object.entries(buttons).map(([name,button])=>{const listener=()=>{void controller[name]();};button.addEventListener('click',listener);return ()=>button.removeEventListener('click',listener);});
 if(transport!==null)controller.connect(transport,manifestToken);
 return {connect:(value,token)=>controller.connect(value,token),dispose(){controller.dispose();for(const remove of listeners)remove();},get state(){return controller.state;}};
}
// Adapts the pinned Python dispatcher's compact ASCII JSON envelope. This is not authentication.
const IMPORT_REFUSALS=['unknown_selection','import_busy','use_explicit_retry','retry_refused','stale_job','attempt_limit','output_budget','invalid_request','response_bound','invalid_owner_response','command_refused','command_failed'];
export function createImportWireTransport(sendBytes){
 if(typeof sendBytes!=='function')throw Error('Trusted byte transport unavailable');
 async function command(action,value,options={}){
  const {signal}=options;if(signal?.aborted)throw Error('Import reception canceled');
  if(action!=='status'&&!importId(value))throw Error('Invalid opaque import identity');
  const request=new TextEncoder().encode(JSON.stringify({version:1,action,...(action==='status'?{}:{[action==='start'?'token':'job']:value})}));
  if(request.byteLength>1024)throw Error('Import request bound');
  const response=await Reflect.apply(sendBytes,undefined,[request,{signal}]);
  if(signal?.aborted)throw Error('Import reception canceled');
  if(!(response instanceof Uint8Array)||response.byteLength===0||response.byteLength>4096)throw Error('Import response bound');
  let envelope;try{
   const text=new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(response);envelope=JSON.parse(text);
   // The pinned host emits this exact compact ASCII form. This also rejects duplicate keys.
   if(JSON.stringify(envelope)!==text)throw Error();
  }catch{throw Error('Invalid import wire response');}
  const exact=keys=>envelope&&Object.getPrototypeOf(envelope)===Object.prototype&&Object.keys(envelope).sort().join()===keys.sort().join();
  if(envelope?.version!==1||typeof envelope?.ok!=='boolean')throw Error('Invalid import envelope');
  if(envelope.ok===false){if(!exact(['version','ok','error'])||!IMPORT_REFUSALS.includes(envelope.error))throw Error('Invalid import refusal');throw Error('Import command refused');}
  if(action==='status'){if(!exact(['version','ok','status']))throw Error('Invalid import status envelope');return validateImportStatus(envelope.status);}
  if(action==='cancel'){if(!exact(['version','ok']))throw Error('Invalid cancel acknowledgement');return;}
  if(!exact(['version','ok','job'])||!importId(envelope.job))throw Error('Invalid import job acknowledgement');return envelope.job;
 }
 return Object.freeze({status:options=>command('status',null,options),start:(token,options)=>command('start',token,options),retry:(job,options)=>command('retry',job,options),cancel:(job,options)=>command('cancel',job,options)});
}
// END EXACT TESTED IMPORT WORKFLOW
const $=selector=>document.querySelector(selector), form=$('#filters'), results=$('#results');
const importRoot=$('#catalog-import'),catalogImport=importRoot?.querySelector('[data-import="status"]')?bindCatalogImport({root:importRoot}):null;
// Explicit trusted-host injection is a cooperation contract, NOT browser authentication.
export function connectTrustedCatalogImport({transport,manifestToken}={}){return catalogImport?.connect(transport,manifestToken)??false;}

const text=(tag,value,className)=>{const el=document.createElement(tag);el.textContent=value;if(className)el.className=className;return el;};
// Dense summary keeps uncertainty visible; native disclosure retains every projected row field.
export function createCard(row,nameMode='preferred'){
 const card=text('article','','card'),body=text('div','','card-body'),title=itemTitle(row,nameMode);
 card.append(text('p','Image not projected','image-state'));const heading=text('h3',title);heading.title=title;body.append(heading);
 const author=row.author.state==='present'?`Author: ${row.author.name}`:row.author.state==='redacted'?'Author: redacted':'Author: unknown';const authorLine=text('p',author,'author');authorLine.title=author;body.append(authorLine);
 body.append(text('p',`Verification: ${row.creator_verified===true?'explicitly verified':row.creator_verified===false?'explicitly unverified':'unknown'}`,'verification'));
 body.append(text('p',`${row.origin===null?'Unknown origin':row.origin.toUpperCase()} · Type ${row.body_type??'unknown'}`,'type-origin'));
 if(row.swatch_colors_argb?.length){const colors=text('div','','swatches');colors.tabIndex=0;colors.setAttribute('role','group');colors.setAttribute('aria-label',`Authored ARGB swatches (${row.swatch_colors_argb.length}), not perceived colors`);body.append(text('p',`Authored ARGB (${row.swatch_colors_argb.length})`,'color-label'));for(const argb of row.swatch_colors_argb){const label=`Authored ARGB #${argb.toString(16).padStart(8,'0').toUpperCase()}`;const chip=text('span','','chip');chip.style.backgroundColor=`#${(argb&0xffffff).toString(16).padStart(6,'0')}${(argb>>>24).toString(16).padStart(2,'0')}`;chip.title=label;chip.setAttribute('aria-label',label);chip.setAttribute('role','img');colors.append(chip);}body.append(colors);}else body.append(text('p',row.swatch_colors_argb===null?'Authored swatches: unknown':'Authored swatches: none recorded','color-label'));
 const details=text('details','','metadata-details');details.append(text('summary','Full metadata'));const list=document.createElement('dl');
 const fields=[['Display title',title],['Name',row.name],['Preferred name',row.preferred_name],['Package name',row.package_name],['Code name',row.code_name],['Part ID',row.part_id],['Family ID',row.family_id],['Package SHA256',row.package_sha256],['Resource SHA256',row.resource_sha256],['Resource TGI',row.resource_tgi],['Origin',row.origin],['Body type',row.body_type],['Author name',row.author.name],['Author state',row.author.state],['Author verified',row.author.verified],['Creator verified',row.creator_verified],['Creator source',row.creator_source],['Thumbnail state',row.thumbnail.state],['Thumbnail URL',row.thumbnail.url],['Image state',row.image_state],['Image available',row.image_available],['Equip allowed',row.equip_allowed],['Authored ARGB values',row.swatch_colors_argb===null?null:row.swatch_colors_argb.map(n=>'#'+n.toString(16).padStart(8,'0').toUpperCase()).join(', ')||'None recorded']];
 for(const [label,value] of fields){list.append(text('dt',label),text('dd',value===null?'Unknown / not projected':String(value)));}details.append(list);body.append(details);card.append(body);return card;
}
const IMAGE_LABELS={pending:'Source image: checking companion',loading:'Source image: loading pinned PNG',ready:'Source thumbnail · inspection only',disabled:'Source images disabled · metadata only',missing:'Prepared image cache missing',unqualified:'Source image unqualified in snapshot',changed:'Source image identity changed',unsupported:'Source image unsupported',overbudget:'Source image budget exceeded',conflicting:'Source image identity conflict','wrong-catalog':'Source image catalog mismatch',unavailable:'Source image unavailable'};
export function updateSourceImage(card,part,entry,failDecode=()=>{}){
 let slot=card.querySelector('.image-state');if(!slot||card.sourceImageEntry===entry)return;card.sourceImageEntry=entry;
 slot.replaceChildren();slot.className='image-state'+(entry.row?' source-image-slot':'');
 slot.append(text('span',IMAGE_LABELS[entry.state]||IMAGE_LABELS.unavailable));
 if(entry.state==='ready'&&typeof entry.url==='string'&&entry.url.startsWith('blob:')){
  const img=document.createElement('img');img.width=40;img.height=57;img.alt='Prepared source thumbnail; not compatibility or equip evidence';img.decoding='async';
  img.addEventListener('error',()=>failDecode(part,entry.url));img.addEventListener('load',()=>{if(img.naturalWidth!==104||img.naturalHeight!==148)failDecode(part,entry.url);});
  img.src=entry.url;slot.append(img);
 }
 const details=card.querySelector('details');if(!details)return;let evidence=details.querySelector('.source-image-evidence');if(!evidence){evidence=text('div','','source-image-evidence');details.append(evidence);}evidence.replaceChildren(text('p','Companion source image (independent of metadata projection)'));
 const fields=[['Companion state',entry.state],['Coverage','Prepared snapshot only; not live Mods or whole-library coverage'],['Equip / compatibility evidence','None']];
 if(entry.index)fields.push(['Catalog SHA256',entry.index.catalog_sha256],['Image index SHA256',entry.index.index_sha256],['Image manifest SHA256',entry.index.manifest_sha256]);
 if(entry.row)fields.push(['Companion part ID',entry.row.part_id],['Image asset ID',entry.row.asset_id],['PNG SHA256',entry.row.png_sha256],['PNG dimensions',`${entry.row.width} × ${entry.row.height}`],['PNG bytes',entry.row.byte_count]);
 const list=document.createElement('dl');for(const [label,value] of fields)list.append(text('dt',label),text('dd',String(value)));evidence.append(list);
}
const sourceImages=new SourceImages({onChange:(part,entry)=>{for(const card of Array.from(results.children).filter(node=>node.dataset.partId===part))updateSourceImage(card,part,entry,(id,url)=>sourceImages.failDecode(id,url));}});
let renderedPage=null,renderedFacets=null,renderedPageKey=null,renderedContent=null,pageNavigationRequested=false;
function completeness(value){return value===true?'complete':value===false?'incomplete':'unknown';}
export function render(browser){
 $('#status').textContent=browser.message;$('#status').dataset.state=browser.state;
 $('#folder-sort-status').textContent=!browser.identity?'Folder sorting unavailable: no ready catalog helper.':browser.folderSort==='unsupported'?'Folder sorting unavailable for this index/helper. Other sorts remain available.':browser.folderSort==='supported'?'Folder sorting accepted by this helper. Ordering uses the indexed folder key, not a source path.':'Folder sorting uses the indexed folder key. Support is checked on first use; no folder paths are inferred.';
 $('#query-fields').disabled=!browser.identity;$('#recheck').disabled=browser.state==='loading';results.setAttribute('aria-busy',String(browser.state==='loading'));
 const stale=browser.page&& !['ready','empty'].includes(browser.state);
 $('#coverage').textContent=browser.page?`${stale?'LAST GOOD PAGE · stale while filters or availability are unresolved. ':''}Snapshot ${completeness(browser.page.snapshot_complete)} · Package inventory ${browser.page.package_inventory_coverage} · Source errors ${browser.page.source_errors_count??'unknown'} · Redacted fields ${browser.page.projection_redactions}`:'Snapshot completeness unknown. No catalog page accepted yet.';
 $('#identity').textContent=browser.identity?`Epoch ${browser.identity.epoch} · Catalog ${browser.identity.catalog_sha256} · Identity policy ${browser.identity.policy}`:'No ready catalog identity.';
 if(browser.facets!==renderedFacets){renderedFacets=browser.facets;const f=browser.facets;$('#authors').replaceChildren(...(f?.creators??[]).filter(c=>c.name_state==='present'&&c.name).map(c=>{const o=text('option',`${c.name} (${c.count})`);o.value=c.name;return o;}));$('#types').replaceChildren(...(f?.categories??[]).filter(c=>c.body_type!==null).map(c=>{const o=text('option',`${c.count} indexed`);o.value=String(c.body_type);return o;}));$('#author-note').textContent=f?`Author inventory ${f.included?'included':'not included'}; completeness ${completeness(f.complete)}. Unknown or redacted authors are not guessed.`:'Author inventory not loaded.';}
 if(browser.page&&browser.page!==renderedPage&&['ready','empty'].includes(browser.state)){
  const p=browser.page,key=JSON.stringify([p.epoch,p.catalog_sha256,browser.pageQuery]),signature=JSON.stringify([p.items,browser.pageQuery.name_mode]);
  const changedPage=key!==renderedPageKey;
  if(signature!==renderedContent){
   const expanded=new Set(Array.from(results.children).filter(card=>card.querySelector('details')?.open).map(card=>card.dataset.partId));
   results.replaceChildren();for(const row of p.items){const card=createCard(row,browser.pageQuery.name_mode);card.dataset.partId=row.part_id;if(expanded.has(row.part_id))card.querySelector('details').open=true;results.append(card);}
   if(!p.items.length)results.append(text('p','No matching metadata. Try broader filters.','empty'));
  }
  renderedPage=p;renderedPageKey=key;renderedContent=signature;
  // Unsupported companion IDs must never invalidate an otherwise accepted metadata page.
  const imageCatalog=/^[a-f0-9]{64}$/.test(p.catalog_sha256),imageParts=[...new Set(p.items.map(row=>row.part_id).filter(id=>/^[a-f0-9]{64}$/.test(id)))];
  if(imageCatalog)sourceImages.setPage(p.catalog_sha256,imageParts);else sourceImages.reset();
  for(const card of Array.from(results.children))if(card.dataset.partId&&(!imageCatalog||!imageParts.includes(card.dataset.partId)))updateSourceImage(card,card.dataset.partId,{state:'unqualified'});
  if(changedPage){
   const heading=$('#results-heading'),active=document.activeElement;
   // Only the results owner moves: no scrollIntoView on desktop (it can move ancestors).
   if(window.matchMedia('(max-width: 700px)').matches)heading.scrollIntoView({block:'start',behavior:'instant'});
   else $('.library').scrollTo({top:0,behavior:'instant'});
   if(active===$('#previous')||active===$('#next')||(pageNavigationRequested&&active===document.body))heading.focus({preventScroll:true});
  }
  pageNavigationRequested=false;
 }
 if(['error','invalid','unavailable','unsupported'].includes(browser.state))pageNavigationRequested=false;
 const p=browser.page, canPage=!!browser.identity&&['ready','empty'].includes(browser.state);$('#previous').disabled=!canPage||!p||p.offset===0;$('#next').disabled=!canPage||!p||p.next_offset===null;$('#page-label').textContent=p?`${p.items.length?`${p.offset+1}–${p.offset+p.items.length}`:'0 results'} of ${p.total.toLocaleString()}${p.grouped?' · grouped':''}`:'No page loaded';
}
const browser=new CatalogBrowser({onChange:render});
function query(){const data=new FormData(form),number=name=>data.get(name)===''?null:/^\d+$/.test(data.get(name))?Number(data.get(name)):NaN;return {text:data.get('text'),folder:data.get('folder'),author:data.get('author'),body_type:number('body_type'),origin:data.get('origin')||null,sort:data.get('sort'),name_mode:data.get('name_mode'),added_days:number('added_days'),grouped:data.has('grouped'),fuzzy:data.has('fuzzy'),offset:0};}
let debounce;
export function resetFilters(){if(!browser.identity||browser.disposed)return;clearTimeout(debounce);pageNavigationRequested=false;form.reset();browser.request(query());form.elements.namedItem('text')?.focus({preventScroll:true});}
$('#reset-filters').addEventListener('click',resetFilters);
form.addEventListener('submit',event=>{event.preventDefault();pageNavigationRequested=false;clearTimeout(debounce);browser.request(query());});
form.addEventListener('input',()=>{pageNavigationRequested=false;clearTimeout(debounce);debounce=setTimeout(()=>browser.request(query()),220);});
$('#previous').addEventListener('click',()=>{pageNavigationRequested=true;browser.request({...browser.pageQuery,offset:Math.max(0,browser.page.offset-PAGE_SIZE)});});
$('#next').addEventListener('click',()=>{pageNavigationRequested=true;browser.request({...browser.pageQuery,offset:browser.page.next_offset});});
$('#recheck').addEventListener('click',()=>{pageNavigationRequested=false;browser.recheck();});
window.addEventListener('pagehide',()=>{catalogImport?.dispose();clearTimeout(debounce);sourceImages.close();browser.dispose();});
window.addEventListener('pageshow',event=>{if(event.persisted)location.reload();});
browser.recheck();
