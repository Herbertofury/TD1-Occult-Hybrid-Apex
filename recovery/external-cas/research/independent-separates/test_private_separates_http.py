# SPDX-License-Identifier: GPL-3.0-or-later
"""Private opt-in local fixture replay; paths/config provided by trusted caller.

Does not test a browser, arbitrary selections, native game fidelity or game writes.
"""
import argparse, hashlib, json, pathlib, select, signal, subprocess, sys, urllib.request, urllib.error

def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--bindings',required=True);a=p.parse_args()
 proc=subprocess.Popen([sys.executable,str(pathlib.Path(__file__).with_name('run_scene_gateway.py')),'--config',a.config,'--config-sha',sha(a.config),'--bindings',a.bindings,'--bindings-sha',sha(a.bindings)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 try:
  if not select.select([proc.stdout],[],[],60)[0]:raise AssertionError('gateway did not become ready')
  url=proc.stdout.readline().strip().removesuffix('/cas-room');assert url.startswith('http://127.0.0.1:')
  def get(path):
   with urllib.request.urlopen(url+path,timeout=60) as r:return r.read()
  def post(path,data):
   q=urllib.request.Request(url+path,data=json.dumps(data).encode(),method='POST',headers={'Origin':url,'Content-Type':'application/json','X-CAS-Request':'1'})
   with urllib.request.urlopen(q,timeout=90) as r:return json.load(r)
  binding=json.loads(get('/prepared-dresses')); assert binding['schema']==3 and binding['inspect_only'] and not binding['game_modified']
  state=json.loads(get('/scene-catalog')); initial=state['active']; assert len(state['entries'])==4
  bytoken={}
  for row in binding['items']:
   for token,target in row['transitions'].items():
    if token==target:bytoken.setdefault(token,{})[row['kind']]=row['part_id']
  assert set(bytoken[initial])=={'top','bottom','hair','shoes','eyes','tattoo'}
  base=bytoken[initial]; sequence=[];current=initial
  for kind in ('top','bottom','top'):
   prior=bytoken[current];candidates=[r for r in binding['items'] if r['kind']==kind and r['part_id']!=prior[kind] and current in r['transitions']];assert len(candidates)==1
   target=candidates[0]['transitions'][current]; chosen=bytoken[target];assert chosen[kind]!=prior[kind] and all(chosen[k]==prior[k] for k in prior if k!=kind)
   state=json.loads(get('/scene-catalog')); assert state['active']==current;prior_token=current
   post('/scene-switch',{'token':target,'generation':state['generation']});current=target
   # Reusing a prior generation and asking for an unknown scene must fail
   # without disturbing the verified last-good scene.
   for data in ({'token':prior_token,'generation':state['generation']},{'token':'f'*32,'generation':state['generation']+1}):
    try:post('/scene-switch',data);raise AssertionError('invalid switch accepted')
    except urllib.error.HTTPError as e:assert e.code==409
    assert json.loads(get('/scene-catalog'))['active']==target
   frame=get('/cc-frame?yaw=0&brightness=0&saturation=0&hue=0&opacity=16384');assert len(frame)==512*512*3
   sequence.append(hashlib.sha256(frame).hexdigest())
  assert len(set(sequence))==3
  assert bytoken[current]['top']==base['top'] and bytoken[current]['bottom']!=base['bottom']
  print('PASS: source-bound top, bottom, top switches; other four slots retained; three distinct preview frames; stale and unknown switches retain last good; no game writes')
 finally:
  proc.send_signal(signal.SIGTERM)
  try:proc.wait(timeout=20)
  except subprocess.TimeoutExpired:proc.kill();proc.wait()
  print('gateway exit',proc.returncode)
if __name__=='__main__':main()
