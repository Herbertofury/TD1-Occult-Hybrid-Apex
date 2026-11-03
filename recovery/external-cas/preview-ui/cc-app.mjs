import {routeHistoryShortcut} from './history-shortcuts.mjs';
import {CcHistory,CC_DEFAULTS} from './cc-history.mjs';
import {PreviewController} from './controller.mjs';
import {createFrameClient} from './frame-client.mjs';
const canvas=document.querySelector('canvas'),context=canvas.getContext('2d');
const fields=['yaw','pose','brightness','saturation','hue','opacity'];
const status=document.querySelector('#status'),metrics=document.querySelector('#metrics'),identity=document.querySelector('#identity');
const client=createFrameClient({mode:'cc',timeoutMs:15000});
const controller=new PreviewController(request=>client.read(request),(frame,request)=>{
 context.putImageData(new ImageData(frame.rgba,512,512),0,0);
 document.querySelector('#pose').disabled=!frame.poseReady;
 canvas.dataset.scene=frame.scene;canvas.dataset.harness=frame.harness;canvas.dataset.sequence=String(request.sequence);
 canvas.dataset.parameters=JSON.stringify(Object.fromEntries(fields.map(k=>[k,request[k]])));
 identity.textContent=`${frame.harness} · ${frame.renderer} · scene ${frame.scene}`;
 metrics.textContent=`Render ${frame.cpuMs??'?'} ms · request ${frame.fetchMs.toFixed(1)} ms. Offline diagnostic; not game FPS.`;
},message=>{status.textContent=message;});
const history=new CcHistory();let historyError='';
const undo=document.querySelector('#undo'),redo=document.querySelector('#redo'),branches=document.querySelector('#branches'),historyStatus=document.querySelector('#history-status');
function syncHistory(){
 undo.disabled=!history.canUndo;redo.disabled=history.pending||history.branches.length===0;
 branches.replaceChildren(...history.branches.map(branch=>{const option=document.createElement('option');option.value=String(branch.id);option.textContent=`Edit ${branch.id}: arm ${branch.value.pose}, hue ${branch.value.hue}, brightness ${branch.value.brightness}, saturation ${branch.value.saturation}, opacity ${branch.value.opacity}, yaw ${branch.value.yaw}`;return option;}));
 if(history.branches.length)branches.value=String(history.branches.at(-1).id);
 branches.disabled=redo.disabled;
 historyStatus.textContent=`Session preview history: ${history.nodes.length}/${history.capacity} states. ${history.pending?'Uncommitted slider gesture.':'No game or collection writes.'} ${historyError}`;
}
function renderValue(){for(const name of fields)document.getElementById(name).value=String(history.value[name]);syncHistory();controller.request(history.value);}
function update(){try{history.stage(Object.fromEntries(fields.map(k=>[k,Number(document.getElementById(k).value)])));syncHistory();controller.request(history.value);}catch(error){status.textContent=error.message;}}
function commit(){try{history.commit();historyError='';syncHistory();}catch(error){historyError=error.message;renderValue();}}
for(const name of fields){const field=document.getElementById(name);field.addEventListener('input',update);field.addEventListener('change',commit);}
undo.addEventListener('click',()=>{history.undo();renderValue();});
redo.addEventListener('click',()=>{try{history.redo(Number(branches.value));renderValue();}catch(error){status.textContent=error.message;}});
document.querySelector('#reset').addEventListener('click',()=>{history.stage(CC_DEFAULTS);commit();renderValue();});
document.querySelector('#close').addEventListener('click',()=>{controller.close();if(history.pending){history.undo();renderValue();}});
document.querySelector('#open').addEventListener('click',()=>{controller.open();renderValue();});
// BFCache preserves this module and DOM, but pagehide retires the render epoch.
// Restore the user's open/closed choice without changing history or committing edits.
let reopenAfterNavigation=false;
window.addEventListener('pagehide',()=>{reopenAfterNavigation=controller.opened;controller.close();});
window.addEventListener('pageshow',event=>{if(event.persisted&&reopenAfterNavigation){reopenAfterNavigation=false;controller.open();renderValue();}});
controller.open();renderValue();

document.addEventListener('keydown',event=>routeHistoryShortcut(event,{undo,redo}));
