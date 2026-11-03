// Per-tab preview recovery only. Not native favorites or durable game storage.
const limit=65536;
function key(scene){if(typeof scene!=='string'||!/^[a-f0-9]{64}$/.test(scene))throw Error('Scene-bound tab history required');return 'apex.pose-preview.v1.'+scene;}
// Only overwrite bytes that this exact history owner has successfully loaded or saved.
// SessionStorage is synchronous within this page; this is not a cross-process disk CAS.
const accepted=new WeakMap();
export function loadPoseHistory(history,storage,scene){const name=key(scene),raw=storage.getItem(name);if(raw===null){accepted.set(history,{storage,name,raw});return false;}if(typeof raw!=='string'||raw.length>limit)throw Error('Tab history exceeds bounded checkpoint size');history.restoreState(JSON.parse(raw));accepted.set(history,{storage,name,raw});return true;}
export function savePoseHistory(history,storage,scene){const name=key(scene);if(history.value.scene!==scene)throw Error('Tab history scene mismatch');const raw=JSON.stringify(history.exportState());if(raw.length>limit)throw Error('Tab history exceeds bounded checkpoint size');const current=storage.getItem(name),prior=accepted.get(history);if(current!==null&&(!prior||prior.storage!==storage||prior.name!==name||prior.raw!==current))throw Error('Retained tab history changed or was not recovered; refusing overwrite');if(prior&&prior.storage===storage&&prior.name===name&&prior.raw!==current)throw Error('Retained tab history changed; refusing overwrite');storage.setItem(name,raw);if(storage.getItem(name)!==raw)throw Error('Tab history readback changed');accepted.set(history,{storage,name,raw});}


// Tab-local pose library choices, separate from native/shared favorites.
const libraryLimit=131072;
function libraryKey(scene){return key(scene).replace('pose-preview','pose-library');}
function checkedLibrary(value,ids){
 const known=new Set(ids);if(known.size!==ids.length||ids.length>1024||ids.some(id=>typeof id!=='string'||!/^[a-f0-9]{64}$/.test(id)))throw Error('Verified pose catalog required');
 if(!value||Object.keys(value).length!==2||!Array.isArray(value.pins)||!Array.isArray(value.recent)||value.pins.length>1024||value.recent.length>10)throw Error('Invalid tab pose library');
 for(const items of [value.pins,value.recent])if(new Set(items).size!==items.length||items.some(id=>!known.has(id)))throw Error('Unknown or duplicate tab pose identity');
 return {pins:[...value.pins],recent:[...value.recent]};
}
export function loadPoseLibrary(storage,scene,ids){
 const raw=storage.getItem(libraryKey(scene));if(raw===null)return null;
 if(typeof raw!=='string'||raw.length>libraryLimit)throw Error('Tab pose library exceeds budget');
 const state=JSON.parse(raw);if(!state||Object.keys(state).length!==3||state.schema!==1||state.scene!==scene)throw Error('Invalid tab pose library owner');
 return checkedLibrary(state.value,ids);
}
export function savePoseLibrary(storage,scene,ids,value){
 const checked=checkedLibrary(value,ids);loadPoseLibrary(storage,scene,ids); // Refuse to erase corrupt or stale last-good bytes.
 const raw=JSON.stringify({schema:1,scene,value:checked});if(raw.length>libraryLimit)throw Error('Tab pose library exceeds budget');
 const name=libraryKey(scene);storage.setItem(name,raw);if(storage.getItem(name)!==raw)throw Error('Tab pose library readback changed');
}
