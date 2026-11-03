// Closed prepared-fixture catalog. Names and thumbnails never grant compatibility.
import {SWATCH_ID} from './swatch-model.mjs';
export const ACCESSORY_IDS=Object.freeze(['034AEECB:80000000:8CD98CB25CD1698D','034AEECB:80000000:8CD608B25CCE53AB','034AEECB:80000000:C8B807499B50E181','034AEECB:80000000:C8AD87499B47B38A']);
export const ACCESSORY_UNSUPPORTED='Only four prepared Caluxa selections; arbitrary CC and other swatches are unsupported.';
const digest=x=>typeof x==='string'&&/^[a-f0-9]{64}$/.test(x);
const exact=(v,keys)=>v&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).length===keys.length&&keys.every(k=>Object.hasOwn(v,k));
export function validateAccessoryCatalog(value){
 if(!exact(value,['schema','scene_sha256','catalog_sha256','default_id','enabled','selections','unsupported'])||value.schema!==1||!digest(value.scene_sha256)||value.default_id!==ACCESSORY_IDS[0]||typeof value.enabled!=='boolean'||!Array.isArray(value.selections)||value.unsupported!==ACCESSORY_UNSUPPORTED||(value.enabled?(!digest(value.catalog_sha256)||value.selections.length!==4):(value.catalog_sha256!==null||value.selections.length!==0)))throw Error('Invalid bounded accessory catalog');
 const ids=new Set();
 const selections=value.selections.map(row=>{
  if(!exact(row,['id','label','package_sha256','casp_sha256','geom_tgi','diffuse_tgi'])||typeof row.id!=='string'||!SWATCH_ID.test(row.id)||!ACCESSORY_IDS.includes(row.id)||ids.has(row.id)||typeof row.label!=='string'||row.label.length<1||row.label.length>96||/[\u0000-\u001f\u007f]/.test(row.label)||!digest(row.package_sha256)||!digest(row.casp_sha256)||typeof row.geom_tgi!=='string'||!/^015A1849:[A-F0-9]{8}:[A-F0-9]{16}$/.test(row.geom_tgi)||typeof row.diffuse_tgi!=='string'||!/^3453CF95:[A-F0-9]{8}:[A-F0-9]{16}$/.test(row.diffuse_tgi))throw Error('Invalid prepared accessory selection');
  ids.add(row.id);return Object.freeze({...row});
 });
 if(value.enabled&&!ACCESSORY_IDS.every(id=>ids.has(id)))throw Error('Incomplete prepared accessory catalog');
 return Object.freeze({...value,selections:Object.freeze(selections)});
}
export function accessoryLabel(catalog,id){const row=catalog.selections.find(row=>row.id===id);if(!row)throw Error('Unknown prepared accessory');return row.label;}
