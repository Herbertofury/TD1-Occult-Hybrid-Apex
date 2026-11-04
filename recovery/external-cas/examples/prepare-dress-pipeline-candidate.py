# SPDX-License-Identifier: GPL-3.0-or-later
"""Sequential, private, trusted-parent preparation for one full-body CASP.

The output is a diagnostic mesh, material and scene descriptor; it is not a
native CAS outfit, game write, shader-equivalent render, hostile-input sandbox,
or proof that the adult rig matches age/sex/species requirements. Caller must
own and review input files and use an independently pinned compatible rig.
The script never replaces a prior run and retains completed stages on failure.
"""
import argparse,hashlib,json,pathlib,re,subprocess,sys
root=pathlib.Path(__file__).resolve().parents[1];private=root/'private-input-recovery';DIGEST=re.compile(r'[a-f0-9]{64}\Z');NAME=re.compile(r'[a-z0-9][a-z0-9-]{0,31}\Z');CASP=re.compile(r'034AEECB:[0-9A-F]{8}:[0-9A-F]{16}\Z')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for x in iter(lambda:f.read(1024*1024),b''):h.update(x)
 return h.hexdigest()
def run(script,args):
 p=subprocess.run([sys.executable,str(root/'rig-recovery'/script),*map(str,args)],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=90,check=False)
 if len(p.stdout)>65536 or len(p.stderr)>65536:raise ValueError('preparation output bound')
 if p.returncode:raise ValueError('stage failed: '+script+'; '+p.stderr.decode('utf8','replace')[-1000:])
 return p.stdout

def main():
 p=argparse.ArgumentParser()
 for f in ('package','package-sha','casp','casp-sha','rig','rig-sha','name'):p.add_argument('--'+f,required=True)
 a=p.parse_args()
 if not NAME.fullmatch(a.name) or not CASP.fullmatch(a.casp) or not all(DIGEST.fullmatch(x) for x in (a.package_sha,a.casp_sha,a.rig_sha)):raise ValueError('invalid selected identity')
 if private.is_symlink() or not private.is_dir():raise ValueError('private parent unavailable')
 names=[a.name+'-resolution',a.name+'-diffuse',a.name+'-merged',a.name+'-descriptor',a.name+'-ready']+[a.name+'-geom-'+str(i) for i in range(8)]
 if any((private/n).exists() or (private/n).is_symlink() for n in names):raise ValueError('fresh run name required')
 run('resolve_pinned_casp.py',['--package',a.package,'--package-sha',a.package_sha,'--casp',a.casp,'--casp-sha',a.casp_sha,'--output',names[0]])
 res=private/names[0]/'resolution.json';m=json.loads(res.read_bytes())
 if m['body_type']!=5:raise ValueError('full-body CASP required; age/rig compatibility still unverified')
 geoms=[x for x in m['references'] if x['role']=='lod-0'];tex=[x for x in m['references'] if x['role']=='texture']
 if not 1<=len(geoms)<=8 or len(tex)!=1 or any(x['state']!='source-present-not-rendered' for x in geoms+tex):raise ValueError('required package resources missing')
 run('prepare_pinned_diffuse.py',['--package',a.package,'--package-sha',a.package_sha,'--casp',a.casp,'--casp-sha',a.casp_sha,'--texture-sha',tex[0]['sha256'],'--output',names[1]])
 projection=[]
 for i,g in enumerate(geoms):
  n=names[5+i];run('project_pinned_geom.py',['--package',a.package,'--package-sha',a.package_sha,'--geom',g['resolved'],'--geom-sha',g['sha256'],'--rig',a.rig,'--rig-sha',a.rig_sha,'--output',n]);report=private/n/'report.json';projection.extend(['--projection',report,sha(report)])
 run('merge_resolved_lod.py',['--resolution',res,sha(res),*projection,'--output',names[2]])
 mesh=private/names[2]/'report.json';mat=private/names[1]/'report.json'
 run('build_generic_dress_descriptor.py',['--package',a.package,'--package-sha',a.package_sha,'--resolution',res,sha(res),'--mesh-report',mesh,sha(mesh),'--material-report',mat,sha(mat),'--output',names[3]])
 descriptor=private/names[3]/'descriptor.txt';payload={'schema':1,'descriptor_sha256':sha(descriptor),'mesh_sha256':json.loads(mesh.read_bytes())['mesh_sha256'],'material_sha256':json.loads(mat.read_bytes())['material_sha256'],'source_meshes':len(geoms),'game_modified':False,'native_fidelity':'unverified','age_rig_compatibility':'unverified'}
 ready=private/names[4];ready.mkdir(mode=0o700,exist_ok=False)
 with (ready/'ready.json').open('x') as f:json.dump(payload,f,indent=2)
 print(json.dumps({'stages_completed':4+len(geoms),'source_meshes':len(geoms),'game_modified':False,'native_fidelity':'unverified','age_rig_compatibility':'unverified'}))
if __name__=='__main__':main()
