# SPDX-License-Identifier: GPL-3.0-or-later
"""Prepare source-bound adult-rig pose previews in a fresh private directory.

Diagnostic only: does not establish native-game compatibility, apply to a game,
or authorize running an untrusted sampler. Use an independently reviewed and
pinned sampler built from the retained source. Caller owns trusted parent paths.
"""
import argparse,hashlib,io,json,math,os,pathlib,re,struct,subprocess,sys,time
import numpy as np
from PIL import Image
root=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'inert-status-fixture/modules'));sys.path.insert(0,str(root/'real-recovery-evidence/clip-gpl'))
from cas_resource_catalog import Package,tgi
from decode_clip import decode
from dst_adapter import to_dds
from intake_pose_package import estimated_keys
HEX=re.compile('[a-f0-9]{64}\\Z');TGI=re.compile('6B20C4F3:[0-9A-F]{8}:[0-9A-F]{16}\\Z')
def read_pinned(path,digest,limit):
 p=pathlib.Path(path)
 if not HEX.fullmatch(digest) or p.is_symlink() or not p.is_file():raise ValueError('Pinned regular file required')
 with p.open('rb') as f:data=f.read(limit+1)
 if len(data)>limit or hashlib.sha256(data).hexdigest()!=digest:raise ValueError('File extent or identity mismatch')
 return data
def child_name(value):
 if not value or value in ('.','..') or pathlib.Path(value).name!=value:raise ValueError('Single directory name required')
 return value
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--package',required=True);ap.add_argument('--package-sha',required=True);ap.add_argument('--case',required=True);ap.add_argument('--catalog',required=True);ap.add_argument('--catalog-sha',required=True);ap.add_argument('--rig',required=True);ap.add_argument('--rig-sha',required=True);ap.add_argument('--sampler',required=True);ap.add_argument('--sampler-sha',required=True);ap.add_argument('--mesh',nargs=2,action='append',required=True,metavar=('PATH','SHA256'));ap.add_argument('--output',required=True);a=ap.parse_args()
 for x in (a.case,a.catalog,a.output):child_name(x)
 if len(a.mesh)!=4:raise ValueError('Exactly four ordered meshes required')
 source=pathlib.Path(a.package)
 if source.is_symlink() or not source.is_file() or source.stat().st_size>8*1024*1024:raise ValueError('Bounded package required')
 package=Package(source,'mod')
 if package.source_sha256!=a.package_sha or len(package.entries)>1024 or sum(max(v[1:3]) for v in package.entries.values())>64*1024*1024:raise ValueError('Package identity or budget mismatch')
 items={tgi(k):v for k,v in package.read_many(list(package.entries)).items()}
 case=root/'private-input-recovery'/a.case;catalog_dir=case/a.catalog
 if case.is_symlink() or catalog_dir.is_symlink() or not catalog_dir.is_dir():raise ValueError('Private catalog unavailable')
 catalog=json.loads(read_pinned(catalog_dir/'catalog.json',a.catalog_sha,1024*1024))
 if catalog.get('schema')!=1 or catalog.get('source_package_sha256')!=a.package_sha or catalog.get('autoplay') is not False or not isinstance(catalog.get('poses'),list) or len(catalog['poses'])>1024:raise ValueError('Catalog identity or shape mismatch')
 rig=read_pinned(a.rig,a.rig_sha,1024*1024).decode('ascii').splitlines()
 if not rig or rig[0]!='165' or len(rig)!=166:raise ValueError('Adult rig bounds')
 hashes=set()
 for i,line in enumerate(rig[1:]):
  f=line.split()
  if len(f)!=12:raise ValueError('Rig field count')
  h,parent=int(f[0]),int(f[1]);values=[float(v) for v in f[2:]]
  if h in hashes or not 0<=h<=0xffffffff or not -1<=parent<i or not all(math.isfinite(v) for v in values) or any(abs(v-1)>1e-6 for v in values[-3:]):raise ValueError('Rig structure')
  hashes.add(h)
 read_pinned(a.sampler,a.sampler_sha,64*1024*1024)
 dtype=np.dtype(dict(names=['p','n','uv','j','w'],formats=[('<f4',3),('<f4',3),('<f4',2),('<u2',4),('<f4',4)],offsets=[0,12,24,32,40],itemsize=56));vertices=[];mesh_hash=hashlib.sha256();total_vertices=0
 for path,digest in a.mesh:
  raw=read_pinned(path,digest,64*1024*1024)
  if len(raw)<16 or raw[:8]!=b'APXMESH1':raise ValueError('Mesh header')
  count,indices=struct.unpack_from('<II',raw,8);total_vertices+=count
  if not 0<count<=500000 or total_vertices>1000000 or indices>3000000 or len(raw)!=16+count*56+indices*4:raise ValueError('Mesh extent')
  mesh_hash.update(struct.pack('<Q',len(raw)));mesh_hash.update(raw);v=np.frombuffer(raw,dtype,count=count,offset=16)
  if not np.isfinite(v['p']).all() or not np.isfinite(v['w']).all() or np.any(v['w']<0) or np.any(v['w'].sum(axis=1)<=0) or np.any(v['j']>=165):raise ValueError('Mesh vertex bounds')
  vertices.append((np.c_[v['p'].astype(float),np.ones(count)],v['j'].copy(),v['w'].astype(float)))
 output=case/a.output;output.mkdir(mode=0o700,exist_ok=False);start=time.monotonic();total_frames=0;claimed=0;prepared=0;pose_rows=[]
 for pose in catalog['poses']:
  if not isinstance(pose,dict) or not HEX.fullmatch(pose.get('id','')):raise ValueError('Invalid pose identity')
  row=dict(pose);row['playing']=False;row['playback_ready']=False
  icon=row.get('icon')
  if isinstance(icon,dict) and icon.get('state')=='decoded-source-image':
   name=icon.get('file','');pngsha=icon.get('png_sha256','')
   if not re.fullmatch('[a-f0-9]{64}\\.png',name) or not HEX.fullmatch(pngsha):raise ValueError('Icon identity')
   png=read_pinned(catalog_dir/name,pngsha,512*1024);source_sha=name[:-4]
   matches=[v for k,v in items.items() if k.startswith('00B2D882:') and hashlib.sha256(v).hexdigest()==source_sha]
   if len(matches)!=1:raise ValueError('Icon source ambiguous')
   im=Image.open(io.BytesIO(to_dds(matches[0])))
   if im.format!='DDS' or not 0<im.width<=512 or not 0<im.height<=512:raise ValueError('Icon dimensions')
   im.load();buffer=io.BytesIO();im.convert('RGBA').save(buffer,format='PNG')
   if buffer.getvalue()!=png:raise ValueError('Icon not derived from source')
   dest=output/name
   if not dest.exists():
    with dest.open('xb') as f:f.write(png)
  clip=row.get('clip_resource');clip_sha=row.get('clip_sha256');decoded_sha=row.get('decoded_sha256')
  if row.get('state')!='decoded-not-prepared' or not isinstance(clip,str) or not TGI.fullmatch(clip) or clip not in items:
   pose_rows.append(row);continue
  raw=items[clip]
  if not isinstance(clip_sha,str) or not HEX.fullmatch(clip_sha) or hashlib.sha256(raw).hexdigest()!=clip_sha or not isinstance(decoded_sha,str) or not HEX.fullmatch(decoded_sha):raise ValueError('Clip source identity')
  claimed+=estimated_keys(raw)
  if claimed>250000:raise ValueError('Clip expansion budget')
  x=decode(raw);canonical=json.dumps(x,separators=(',',':'),allow_nan=False).encode()
  if len(canonical)>16*1024*1024 or hashlib.sha256(canonical).hexdigest()!=decoded_sha or x['name']!=row.get('clip_name'):raise ValueError('Decoded clip identity')
  if x['unsupported_channels'] or any(t['key'] not in hashes for t in x['tracks']):row['state']='unsupported-or-incompatible';pose_rows.append(row);continue
  changing=sum(len({tuple(k['values']) for k in t['frames']})>1 for t in x['tracks']);duration=x['duration'];step=x['frame_duration'];frames=1 if changing==0 else math.ceil(duration/step)+1
  if not 1<=frames<=2048 or total_frames+frames>4096:row['state']='frame-budget-exceeded';pose_rows.append(row);continue
  lines=[f"{duration!r} {step!r} {len(x['tracks'])}"]
  for track in x['tracks']:
   lines.append(f"{track['key']} {track['kind']} {len(track['frames'])}")
   for k in track['frames']:
    at=struct.unpack('<f',struct.pack('<f',k['frame']*step))[0];v=k['values'] if track['kind']==2 else k['values']+[0.];lines.append(' '.join(map(repr,[at,*v])))
  scratch=output/'current.clip';scratch.write_text('\n'.join(lines)+'\n');matrixfile=output/'current.f32';payload=bytearray();lo=np.array([np.inf]*3);hi=-lo
  for i in range(frames):
   if time.monotonic()-start>120:raise ValueError('Preparation deadline')
   read_pinned(a.sampler,a.sampler_sha,64*1024*1024);read_pinned(a.rig,a.rig_sha,1024*1024)
   cmd=[a.sampler,a.rig,str(scratch),str(min(i*step,duration)),str(matrixfile),'normalize']
   proc=subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=10,env={'PATH':'/usr/bin:/bin'},check=True)
   if len(proc.stdout)>65536:raise ValueError('Sampler output budget')
   info=json.loads(proc.stdout);matrix=matrixfile.read_bytes()
   if info.get('bones')!=165 or info.get('max_matrix_orthogonality_error',1)>=1e-4 or len(matrix)!=165*48:raise ValueError('Sampler verification')
   payload.extend(matrix);mat=np.frombuffer(matrix,dtype='<f4').reshape(165,3,4).astype(float)
   if not np.isfinite(mat).all():raise ValueError('Nonfinite sampler matrix')
   for pos,j,w in vertices:
    transformed=(np.einsum('nikl,nl->nik',mat[j],pos)*w[:,:,None]).sum(axis=1)/w.sum(axis=1)[:,None];lo=np.minimum(lo,transformed.min(axis=0));hi=np.maximum(hi,transformed.max(axis=0))
  lo-=0.0001;hi+=0.0001
  if not np.isfinite(lo).all() or not np.isfinite(hi).all() or not (hi>lo).all():raise ValueError('Pose framing bounds')
  blob=b'APXPOSE1'+mesh_hash.digest()+struct.pack('<IIff6f',165,frames,step,duration,*lo,*hi)+payload
  with (output/(row['id']+'.posebin')).open('xb') as f:f.write(blob)
  scratch.unlink();matrixfile.unlink();total_frames+=frames;prepared+=1
  row.update(duration=duration,frame_duration=step,changing_curves=changing,prepared_frames=frames,playback_ready=True,state='prepared-not-playing')
  pose_rows.append(row)
 if hashlib.sha256(read_pinned(source,a.package_sha,8*1024*1024)).hexdigest()!=a.package_sha:raise ValueError('Package changed')
 result={**catalog,'poses':pose_rows,'autoplay':False,'game_connected':False,'shared_favorites_connected':False};encoded=json.dumps(result,ensure_ascii=False,indent=2).encode()
 if len(encoded)>1024*1024:raise ValueError('Catalog output budget')
 with (output/'catalog.json').open('xb') as f:f.write(encoded)
 print(json.dumps({'poses':len(pose_rows),'prepared':prepared,'frames':total_frames,'autoplay':False,'game_modified':False}))
if __name__=='__main__':main()
