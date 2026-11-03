import {validateAccessoryCatalog} from './accessory-model.mjs';
import {validateSwatchCatalog} from './swatch-model.mjs';
// Reuses the existing session history owner. No favorites, game or disk writes.
import {PreviewHistory} from './cc-history.mjs';
import {validateCatalog} from './pose-model.mjs';
const legacyKeys=['scene','clipId','frame','yaw','hue'];
const materialKeys=[...legacyKeys,'brightness','saturation','opacity'];
export class PoseHistory extends PreviewHistory {
 constructor({scene,catalog,swatches=null,accessories=null},initial,capacity=128){
  if(typeof scene!=='string'||!/^[a-f0-9]{64}$/.test(scene))throw Error('Verified scene identity required');
  validateCatalog(catalog);
  const verifiedSwatches=swatches===null?null:validateSwatchCatalog(swatches);
  if(verifiedSwatches&&verifiedSwatches.scene_sha256!==scene)throw Error('Swatch history scene differs');
  const swatchIds=verifiedSwatches?new Set(verifiedSwatches.swatches.map(s=>s.id)):null;
  const verifiedAccessories=accessories===null?null:validateAccessoryCatalog(accessories);
  if(verifiedAccessories&&verifiedAccessories.scene_sha256!==scene)throw Error('Accessory history scene differs');
  const accessoryIds=verifiedAccessories?.enabled?new Set(verifiedAccessories.selections.map(s=>s.id)):null;
  const priorKeys=verifiedSwatches?[...materialKeys,'swatchId']:materialKeys;
  const keys=accessoryIds?[...priorKeys,'accessoryId']:priorKeys;
  const frames=new Map(catalog.poses.filter(p=>p.playback_ready===true).map(p=>[p.id,p.prepared_frames]));
  const checked=input=>{
   // Exact old checkpoints gain the same neutral values the old UI sent.
   let value=input&&Object.keys(input).length===legacyKeys.length&&legacyKeys.every(k=>Object.hasOwn(input,k))?{...input,brightness:0,saturation:0,opacity:16384}:input;
   if(verifiedSwatches&&value&&Object.keys(value).length===materialKeys.length&&materialKeys.every(k=>Object.hasOwn(value,k)))value={...value,swatchId:verifiedSwatches.default_id};
   if(accessoryIds&&value&&Object.keys(value).length===priorKeys.length&&priorKeys.every(k=>Object.hasOwn(value,k)))value={...value,accessoryId:verifiedAccessories.default_id};
   if(accessoryIds&&!accessoryIds.has(value?.accessoryId))throw Error('Unknown history accessory');
   if(verifiedSwatches&&!swatchIds.has(value?.swatchId))throw Error('Unknown history swatch');
   if(!value||Object.keys(value).length!==keys.length||!keys.every(k=>Object.hasOwn(value,k))||value.scene!==scene||!frames.has(value.clipId)||!Number.isInteger(value.frame)||value.frame<0||value.frame>=frames.get(value.clipId)||!Number.isInteger(value.yaw)||Math.abs(value.yaw)>180||!Number.isInteger(value.hue)||Math.abs(value.hue)>8192)throw Error('Pose history requires complete parameters bound to this scene and prepared clip');
   for(const [k,min,max] of [['brightness',-8192,8192],['saturation',-8192,8192],['opacity',3277,16384]])if(!Number.isInteger(value[k])||value[k]<min||value[k]>max)throw Error('Invalid pose material '+k);
   return Object.freeze({...value});
  };
  super(initial,capacity,{checked,same:(a,b)=>keys.every(k=>a[k]===b[k])});
 }
}
