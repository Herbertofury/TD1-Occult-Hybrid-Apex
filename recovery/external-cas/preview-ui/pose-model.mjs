const idPattern=/^[a-f0-9]{64}$/;
const text=v=>typeof v==='string'&&v.length<=2048;
export function validateCatalog(value){
 if(!value||value.schema!==1||value.autoplay!==false||!Array.isArray(value.poses)||value.poses.length>1024||!Array.isArray(value.packs)||value.packs.length>128)throw Error('Invalid pose catalog');
 const packIds=new Set();for(const p of value.packs){if(!p||!idPattern.test(p.id)||packIds.has(p.id)||!text(p.name))throw Error('Invalid pack identity');packIds.add(p.id);}
 const ids=new Set();
 for(const p of value.poses){
  if(!p||!idPattern.test(p.id)||ids.has(p.id)||!idPattern.test(p.pack_id)||!packIds.has(p.pack_id)||!['name','pack','creator','package','clip_name','state'].every(k=>text(p[k])))throw Error('Invalid or duplicate pose identity');ids.add(p.id);
  if(p.playback_ready!==undefined&&typeof p.playback_ready!=='boolean')throw Error('Invalid playback readiness');
  if(p.changing_curves!=null&&(!Number.isSafeInteger(p.changing_curves)||p.changing_curves<0))throw Error('Invalid changing-curve count');
  if(p.playback_ready===true&&(!Number.isInteger(p.prepared_frames)||p.prepared_frames<1||p.prepared_frames>2048||!Number.isFinite(p.duration)||p.duration<0||p.duration>3600||!Number.isFinite(p.frame_duration)||p.frame_duration<=0||p.frame_duration>1))throw Error('Invalid playback timing');
  if(p.playback_ready===true){if(!Number.isSafeInteger(p.changing_curves)||p.changing_curves<0)throw Error('Missing changing-curve count');const expected=p.changing_curves===0?1:Math.ceil(p.duration/p.frame_duration)+1;if((p.changing_curves>0&&p.duration<=0)||p.prepared_frames!==expected)throw Error('Prepared timeline does not cover declared duration');}
  if(p.icon?.state==='decoded-source-image'&&(!/^[a-f0-9]{64}\.png$/.test(p.icon.file)||![p.icon.width,p.icon.height].every(n=>Number.isInteger(n)&&n>0&&n<=512)))throw Error('Invalid pose thumbnail');
 }
 return value;
}
export function searchPoses(poses,{query='',pack='',creator='',kind='',availability='',pinnedOnly=false,pins=new Set()}={}){
 if(!['','ready','unavailable'].includes(availability))throw Error('Invalid playback availability filter');
 const words=String(query).slice(0,256).normalize('NFKC').toLocaleLowerCase('en').split(/\s+/).filter(Boolean);
 return poses.filter(p=>{const hay=[p.name,p.pack,p.creator,p.package,p.clip_name,p.description??''].join(' ').normalize('NFKC').toLocaleLowerCase('en');return words.every(w=>/^\d+$/.test(w)?hay.split(/[^a-z0-9]+/).includes(w):hay.includes(w))&&(!pack||p.pack_id===pack)&&(!creator||p.creator===creator)&&(!kind||(kind==='motion'?p.changing_curves>0:p.changing_curves===0))&&(!availability||(availability==='ready'?p.playback_ready===true:p.playback_ready!==true))&&(!pinnedOnly||pins.has(p.id));}).sort((a,b)=>a.pack.localeCompare(b.pack,'en',{numeric:true})||a.order-b.order||a.id.localeCompare(b.id));
}
export function frameAt(pose,time){
 if(pose.playback_ready!==true||!Number.isFinite(time))throw Error('Pose is not playback ready');
 if(pose.prepared_frames===1)return 0;
 if(time>=pose.duration)return pose.prepared_frames-1;
 return Math.max(0,Math.min(pose.prepared_frames-1,Math.floor(Math.max(0,time)/pose.frame_duration)));
}
export function remember(recent,id,limit=10){if(!idPattern.test(id))throw Error('Invalid recent pose');return [id,...recent.filter(v=>v!==id)].slice(0,limit);}
// A restored browser page must reacquire revoked thumbnail resources and reopen
// its preview epoch, but never resume motion without another explicit Play.
export function restoreViewer({controller,pool,makePool,pause,repaint}){
 pause();const current=pool.closed?makePool():pool;controller.open();repaint(current);return current;
}

// rates never alter saved pose samples or game state.
export function checkedPlaybackRate(rate){if(!Number.isFinite(rate)||rate<.25||rate>2)throw Error('Playback rate must be between 0.25 and 2');return rate;}
export function playbackTime(start,elapsedMs,rate){checkedPlaybackRate(rate);if(!Number.isFinite(start)||start<0||!Number.isFinite(elapsedMs)||elapsedMs<0)throw Error('Invalid playback clock');const time=start+elapsedMs*rate/1000;if(!Number.isFinite(time))throw Error('Playback clock overflow');return time;}
export function playbackDelay(due,now,rate){checkedPlaybackRate(rate);if(!Number.isFinite(due)||due<0||!Number.isFinite(now)||now<0)throw Error('Invalid playback deadline');const delay=Math.max(1,Math.ceil((due-now)*1000/rate));if(!Number.isFinite(delay)||delay>30000)throw Error('Playback delay exceeds bounded sample interval');return delay;}

export function poseReadiness(pose){return pose.playback_ready===true?(pose.changing_curves>0?'Ready · sequence':'Ready · static pose'):'Not playable · '+pose.state;}
