import {createFrameClient} from './frame-client.mjs';
import {PreviewController} from './controller.mjs';
const canvas=document.querySelector('canvas'),ctx=canvas.getContext('2d');
const yaw=document.querySelector('#yaw'),pose=document.querySelector('#pose'),morph=document.querySelector('#morph'),format=document.querySelector('#format'),headerOption=document.querySelector('#headers');
const status=document.querySelector('#status'),metrics=document.querySelector('#metrics'),trace=document.querySelector('#trace'),identityLabel=document.querySelector('#identity');
let benchmarkEpoch=0,benchmarkResolve=null,benchmarkActive=false;const observations=[];
const longTasks=[];let longTaskDropped=0;
let longTaskSupported=false,longTaskObserver=null;
function captureTasks(entries){if(!benchmarkActive)return;for(const entry of entries){if(longTasks.length<256)longTasks.push({startTime:entry.startTime,duration:entry.duration});else longTaskDropped++;}}
try{if(typeof PerformanceObserver!=='undefined'&&PerformanceObserver.supportedEntryTypes?.includes('longtask')){longTaskObserver=new PerformanceObserver(list=>captureTasks(list.getEntries()));longTaskObserver.observe({type:'longtask',buffered:true});longTaskSupported=true;}}catch{longTaskObserver?.disconnect();longTaskObserver=null;}
function writeTimingTrace(){if(longTaskObserver)captureTasks(longTaskObserver.takeRecords());document.querySelector('#timingTrace').textContent=JSON.stringify({supported:Boolean(longTaskSupported),dropped:longTaskDropped,entries:longTasks},null,2);}
const frameClient=createFrameClient();
const controller=new PreviewController(async request=>{
 const frame=await frameClient.read(request);
 return {...frame,pixels:new ImageData(frame.rgba,512,512)};
},(frame,request)=>{
 const before=performance.now();ctx.putImageData(frame.pixels,0,0);const drawn=performance.now();
 const verifiedIdentity=`${frame.harness} / ${frame.scene}`;if(identityLabel.textContent!==verifiedIdentity)identityLabel.textContent=verifiedIdentity;
 frame.drawMs=drawn-before;frame.totalMs=drawn-frame.start;
 metrics.textContent=`Request ${request.sequence}; request through canvas submission ${frame.totalMs.toFixed(1)} ms; conversion ${frame.convertMs.toFixed(2)} ms; Rust ${frame.cpuMs??'unreported'} ms [${frame.renderer}/io${frame.httpWorkers}]`;
 Object.assign(canvas.dataset,{sequence:String(request.sequence),yaw:String(request.yaw),pose:String(request.pose),morph:String(request.morph),format:request.format,scene:frame.scene,renderer:frame.renderer,httpWorkers:String(frame.httpWorkers)});
 if(benchmarkResolve){const resolve=benchmarkResolve;benchmarkResolve=null;resolve({frame,request});}
},message=>{
 status.textContent=message;
 if(message.startsWith('Failed')&&benchmarkResolve){const resolve=benchmarkResolve;benchmarkResolve=null;resolve({error:message});}
});
function cancelBenchmark(){writeTimingTrace();if(benchmarkActive)document.querySelector('#measurementStatus').textContent='Measurement canceled';benchmarkActive=false;benchmarkEpoch++;if(benchmarkResolve){const resolve=benchmarkResolve;benchmarkResolve=null;resolve({error:'canceled'});}for(const el of document.querySelectorAll('input,select,#benchmark'))el.disabled=false;}
function update(){cancelBenchmark();controller.request({yaw:Number(yaw.value),pose:Number(pose.value),morph:Number(morph.value),format:format.value,header:headerOption.value});}
for(const el of [yaw,pose,morph,format,headerOption])el.addEventListener('input',update);
document.querySelector('#close').onclick=()=>{cancelBenchmark();controller.close();ctx.clearRect(0,0,512,512);delete canvas.dataset.sequence;};
document.querySelector('#open').onclick=()=>{cancelBenchmark();controller.open();update();};
document.querySelector('#reset').onclick=()=>{yaw.value='0';pose.value='0';morph.value='0';update();};
document.querySelector('#benchmark').onclick=async()=>{
 cancelBenchmark();controller.open();const token=benchmarkEpoch;observations.length=0;trace.textContent='[]';document.querySelector('#measurementStatus').textContent='Measuring';benchmarkActive=true;longTasks.length=0;longTaskDropped=0;if(longTaskObserver)longTaskObserver.takeRecords();document.querySelector('#timingTrace').textContent='{}';
 for(const el of document.querySelectorAll('input,select,#benchmark'))el.disabled=true;
 try {
  for(let pair=0;pair<16;pair++){
   const modes=[['rgb','split'],['rgba','split'],['rgb','joined'],['rgba','joined'],['rgb','vectored'],['rgba','vectored']];const order=modes.slice(pair%modes.length).concat(modes.slice(0,pair%modes.length));
   for(const [mode,header] of order){
    if(token!==benchmarkEpoch||!controller.opened)return;
    const result=await new Promise(resolve=>{benchmarkResolve=resolve;controller.request({yaw:pair*7,pose:pair*3,morph:pair*6,format:mode,header});});
    if(result.error)throw new Error(result.error);
    const digest=await crypto.subtle.digest('SHA-256',result.frame.pixels.data);
    if(token!==benchmarkEpoch||!controller.opened)return;
    const f=result.frame;
    observations.push({pair,startedAt:f.start,submittedAt:f.start+f.totalMs,renderer:f.renderer,httpWorkers:f.httpWorkers,identityMs:f.identityMs,headersMs:f.headersMs,bodyMs:f.bodyMs,serverHeaderMs:f.serverHeaderMs,serverWaitMs:f.serverWaitMs,mode:mode+'-'+header,format:mode,header,fetchMs:f.fetchMs,convertMs:f.convertMs,drawMs:f.drawMs,totalMs:f.totalMs,cpuMs:f.cpuMs,bytes:f.bytes,pixelSha256:[...new Uint8Array(digest)].map(x=>x.toString(16).padStart(2,'0')).join('')});
    trace.textContent=JSON.stringify(observations,null,2);
   }
  }
  document.querySelector('#measurementStatus').textContent='Measurement complete; full pixel hashes retained. Not game FPS.';
  controller.request({yaw:Number(yaw.value),pose:Number(pose.value),morph:Number(morph.value),format:format.value,header:headerOption.value});
 }catch(error){if(token===benchmarkEpoch)status.textContent='Measurement stopped: '+error.message;}
 finally{writeTimingTrace();if(token===benchmarkEpoch)benchmarkActive=false;if(token===benchmarkEpoch)for(const el of document.querySelectorAll('input,select,#benchmark'))el.disabled=false;}
};
// Navigation ends measurement ownership; BFCache must not silently resume a benchmark.
let reopenAfterNavigation=false;
window.addEventListener('pagehide',()=>{reopenAfterNavigation=controller.opened;cancelBenchmark();controller.close();});
window.addEventListener('pageshow',event=>{if(event.persisted&&reopenAfterNavigation){reopenAfterNavigation=false;controller.open();update();}});
controller.open();update();
