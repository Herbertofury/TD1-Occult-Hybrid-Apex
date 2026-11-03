import {readLimited,abortable} from './frame-client.mjs';
// Bounded resource ownership survives list rebuilds; never re-fetch the same identity per card.
export class ThumbnailPool {
 constructor({fetchImpl=globalThis.fetch,makeURL=b=>URL.createObjectURL(new Blob([b],{type:'image/png'})),revokeURL=u=>URL.revokeObjectURL(u),workers=2,maxBytes=16*1024*1024,maxDecodedBytes=32*1024*1024}={}){
  if(!Number.isInteger(workers)||workers<1||workers>2||!Number.isInteger(maxBytes)||maxBytes<24||maxBytes>16*1024*1024||!Number.isInteger(maxDecodedBytes)||maxDecodedBytes<4||maxDecodedBytes>32*1024*1024)throw Error('Thumbnail budget');Object.assign(this,{fetchImpl,makeURL,revokeURL,workers,maxBytes,maxDecodedBytes});this.entries=new Map();this.queue=[];this.active=0;this.usedBytes=0;this.usedDecodedBytes=0;this.urls=[];this.closed=false;this.abort=new AbortController();
 }
 get(file){
  if(this.closed)return Promise.reject(Error('Thumbnail pool closed'));
  if(!/^[a-f0-9]{64}\.png$/.test(file))return Promise.reject(Error('Thumbnail identity'));
  if(this.entries.has(file))return this.entries.get(file);
  if(this.entries.size>=1024)return Promise.reject(Error('Thumbnail entry bound'));
  let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});this.entries.set(file,promise);this.queue.push({file,resolve,reject});this.pump();return promise;
 }
 pump(){while(!this.closed&&this.active<this.workers&&this.queue.length){const job=this.queue.shift();this.active++;this.load(job).finally(()=>{this.active--;this.pump();});}}
 async load(job){
  const abort=new AbortController(),stop=()=>abort.abort(Error('Thumbnail pool closed'));this.abort.signal.addEventListener('abort',stop,{once:true});const timer=setTimeout(()=>abort.abort(Error('Thumbnail deadline')),10000);
  try{const fetchImpl=this.fetchImpl;const response=await abortable(fetchImpl('/pose-image/'+job.file,{signal:abort.signal,cache:'no-store',redirect:'error',credentials:'same-origin'}),abort.signal);if(response.status!==200||(response.headers.get('content-type')||'').split(';')[0]!=='image/png'){try{response.body?.cancel().catch(()=>{});}catch{}throw Error('Thumbnail response refused');}const bytes=await readLimited(response,{maxBytes:512*1024,signal:abort.signal});if(bytes.length<24||[137,80,78,71,13,10,26,10].some((v,i)=>bytes[i]!==v))throw Error('Thumbnail PNG header');const view=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);if(view.getUint32(8)!==13||String.fromCharCode(...bytes.slice(12,16))!=='IHDR')throw Error('Thumbnail IHDR');for(const at of [16,20])if(view.getUint32(at)<1||view.getUint32(at)>512)throw Error('Thumbnail dimensions');const decodedBytes=view.getUint32(16)*view.getUint32(20)*4;if(this.closed||this.usedBytes+bytes.length>this.maxBytes||this.usedDecodedBytes+decodedBytes>this.maxDecodedBytes)throw Error('Thumbnail memory bound or closed');const url=this.makeURL(bytes);this.urls.push(url);this.usedBytes+=bytes.length;this.usedDecodedBytes+=decodedBytes;job.resolve(url);
  }catch(error){job.reject(error);}finally{clearTimeout(timer);abort.abort();this.abort.signal.removeEventListener('abort',stop);}
 }
 close(){if(this.closed)return;this.closed=true;this.abort.abort();for(const job of this.queue.splice(0))job.reject(Error('Thumbnail pool closed'));for(const url of this.urls)this.revokeURL(url);this.urls=[];this.usedBytes=0;this.usedDecodedBytes=0;}
}
