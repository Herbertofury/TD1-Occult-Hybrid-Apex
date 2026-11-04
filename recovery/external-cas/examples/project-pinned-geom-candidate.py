# SPDX-License-Identifier: GPL-3.0-or-later
"""Offline diagnostic projection of one pinned GEOM; not a general CC renderer.

Use trusted local files and trusted output parent. No game writes. This research
adapter is not an OS sandbox and may allocate substantially while inspecting a
bounded package. Unknown layouts or unresolved weighted bones are refused.
"""
import argparse,hashlib,json,math,pathlib,re,struct,sys
root=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'inert-status-fixture/modules'))
from cas_resource_catalog import Package
from inspect_geom_v15 import inspect
from inspect_rig import inspect_rig,map_joints
HEX=re.compile(r'[a-f0-9]{64}\Z');TGI=re.compile(r'015A1849:[0-9A-F]{8}:[0-9A-F]{16}\Z')
def pinned(path,digest,limit):
 p=pathlib.Path(path)
 if not HEX.fullmatch(digest) or p.is_symlink() or not p.is_file():raise ValueError('pinned regular file required')
 with p.open('rb') as f:b=f.read(limit+1)
 if len(b)>limit or hashlib.sha256(b).hexdigest()!=digest:raise ValueError('file identity or size mismatch')
 return b
def main():
 p=argparse.ArgumentParser();p.add_argument('--package',required=True);p.add_argument('--package-sha',required=True);p.add_argument('--geom',required=True);p.add_argument('--geom-sha',required=True);p.add_argument('--rig',required=True);p.add_argument('--rig-sha',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 if not HEX.fullmatch(a.package_sha) or not HEX.fullmatch(a.geom_sha) or not TGI.fullmatch(a.geom):raise ValueError('invalid resource identity')
 out=a.output
 if not out or out in ('.','..') or pathlib.Path(out).name!=out:raise ValueError('single fresh directory name required')
 source=pathlib.Path(a.package)
 if source.is_symlink() or not source.is_file() or source.stat().st_size>64*1024*1024:raise ValueError('bounded package required')
 rig=inspect_rig(pinned(a.rig,a.rig_sha,4*1024*1024));bones=rig['bones']
 if len(bones)!=165:raise ValueError('expected adult rig')
 pkg=Package(source,'mod')
 if pkg.source_sha256!=a.package_sha or len(pkg.entries)>1024:raise ValueError('package identity or resource count')
 key=tuple(int(x,16) for x in a.geom.split(':'))
 if key not in pkg.entries:raise ValueError('selected GEOM missing')
 raw=pkg.read_many([key],max_total=32*1024*1024)[key]
 if hashlib.sha256(raw).hexdigest()!=a.geom_sha:raise ValueError('GEOM identity mismatch')
 data={};metadata=inspect(raw,data);vertices=data['vertices'];indices=data['indices'];palette=data['palette'];by={b['hash']:i for i,b in enumerate(bones)}
 if not 0<len(vertices)<=500000 or len(indices)>3000000:raise ValueError('geometry output budget')
 projected=bytearray(b'APXMESH1'+struct.pack('<II',len(vertices),len(indices)))
 for pos,norm,uv,joints,weights in vertices:
  if any(v is None for v in (pos,norm,uv,joints,weights)) or not all(math.isfinite(w) and 0<=w<=1 for w in weights) or not sum(weights)>0:raise ValueError('incomplete vertex or invalid weights')
  mapped=map_joints(joints,weights,palette,by);projected+=struct.pack('<8f4H4f',*pos,*norm,*uv,*mapped,*[w/sum(weights) for w in weights])
 projected+=struct.pack('<'+'I'*len(indices),*indices)
 if hashlib.sha256(pinned(source,a.package_sha,64*1024*1024)).hexdigest()!=a.package_sha:raise ValueError('package changed')
 parent=root/'private-input-recovery'
 if parent.is_symlink() or not parent.is_dir():raise ValueError('private parent unavailable')
 target=parent/out;target.mkdir(mode=0o700,exist_ok=False)
 with (target/'mesh.apxmesh').open('xb') as f:f.write(projected)
 report={'source_sha256':a.package_sha,'resource':a.geom,'geom_sha256':a.geom_sha,'rig_sha256':a.rig_sha,'mesh_sha256':hashlib.sha256(projected).hexdigest(),'vertices':len(vertices),'triangles':len(indices)//3,'geom_version':metadata['version'],'game_modified':False,'compatibility':'unverified'}
 with (target/'report.json').open('x') as f:json.dump(report,f,indent=2)
 print(json.dumps({'vertices':len(vertices),'triangles':len(indices)//3,'geom_version':metadata['version'],'game_modified':False,'compatibility':'unverified'}))
if __name__=='__main__':main()
