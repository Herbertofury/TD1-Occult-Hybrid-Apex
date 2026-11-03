import {ACCESSORY_IDS} from './accessory-model.mjs';
import {SWATCH_ID} from './swatch-model.mjs';
// Fixed-buffer reader reuses the Engineering Atlas job-submit/audio reader pattern.
// No unbounded arrayBuffer()/json() call before checking the stream budget.
export async function readLimited(response,{maxBytes,exact=false,signal,chunkLimit=8192}){
 if(!Number.isInteger(maxBytes)||maxBytes<1||maxBytes>1048576||!Number.isInteger(chunkLimit)||chunkLimit<1||chunkLimit>8192)throw Error('Invalid byte/chunk budget');
 const length=response.headers.get('content-length');
 const reject=message=>{try{response.body?.cancel().catch(()=>{});}catch{}throw Error(message);};
 if(length!==null&&(length.length>32||!/^[0-9]+$/.test(length)||BigInt(length)>BigInt(maxBytes)||(exact&&BigInt(length)!==BigInt(maxBytes))))return reject('Response length exceeds or differs from expected bound');
 if(!response.body)return reject('Missing byte stream');
 const reader=response.body.getReader(),bytes=new Uint8Array(maxBytes);let used=0,chunks=0,abort;
 const aborted=new Promise((_,reject)=>{abort=()=>reject(signal.reason||Error('Aborted'));signal?.addEventListener('abort',abort,{once:true});});
 try{
  if(signal?.aborted)throw signal.reason||Error('Aborted');
  for(;;){const {done,value}=await Promise.race([reader.read(),aborted]);if(done)break;
   if(++chunks>chunkLimit||!(value instanceof Uint8Array)||used+value.byteLength>maxBytes)throw Error('Response byte/chunk budget exceeded');
   bytes.set(value,used);used+=value.byteLength;
  }
  if(used===0||(exact&&used!==maxBytes)||(length!==null&&BigInt(used)!==BigInt(length)))throw Error('Incomplete response');
  if(signal?.aborted)throw signal.reason||Error('Aborted');
  return used===maxBytes?bytes:bytes.slice(0,used);
 }catch(error){try{reader.cancel().catch(()=>{});}catch{}throw error;}
 finally{signal?.removeEventListener('abort',abort);try{reader.releaseLock();}catch{}}
}
function discard(response){try{response.body?.cancel().catch(()=>{});}catch{}}
export async function abortable(promise,signal){let listener;const aborted=new Promise((_,reject)=>{listener=()=>reject(signal.reason||Error('Aborted'));if(signal.aborted)listener();else signal.addEventListener('abort',listener,{once:true});});const observed=Promise.resolve(promise).then(value=>{if(signal.aborted){if(value?.body)discard(value);throw signal.reason;}return value;});try{return await Promise.race([observed,aborted]);}finally{signal.removeEventListener('abort',listener);}}
export function createFrameClient({fetchImpl=globalThis.fetch,harness='apex-rust-preview-20261102-v71-import-ui-candidate',timeoutMs=5000,mode="pose"}={}){
 if(!['pose','cc','clip'].includes(mode))throw Error('Invalid client mode');
 if(!Number.isInteger(timeoutMs)||timeoutMs<1||timeoutMs>30000)throw Error('Invalid frame deadline');
 let identity=null;
 async function identityFor(signal){
  if(identity)return identity;
  const response=await abortable(fetchImpl('/identity',{signal,cache:'no-store',redirect:'error',credentials:'same-origin'}),signal);
  if(response.status!==200||!/^application\/json(?:;\s*charset=utf-8)?$/i.test(response.headers.get('content-type')||'')){discard(response);throw Error('Invalid scene identity response');}
  const bytes=await readLimited(response,{maxBytes:4096,signal});
  const parsed=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));
  if(!parsed||typeof parsed!=='object'||Array.isArray(parsed)||parsed.harness!==harness||typeof parsed.scene_sha256!=='string'||!/^[a-f0-9]{64}$/.test(parsed.scene_sha256)||!(mode!=='pose'?['serial-cc','pooled-cc-1','pooled-cc-2','pooled-cc-4']:['serial','serial-opaque','tiled-1','tiled-2','tiled-3','tiled-4']).includes(parsed.renderer)||!Number.isInteger(parsed.http_workers)||parsed.http_workers<1||parsed.http_workers>4)throw Error('Invalid scene identity');
  if(parsed.pose_ready!==undefined&&typeof parsed.pose_ready!=='boolean')throw Error('Invalid scene identity capability');
  if(parsed.pose_library_ready!==undefined&&typeof parsed.pose_library_ready!=='boolean')throw Error('Invalid pose library capability');
  identity=Object.freeze({harness,scene:parsed.scene_sha256,renderer:parsed.renderer,httpWorkers:parsed.http_workers,poseReady:parsed.pose_ready===true,poseLibraryReady:parsed.pose_library_ready===true});return identity;
 }
 return {async read(request){
  let path;
  const hasAccessory=['accessoryId','accessoryCatalog','accessoryScene'].some(key=>request[key]!==undefined);
  if(hasAccessory&&(mode!=='clip'||!ACCESSORY_IDS.includes(request.accessoryId)||typeof request.accessoryCatalog!=='string'||!/^[a-f0-9]{64}$/.test(request.accessoryCatalog)||typeof request.accessoryScene!=='string'||!/^[a-f0-9]{64}$/.test(request.accessoryScene)))throw Error('Invalid prepared accessory identity');
  if(request.swatchId!==undefined&&(mode!=='clip'||typeof request.swatchId!=='string'||!SWATCH_ID.test(request.swatchId)))throw Error('Invalid swatch identity');
  if(request.catalogScene!==undefined&&(typeof request.catalogScene!=='string'||!/^[a-f0-9]{64}$/.test(request.catalogScene)))throw Error('Invalid catalog scene');
  if(mode==='cc'||mode==='clip') {
   if((request.pose!==undefined&&(!Number.isInteger(request.pose)||Math.abs(request.pose)>90))||!Number.isInteger(request.yaw)||Math.abs(request.yaw)>180||!['brightness','saturation','hue'].every(k=>Number.isInteger(request[k])&&Math.abs(request[k])<=8192)||!Number.isInteger(request.opacity)||request.opacity<3277||request.opacity>16384)throw Error('Invalid CC parameters');
   path=`/cc-frame?yaw=${request.yaw}&brightness=${request.brightness}&saturation=${request.saturation}&hue=${request.hue}&opacity=${request.opacity}${request.pose===undefined?'':`&pose=${request.pose}`}`;
   if(mode==='clip'){if(typeof request.clipId!=='string'||!/^[a-f0-9]{64}$/.test(request.clipId)||!Number.isInteger(request.frame)||request.frame<0||request.frame>=2048)throw Error('Invalid clip selection');path=`/clip-frame?clip=${request.clipId}&frame=${request.frame}&yaw=${request.yaw}&brightness=${request.brightness}&saturation=${request.saturation}&hue=${request.hue}&opacity=${request.opacity}`;}
   if(mode==='clip'&&request.swatchId!==undefined)path+=`&swatch=${request.swatchId}`;
   if(hasAccessory)path+=`&accessory=${request.accessoryId}&accessory_catalog=${request.accessoryCatalog}&accessory_scene=${request.accessoryScene}`;
   request={...request,format:'rgb'};
  } else {
  if(!Number.isInteger(request.yaw)||Math.abs(request.yaw)>180||!Number.isInteger(request.pose)||Math.abs(request.pose)>90||!Number.isInteger(request.morph)||request.morph<0||request.morph>100||!['rgb','rgba'].includes(request.format)||!['split','joined','vectored'].includes(request.header))throw Error('Invalid preview parameters');
   path=`/frame?yaw=${request.yaw}&pose=${request.pose}&morph=${request.morph}&format=${request.format}&header=${request.header}`;
  }

  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(Error('Frame deadline exceeded')),timeoutMs);const start=performance.now();
  try{
   const expected=await identityFor(controller.signal);if(hasAccessory&&request.accessoryScene!==expected.scene)throw Error('Accessory catalog scene changed');if(request.catalogScene!==undefined&&request.catalogScene!==expected.scene)throw Error('Swatch catalog scene changed');if(mode==='cc'&&(request.pose??0)!==0&&!expected.poseReady)throw Error('Verified pose rig is unavailable');if(mode==='clip'&&!expected.poseLibraryReady)throw Error('Verified pose library is unavailable');const requestAt=performance.now();
   const response=await abortable(fetchImpl(path,{signal:controller.signal,cache:'no-store',redirect:'error',credentials:'same-origin'}),controller.signal);
   const headersAt=performance.now();
   if(response.status!==200||(response.headers.get('content-type')||'').split(';')[0].trim()!=='application/octet-stream'){discard(response);throw Error('Invalid frame response');}
   if(response.headers.get('X-Harness')!==expected.harness||response.headers.get('X-Scene')!==expected.scene||response.headers.get('X-Renderer')!==expected.renderer||response.headers.get('X-HTTP-Workers')!==String(expected.httpWorkers)){try{response.body?.cancel().catch(()=>{});}catch{}throw Error('Scene identity changed; reload before accepting another scene');}
   if(mode==='clip'&&(response.headers.get('X-Clip-ID')!==request.clipId||response.headers.get('X-Clip-Frame')!==String(request.frame))){discard(response);throw Error('Clip identity or frame changed');}
   if(request.swatchId!==undefined&&response.headers.get('X-Swatch-ID')!==request.swatchId){discard(response);throw Error('Swatch identity changed');}
   if(hasAccessory&&(response.headers.get('X-Accessory-ID')!==request.accessoryId||response.headers.get('X-Accessory-Catalog')!==request.accessoryCatalog)){discard(response);throw Error('Accessory identity changed');}
   const raw=await readLimited(response,{maxBytes:512*512*(request.format==='rgba'?4:3),exact:true,signal:controller.signal});const received=performance.now();let rgba;
   if(request.format==='rgba'){for(let i=3;i<raw.length;i+=4)if(raw[i]!==255)throw Error('Non-opaque pixel in opaque preview');rgba=new Uint8ClampedArray(raw.buffer,raw.byteOffset,raw.byteLength);}
   else {rgba=new Uint8ClampedArray(512*512*4);for(let i=0,j=0;i<raw.length;i+=3,j+=4){rgba[j]=raw[i];rgba[j+1]=raw[i+1];rgba[j+2]=raw[i+2];rgba[j+3]=255;}}
   const timing=name=>{const raw=response.headers.get(name);return raw!==null&&raw.trim()!==""&&Number.isFinite(Number(raw))&&Number(raw)>=0?Number(raw):null;};
   return {rgba,start,poseReady:expected.poseReady,harness:expected.harness,identityMs:requestAt-start,headersMs:headersAt-requestAt,bodyMs:received-headersAt,serverHeaderMs:timing("X-Header-Read-Ms"),serverAdmissionMs:timing("X-Admission-Wait-Ms"),serverWaitMs:timing("X-Render-Wait-Ms"),httpWorkers:expected.httpWorkers,fetchMs:received-start,convertMs:performance.now()-received,cpuMs:timing("X-Render-Ms"),bytes:raw.byteLength,scene:expected.scene,renderer:expected.renderer};
  }finally{clearTimeout(timer);controller.abort();}
 },get scene(){return identity?.scene??null;}};
}
