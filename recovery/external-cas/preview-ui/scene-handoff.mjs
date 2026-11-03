import assert from 'node:assert/strict';import {createFrameClient} from './frame-client.mjs';import {createHash} from 'node:crypto';
let base=process.argv[2];const client=createFrameClient({fetchImpl:(path,options)=>fetch(base+path,options)});
const request={yaw:0,pose:0,morph:50,format:'rgb',header:'split'};
const first=await client.read(request);const hash=createHash('sha256').update(first.rgba).digest('hex');
base=process.argv[3];await assert.rejects(client.read(request),/Scene identity changed/);
assert.equal(createHash('sha256').update(first.rgba).digest('hex'),hash);
console.log(JSON.stringify({first_scene:first.scene,first_frame_sha256:hash,changed_scene_refused:true,last_good_bytes_unchanged:true,scope:'Actual HTTP through a simulated backend-route switch; not a native game session'}));
