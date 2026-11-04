# SPDX-License-Identifier: GPL-3.0-or-later
"""Merge independently projected LOD-0 meshes declared by one pinned CASP.

Private diagnostic only: geometry states, UV layout, native rendering and game
compatibility are not established. Inputs and parent directories are trusted;
this script is not a hostile-filesystem sandbox and makes no game writes.
"""
import argparse,hashlib,json,math,pathlib,re,struct
root=pathlib.Path(__file__).resolve().parents[1];DIGEST=re.compile(r'[a-f0-9]{64}\Z')
def read_pin(path,digest,limit):
 p=pathlib.Path(path)
 if not DIGEST.fullmatch(digest) or p.is_symlink() or not p.is_file():raise ValueError('pinned file required')
 with p.open('rb') as f:b=f.read(limit+1)
 if len(b)>limit or hashlib.sha256(b).hexdigest()!=digest:raise ValueError('identity or size mismatch')
 return b
def main():
 p=argparse.ArgumentParser();p.add_argument('--resolution',nargs=2,required=True,metavar=('PATH','SHA256'));p.add_argument('--projection',nargs=2,action='append',required=True,metavar=('REPORT','SHA256'));p.add_argument('--output',required=True);a=p.parse_args()
 if not a.output or a.output in ('.','..') or pathlib.Path(a.output).name!=a.output:raise ValueError('fresh single directory required')
 manifest=json.loads(read_pin(*a.resolution,1024*1024));rows=[x for x in manifest['references'] if x['role']=='lod-0']
 if not 1<=len(rows)<=8 or len(rows)!=len(a.projection) or len({x['resolved'] for x in rows if x['state']=='source-present-not-rendered'})!=len(rows):raise ValueError('incomplete or ambiguous LOD')
 verts=[];indices=[];vertex_total=0;rig=None
 for row,(rp,rhash) in zip(rows,a.projection):
  report=json.loads(read_pin(rp,rhash,1024*1024));p=pathlib.Path(rp)
  if p.parent.is_symlink() or report['resource']!=row['resolved'] or report['source_sha256']!=manifest['package_sha256'] or report['geom_sha256']!=row['sha256'] or report['game_modified'] is not False:raise ValueError('projection does not match selected CASP')
  if not DIGEST.fullmatch(report['rig_sha256']):raise ValueError('rig identity')
  if rig is None:rig=report['rig_sha256']
  elif rig!=report['rig_sha256']:raise ValueError('different rigs')
  blob=read_pin(p.parent/'mesh.apxmesh',report['mesh_sha256'],64*1024*1024)
  if len(blob)<16 or blob[:8]!=b'APXMESH1':raise ValueError('mesh header')
  n,k=struct.unpack_from('<II',blob,8)
  if not 0<n<=500000 or vertex_total+n>500000 or k>3000000 or k%3 or len(blob)!=16+n*56+k*4:raise ValueError('mesh extent')
  vertex=blob[16:16+n*56]; ids=struct.unpack_from('<'+str(k)+'I',blob,16+n*56)
  if any(i>=n for i in ids) or len(indices)+k>3000000:raise ValueError('index extent')
  for j in range(n):
   values=struct.unpack_from('<8f4H4f',vertex,j*56); weights=values[-4:]
   if not all(math.isfinite(x) for x in values[:8]+weights) or any(x>=165 for x in values[8:12]) or any(x<0 for x in weights) or sum(weights)<=0:raise ValueError('vertex invalid')
  verts.append(vertex);indices.extend(i+vertex_total for i in ids);vertex_total+=n
 data=b'APXMESH1'+struct.pack('<II',vertex_total,len(indices))+b''.join(verts)+struct.pack('<'+str(len(indices))+'I',*indices)
 parent=root/'private-input-recovery'
 if parent.is_symlink() or not parent.is_dir():raise ValueError('private parent unavailable')
 output=parent/a.output;output.mkdir(mode=0o700,exist_ok=False)
 with (output/'mesh.apxmesh').open('xb') as f:f.write(data)
 result={'resolution_sha256':a.resolution[1],'rig_sha256':rig,'mesh_sha256':hashlib.sha256(data).hexdigest(),'source_meshes':len(rows),'vertices':vertex_total,'triangles':len(indices)//3,'rendered':False,'game_modified':False,'compatibility':'unverified'}
 with (output/'report.json').open('x') as f:json.dump(result,f,indent=2)
 print(json.dumps({k:result[k] for k in ('source_meshes','vertices','triangles','rendered','game_modified','compatibility')}))
if __name__=='__main__':main()
