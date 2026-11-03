// Side-effect-free diagnostic. This module owns no normal pose, material or history state.
import {ACCESSORY_IDS} from './accessory-model.mjs';
import {readLimited,abortable} from './frame-client.mjs';
export const INSPECTION_SCOPE='head-reference-hair-dress-shoes-hidden-v1';
export const INSPECTION_FRAMING='cc9df76bcbb0f7a922f4847d3d947775a47bb0773b355e83e7c44b1220552069';
export const INSPECTION_SAMPLES=Object.freeze([0,62,361]);
const digest=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
const sameContext=(a,b)=>a&&b&&['scene','catalog','accessoryId','normalClipId','normalFrame','normalRevision','playing'].every(key=>a[key]===b[key]);
function checkedContext(value){
 if(!value||value.enabled!==true)return null;
 if(!digest(value.scene)||!digest(value.catalog)||!ACCESSORY_IDS.includes(value.accessoryId)||!digest(value.normalClipId)||!Number.isInteger(value.normalFrame)||value.normalFrame<0||value.normalFrame>=2048||!Number.isSafeInteger(value.normalRevision)||value.normalRevision<0||typeof value.playing!=='boolean')throw Error('Invalid inspection context');
 return Object.freeze({...value});
}
function discard(response){try{response.body?.cancel().catch(()=>{});}catch{}}
export function createAccessoryInspection({getContext,fetchImpl=globalThis.fetch,onFrame=()=>{},onStatus=()=>{},onOpenChange=()=>{},harness='apex-rust-preview-20261102-v71-import-ui-candidate',timeoutMs=15000}){
 if(typeof getContext!=='function'||!Number.isInteger(timeoutMs)||timeoutMs<1||timeoutMs>15000)throw Error('Invalid inspection configuration');
 let opened=false,disposed=false,generation=0,active=null,context=null,sample=62,framing=null;
 const notify=(message,state='stale')=>onStatus(message,state);
 function cancel(){generation++;active?.abort(Error('Inspection canceled'));active=null;}
 function close(reason='Inspection closed. Normal preview is unchanged.') {cancel();opened=false;context=null;framing=null;onOpenChange(false);notify(reason,'closed');}
 function current(){try{return checkedContext(getContext());}catch(error){close('Inspection unavailable: '+error.message);return null;}}
 function sync(){if(disposed)return false;const next=current();if(opened&&(!sameContext(context,next)||next.playing))close('Inspection canceled because the normal preview changed.');return Boolean(next&&!next.playing);}
 async function render(){
  cancel();const ticket=generation,expected=context,requested=sample;const controller=new AbortController();active=controller;
  const timer=setTimeout(()=>controller.abort(Error('Inspection deadline exceeded')),timeoutMs);
  notify(`Loading reference sample ${requested}; any retained inspection is stale. Normal preview is unchanged.`);
  const owns=()=>{if(disposed||!opened||ticket!==generation)return false;if(!sameContext(expected,current())||expected.playing){close('Inspection canceled because the normal preview changed.');return false;}return true;};
  try{
   const identityResponse=await abortable(fetchImpl('/identity',{signal:controller.signal,cache:'no-store',redirect:'error',credentials:'same-origin'}),controller.signal);
   if(identityResponse.status!==200||!/^application\/json(?:;\s*charset=utf-8)?$/i.test(identityResponse.headers.get('content-type')||'')){discard(identityResponse);throw Error('Invalid inspection identity response');}
   const identity=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(await readLimited(identityResponse,{maxBytes:4096,signal:controller.signal})));
   if(!identity||identity.harness!==harness||identity.scene_sha256!==expected.scene||!['serial-cc','pooled-cc-1','pooled-cc-2','pooled-cc-4'].includes(identity.renderer)||!Number.isInteger(identity.http_workers)||identity.http_workers<1||identity.http_workers>4||identity.pose_library_ready!==true)throw Error('Inspection scene identity changed');
   if(!owns())return;
   const path=`/accessory-inspection-frame?sample=${requested}&yaw=45&accessory=${expected.accessoryId}&accessory_catalog=${expected.catalog}&accessory_scene=${expected.scene}`;
   const response=await abortable(fetchImpl(path,{signal:controller.signal,cache:'no-store',redirect:'error',credentials:'same-origin'}),controller.signal);
   const header=name=>response.headers.get(name),frameHash=header('X-Inspection-Framing');
   if(response.status!==200||(header('content-type')||'').split(';')[0].trim()!=='application/octet-stream'||header('X-Harness')!==harness||header('X-Scene')!==expected.scene||header('X-Renderer')!==identity.renderer||header('X-HTTP-Workers')!==String(identity.http_workers)||header('X-Accessory-ID')!==expected.accessoryId||header('X-Accessory-Catalog')!==expected.catalog||header('X-Inspection-Sample')!==String(requested)||header('X-Inspection-Scope')!==INSPECTION_SCOPE||frameHash!==INSPECTION_FRAMING||(framing!==null&&framing!==frameHash)){discard(response);throw Error('Inspection frame identity or scope changed');}
   const rgb=await readLimited(response,{maxBytes:786432,exact:true,signal:controller.signal});
   if(!owns())return;
   const rgba=new Uint8ClampedArray(1048576);for(let i=0,j=0;i<rgb.length;i+=3,j+=4){rgba[j]=rgb[i];rgba[j+1]=rgb[i+1];rgba[j+2]=rgb[i+2];rgba[j+3]=255;}
   framing=frameHash;onFrame({rgba,sample:requested,framing:frameHash,scene:expected.scene,catalog:expected.catalog,accessoryId:expected.accessoryId,scope:INSPECTION_SCOPE});
   notify(`Reference sample ${requested} · fixed head framing at 45°. Hair, dress and shoe meshes hidden. This is not the current normal pose. External preview only; no game changes.`,'current');
  }catch(error){if(owns())notify('Inspection failed; any retained diagnostic is stale: '+error.message,'failed');}
  finally{clearTimeout(timer);controller.abort();if(active===controller)active=null;}
 }
 return {open(){if(disposed)return false;const next=current();if(!next||next.playing){notify('Inspection unavailable while normal preview is playing or prepared selections are disabled.','closed');return false;}cancel();context=next;sample=62;framing=null;opened=true;onOpenChange(true);void render();return true;},setSample(value){if(!opened||disposed)return false;if(!INSPECTION_SAMPLES.includes(value)){notify('Unsupported reference sample; choose 0, 62 or 361.','failed');return false;}if(!sync())return false;sample=value;void render();return true;},sync,close,dispose(){if(disposed)return;close('Inspection disposed. Normal preview is unchanged.');disposed=true;},get isOpen(){return opened},get sample(){return sample},get disposed(){return disposed}};
}
export function bindAccessoryInspection({button,dialog,canvas,sampleControl,closeButton,status,help,getContext,fetchImpl=globalThis.fetch,ImageDataImpl=globalThis.ImageData}){
 const ctx=canvas.getContext('2d');
 const inspector=createAccessoryInspection({getContext,fetchImpl,onOpenChange(open){if(open){sampleControl.value='62';ctx.clearRect(0,0,512,512);canvas.dataset.inspectionState='empty';canvas.setAttribute('aria-label','No reference inspection rendered yet');dialog.hidden=false;if(!dialog.open)dialog.showModal();}else{if(dialog.open)dialog.close();dialog.hidden=true;}},onFrame(frame){ctx.putImageData(new ImageDataImpl(frame.rgba,512,512),0,0);canvas.dataset.inspectionSample=String(frame.sample);canvas.dataset.inspectionFraming=frame.framing;canvas.dataset.inspectionAccessory=frame.accessoryId;canvas.setAttribute('aria-label',`Reference earring inspection, sample ${frame.sample}; not the current normal pose`);},onStatus(message,state){status.textContent=message;canvas.dataset.inspectionState=state;}});
 const listen=(node,type,handler)=>{node.addEventListener(type,handler);return ()=>node.removeEventListener(type,handler);};
 const removers=[listen(button,'click',()=>inspector.open()),listen(sampleControl,'change',()=>{if(!inspector.setSample(Number(sampleControl.value)))sampleControl.value=String(inspector.sample);}),listen(closeButton,'click',()=>inspector.close()),listen(dialog,'cancel',event=>{event.preventDefault();inspector.close();}),listen(dialog,'close',()=>{if(inspector.isOpen)inspector.close();})];
 function sync(){const value=getContext();button.hidden=value?.enabled!==true;help.hidden=button.hidden;help.textContent=value?.playing?'Pause normal playback to inspect earrings.':'Opens a separate reference pose inspection; your normal pose and history stay unchanged.';button.disabled=!inspector.sync()||button.hidden;if(button.hidden)dialog.hidden=true;}
 sync();
 return {sync,close:reason=>inspector.close(reason),dispose(){inspector.dispose();for(const remove of removers)remove();button.hidden=true;help.hidden=true;button.disabled=true;},get isOpen(){return inspector.isOpen}};
}
