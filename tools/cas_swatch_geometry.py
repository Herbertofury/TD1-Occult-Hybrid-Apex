"""Strict terminal native SkinTone geometry continuation; no game/profile API."""
from pathlib import Path
import hashlib,json,os,re
import cas_catalog_binding as binding
import cas_cell_attach as attach
import cas_communication_index as comm
import cas_draw_phase as phase

ROOT=Path(__file__).resolve().parents[1]
TYPES=('ColorSwatchPanel','ColorSwatchPanelCellView')
METHODS=('ApexSwatchGeometry','ApexSwatchGroupGeometry')
SOURCES=('tools/cas_swatch_geometry.py','tools/CasSwatchGeometryPatch.java',
         'tools/CasStructuralRolesPatch.java','tools/CasCommunicationIndexPatch.java',
         'Source/CASUi/swatch_geometry_adapter_methods.as','Source/CASUi/swatch_group_geometry_adapter_methods.as')
SEMANTICS={'ApexSwatchGeometry':'afe0a1083e9edab5870a3e3766a50b63a94fc2823304ce9d8c109b96091f5ca3',
           'ApexSwatchGroupGeometry':'128049fdc011312b5d98e1803cc11e5013c18ea1252544e8376d0d27e96695c8'}
DONOR='c97afa8f0362a0452b359074769b9c99174444dd211927d08972091db3391969'

def digest(raw):return hashlib.sha256(raw).hexdigest()

def named(a,type,name):
    owners=[i for i in a.instances if a.qname(i['name'])=='7:'+type+':22:widgets.CAS.controls']
    if len(owners)!=1:raise ValueError('Exact native swatch class absent.')
    traits=owners[0]['traits'];rows=[r for r in traits['rows'] if a.string(a.pool(6,r['value']['name'])['name'])==name]
    if len(rows)!=1:raise ValueError('Exact swatch member absent: '+name)
    return owners[0],rows[0]

def method(a,type,name):
    owner,row=named(a,type,name);t=row['value']
    if t['flags']&15!=1:raise ValueError('Native swatch method kind differs.')
    bodies=[b for b in a.bodies['rows'] if b['value']['method']==t['method']]
    if len(bodies)!=1:raise ValueError('Exact swatch body absent.')
    return owner,row,bodies[0]

def semantic(a,row):
    b=row['value'];info=a.methods['rows'][b['method']]['value'];stack,regs,initial,maximum=b['frame']
    if b['exceptions'] or b['traits']['count'] or info['optional']:raise ValueError('Swatch helper has an activation/exception/optional dependency.')
    text=str(info['flags'])+'|'+phase._qname(a,info['ret'])+''.join('|'+phase._qname(a,p) for p in info['params'])+'|'+str(regs)+'|'+str(stack)+'|'+str(maximum-initial)
    code=a.instructions(b['code']);addresses={x[0]:i for i,x in enumerate(code)};addresses[len(b['code'])]=len(code)
    names={0x04,0x05,0x45,0x46,0x4a,0x4c,0x4e,0x4f,0x59,0x5b,0x5c,0x5d,0x5e,0x5f,0x60,0x61,0x66,0x68,0x6a,0x80,0x86,0xb2}
    for start,end,op,args in code:
        text+='\n'+str(op)
        for n,value in enumerate(args):
            if 0x0c<=op<=0x1a:
                if end+value not in addresses:raise ValueError('Swatch branch leaves an instruction boundary.')
                token='@'+str(addresses[end+value])
            elif n==0 and op in names:token=phase._qname(a,value)
            elif n==1 and op==0xef:token=a.string(value)
            elif n==0 and op==0xf1:token='owned-helper-source'
            elif n==0 and op==0x2c:token=a.string(value)
            elif n==0 and op in (0x2d,0x2e):
                number=a.pool(op-0x2d,value)
                if op==0x2d and number&0x80000000:number-=1<<32
                token=str(number)
            elif n==0 and op==0x2f:
                number=a.pool(2,value)
                # This reviewed helper has only these fixed decimal constants.
                if number not in (0.01,0.5,1.6):raise ValueError('Swatch helper acquired an unreviewed double constant.')
                token=str(number)
            else:token=str(value)
            text+=':'+token
    return text

def rollback_descriptor(baseline):
    _,data=binding._abc_payload(baseline);a=binding._ABC(data).parse()
    return {'pool_counts':[p['count'] for p in a.pools],
            'scopes':[method(a,t,'ResetLayout' if n==0 else 'Draw')[2]['value']['frame'][2] for n,t in enumerate(TYPES)]}

def reconstruct_previous(final,proof):
    from cas_ui_build import replace_payload
    prefix,data=binding._abc_payload(final);a=binding._ABC(data).parse();desc=proof.get('rollback')
    if not isinstance(desc,dict) or set(desc)!={'pool_counts','scopes'} or len(desc['scopes'])!=2 or any(type(v)is not int for v in desc['scopes']):raise ValueError('Exact swatch rollback descriptor absent.')
    counts=desc['pool_counts'];patches=[]
    if not isinstance(counts,list) or len(counts)!=7:raise ValueError('Swatch pool prefix absent.')
    for pool,count in zip(a.pools,counts):
        if type(count)is not int or not 0<=count<=pool['count']:raise ValueError('Swatch pool prefix differs.')
        end=pool['head'] if count<=1 else pool['rows'][count-2]['end'];patches.append((pool['start'],pool['end'],attach._u30(count)+data[pool['head']:end]))
    total=a.methods['count']-2
    for n,(owner_type,name) in enumerate(zip(TYPES,METHODS)):
        owner,t,b=method(a,owner_type,name);traits=owner['traits'];v=t['value']
        if(v['method']!=total+n or t!=traits['rows'][-1] or b!=a.bodies['rows'][-2+n] or
           v['flags']!=1 or v['dispatch']!=0 or a.qname(v['name'])!='7:'+name+':22:' or
           b['value']['frame'][2]!=desc['scopes'][n] or digest(semantic(a,b).encode())!=SEMANTICS[name]):raise ValueError('Reviewed appended swatch method differs.')
        remove=2 if n==0 else 1
        if n==0:
            _,f=named(a,owner_type,'apexSwatchGeometry');fv=f['value']
            if(f!=traits['rows'][-2] or fv['flags']!=0 or fv['slot']!=0 or fv['value']!=0 or
               a.qname(fv['type'])!='7:Object:22:' or a.qname(fv['name'])!='7:apexSwatchGeometry:5:widgets.CAS.controls:ColorSwatchPanel'):
                raise ValueError('Swatch state is not the exact appended default-null private Object.')
        patches.append((traits['start'],traits['end'],attach._u30(traits['count']-remove)+data[traits['head']:traits['rows'][-remove]['start']]))
    for table in (a.methods,a.bodies):patches.append((table['start'],table['end'],attach._u30(table['count']-2)+data[table['head']:table['rows'][-2]['start']]))
    prior=len(data)
    for start,end,raw in sorted(patches,reverse=True):
        if end>prior or start>end:raise ValueError('Overlapping swatch rollback spans.')
        data=data[:start]+raw+data[end:];prior=start
    return replace_payload(final,prefix+data)

def inject(original,owned):
    if 'ApexSwatch' in original:raise ValueError('Native swatch adapter already present.')
    original=re.sub(r'\s*\[Embed\([^\n]*\)\]','',original).replace('   import ','   import olympus.core.widget.Margin;\n   import ',1)
    at=original.rfind('\n   }')
    if at<0:raise ValueError('Native swatch class boundary absent.')
    return original[:at]+'\n'+owned.replace('new olympus.core.widget.Margin(', 'new Margin(')+original[at:]

def adapt(previous,baseline,donor,scripts,ffdec,work):
    from cas_ui_build import replace_payload
    if phase.verify_contract(previous,baseline)is not True:raise ValueError('Complete incoming Draw-phase chain differs.')
    work=Path(work);work.mkdir(parents=True,exist_ok=True);ffdec=Path(ffdec);pins={n:digest((ROOT/n).read_bytes()) for n in SOURCES}
    incoming=work/'baseline.swf';incoming.write_bytes(baseline);compiled=incoming
    for type,file in zip(TYPES,SOURCES[-2:]):
        owned=work/(type+'.as');owned.write_text(inject((Path(scripts)/('widgets/CAS/controls/'+type+'.as')).read_text(encoding='utf-8'),(ROOT/file).read_text(encoding='utf-8')),encoding='utf-8')
        destination=work/(type+'.swf');comm.run([ffdec,'-importAssets','yes,local','-replace',compiled,destination,'widgets.CAS.controls.'+type,owned],work/(type+'.log'));compiled=destination
    classes=work/'classes';classes.mkdir(exist_ok=True);jar=ffdec.with_name('ffdec.jar')
    comm.run(['javac','-cp',jar,'-d',classes,ROOT/'tools/CasStructuralRolesPatch.java',ROOT/'tools/CasCommunicationIndexPatch.java',ROOT/'tools/CasSwatchGeometryPatch.java'],work/'javac.log')
    out=work/'retained.abc';report=work/'proof.json';comm.run(['java','-cp',str(jar)+os.pathsep+str(classes),'CasSwatchGeometryPatch',incoming,compiled,donor,out,report],work/'transplant.log')
    proof=json.loads(report.read_text());abc=out.read_bytes()
    if proof.get('ok')is not True or proof.get('abc_sha256')!=digest(abc) or pins!={n:digest((ROOT/n).read_bytes()) for n in SOURCES}:raise ValueError('Swatch compilation output/source changed.')
    proof.update(source_sha256=pins,previous_stage_sha256=comm.contract_digest(previous),rollback=rollback_descriptor(baseline))
    return replace_payload(baseline,binding._abc_payload(baseline)[0]+abc),proof

def chain_contract(previous,proof,final):
    required=('same_native_class_scopes','same_native_field_bindings','original_callbacks_feeds_initializers_retained','all_unrelated_bodies_exact','full_abc_rollback_exact')
    if(not isinstance(previous,dict) or not isinstance(proof,dict) or proof.get('ok')is not True or proof.get('phase')!='native-swatch-geometry' or
       any(proof.get(k)is not True for k in required) or proof.get('original_donor_sha256')!=DONOR or
       any(type(proof.get(k))is not int or proof[k]!=v for k,v in {'appended_methods':2,'appended_fields':1,'changed_native_bodies':0}.items()) or
       proof.get('baseline_swf_sha256')!=previous.get('final_swf_sha256') or proof.get('previous_stage_sha256')!=comm.contract_digest(previous) or
       proof.get('source_sha256')!={n:digest((ROOT/n).read_bytes()) for n in SOURCES} or proof.get('abc_sha256')!=digest(binding._abc_payload(final)[1])):
        raise ValueError('Swatch geometry continuation/provenance differs.')
    baseline=reconstruct_previous(final,proof)
    if digest(baseline)!=proof['baseline_swf_sha256'] or digest(binding._abc_payload(baseline)[1])!=proof.get('baseline_abc_sha256'):raise ValueError('Swatch geometry does not reconstruct its exact prior Main.')
    if phase.verify_contract(previous,baseline)is not True:raise ValueError('Swatch prior full chain differs.')
    return dict(previous_stage_contract=json.loads(json.dumps(previous)),previous_stage_sha256=comm.contract_digest(previous),
                swatch_geometry_contract=json.loads(json.dumps(proof)),postproof_sha256=comm.contract_digest(proof),final_swf_sha256=digest(final))

def verify_contract(contract,final):
    if not isinstance(contract,dict) or chain_contract(contract.get('previous_stage_contract'),contract.get('swatch_geometry_contract'),final)!=contract:raise ValueError('Swatch complete continuation differs.')
    return True
