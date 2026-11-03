// Restricted real-dress catalog. No file paths or native-game authority.
const digest = /^[a-f0-9]{64}$/;
export const SWATCH_ID = /^034AEECB:[A-F0-9]{8}:[A-F0-9]{16}$/;
const isDigest = x => typeof x==='string' && digest.test(x);
const isId = x => typeof x==='string' && SWATCH_ID.test(x);
const exact = (value, keys) => value && typeof value === 'object' && !Array.isArray(value) && Object.keys(value).length === keys.length && keys.every(k => Object.hasOwn(value,k));
export function validateSwatchCatalog(value) {
 if (!exact(value,['schema','scene_sha256','catalog_sha256','default_id','enabled','swatches']) || value.schema!==1 || !isDigest(value.scene_sha256) || typeof value.enabled!=='boolean' || !isId(value.default_id) || !Array.isArray(value.swatches) || value.swatches.length<1 || value.swatches.length>30 || (value.enabled ? !isDigest(value.catalog_sha256) : value.catalog_sha256!==null || value.swatches.length!==1)) throw Error('Invalid bounded swatch catalog');
 const ids=new Set();
 const swatches=value.swatches.map(row=>{
  if(!exact(row,['id','order','colors_argb','width','height']) || !isId(row.id) || ids.has(row.id) || !Number.isInteger(row.order) || row.order<0 || row.order>65535 || row.width!==2048 || row.height!==4096 || !Array.isArray(row.colors_argb) || row.colors_argb.length<1 || row.colors_argb.length>8 || row.colors_argb.some(c=>!Number.isInteger(c)||c<0||c>0xffffffff))throw Error('Invalid swatch entry');
  ids.add(row.id);return Object.freeze({...row,colors_argb:Object.freeze([...row.colors_argb])});
 });
 if(!ids.has(value.default_id))throw Error('Default swatch is missing');
 return Object.freeze({...value,swatches:Object.freeze(swatches)});
}
export function swatchLabel(catalog,id) {
 const index=catalog.swatches.findIndex(s=>s.id===id);
 if(index<0)throw Error('Unknown swatch');
 return `Swatch ${index+1} · authored order ${catalog.swatches[index].order}`;
}
export function authoredColorCss(argb) {
 if(!Number.isInteger(argb)||argb<0||argb>0xffffffff)throw Error('Invalid authored color');
 const hex=argb.toString(16).padStart(8,'0');return '#'+hex.slice(2)+hex.slice(0,2);
}
