"""Retain committed native CAS cards until complete replacements are ready.

Exact owned-method continuation; every original native image/grid body remains
unchanged. Production paths are repository-relative; no private work is read.
"""
from pathlib import Path
import copy, hashlib, json, os, re
ROOT=Path(__file__).resolve().parents[1]
import cas_catalog_binding as binding
import cas_cell_attach as attach
import cas_draw_phase as draw
import cas_grid_pool as pool
import cas_grid_transaction as grid
import cas_image_boundary_profile as image
import cas_communication_index as comm
GRID='olympus.layout.RecyclingGridLayout'
LOADER='olympus.resources.ImageLoader'
IMAGE='olympus.controls.ImageResource'
REPLACED=('ApexGridCells','ApexGridCellsY','ApexGridMap','ApexGridBegin','ApexGridMetrics','ApexGridGate','ApexGridPoolPark','ApexGridBind','ApexGridReady','ApexGridPublish','ApexGridAbort','ApexTxnPlan','ApexTxnAdvance')
ADDED=('ApexGridPresentationStart','ApexGridPresentationWatch','ApexGridPresentationFailed','ApexGridPresentationBound','ApexGridPresentationTexture','ApexGridPresentationRollback','ApexGridPresentationPublish')
SOURCES=('tools/cas_grid_presentation.py','tools/CasGridPresentationPatch.java',
 'Source/CASUi/catalog_grid_presentation_methods.as','Source/CASUi/catalog_image_readiness_methods.as',
 'Source/CASUi/catalog_image_resource_readiness_methods.as','tools/cas_grid_pool.py','tools/cas_grid_transaction.py',
 'tools/CasStructuralRolesPatch.java','tools/CasCommunicationIndexPatch.java','tools/CasGridPoolPatch.java')
PRESENTATION_SOURCES=SOURCES[:5]
def sha(raw):return hashlib.sha256(raw).hexdigest()
def pins():return {name:sha((ROOT/name).read_bytes()) for name in SOURCES}
def types(mode):return (LOADER,IMAGE) if mode=='image' else (GRID,)
def added(mode,owner):return ('ApexImageReadyFor',) if mode=='image' else ADDED
def replaced(mode):return () if mode=='image' else REPLACED

def semantics():
    text=(ROOT/'tools/CasGridPresentationPatch.java').read_text()
    rows=re.findall(r'Map.entry\("([^"]+)","([0-9a-f]{64})"\)',text)
    out=dict(rows)
    if len(out)!=22 or len(rows)!=22:raise ValueError('Presentation semantic inventory differs.')
    return out


def replace_method(source, name, replacement):
    start, end = pool.method_extent(source, name)
    return source[:start] + replacement + source[end:]


def change(source, name, before, after):
    return pool.edit_method(source, name, [(before, after)])


def helpers():
    source = pool.transform_helpers(grid.ADAPTER_METHODS + '\n' + grid.CORE_METHODS)
    source = change(source, 'ApexGridCells', 'return mCells;',
        'return apexGridState!=null && apexGridState.presentation!=null && apexGridState.presentation.working ? apexGridState.presentation.stageCells : mCells;')
    source = change(source, 'ApexGridCellsY', 'return mCellsY;',
        'return apexGridState!=null && apexGridState.presentation!=null && apexGridState.presentation.working ? apexGridState.presentation.stageY : mCellsY;')
    source = change(source, 'ApexGridMap', 'return mCellIndexToDataIndexMap;',
        'return apexGridState!=null && apexGridState.presentation!=null && apexGridState.presentation.working ? apexGridState.presentation.stageMap : mCellIndexToDataIndexMap;')
    source = change(source, 'ApexGridBegin', 'revision:0,deferredEvents:0,',
        'presentation:prior!=null && prior.view===mGridView ? prior.presentation : null,revision:0,deferredEvents:0,')
    source = change(source, 'ApexGridBegin', 'var prior:Object=apexGridState;',
        'ApexGridPresentationRollback();\n         var prior:Object=apexGridState;')
    source = change(source, 'ApexGridMetrics', 'var s:Object=apexGridState;',
        '''var s:Object=apexGridState;
         result.thumbnail_failures=[];
         if(s.presentation!=null && s.presentation.failures!=null)
            for each(var failure:Object in s.presentation.failures)
               result.thumbnail_failures.push({slot:int(failure.slot),requested_resource_preview:String(failure.requested_resource).substr(0,512),
                  ea_warning:failure.ea_warning===true,text_diagnostic:failure.text_diagnostic===true});''')
    source = replace_method(source, 'ApexGridGate', '''public function ApexGridGate(j:Object,blocked:Boolean) : void {
         if(blocked) {
            // Input and display readiness are independent. Retain committed
            // cards while a complete replacement is prepared off presentation.
            mGridView.mouseEnabled=false;mGridView.mouseChildren=false;
            ApexGridPresentationStart(j);
         } else if(ApexGridValid(apexGridState.identity)) {
            mGridView.visible=apexGridState.visibleBefore;
            mGridView.mouseEnabled=apexGridState.mouseBefore;mGridView.mouseChildren=apexGridState.childrenBefore;
         }
      }''')
    for name in ('ApexGridBind', 'ApexGridReady'):
        start, end = pool.method_extent(source, name)
        body = source[start:end].replace('mCells', 'ApexGridCells').replace('mCellIndexToDataIndexMap', 'ApexGridMap')
        source = source[:start] + body + source[end:]
    source = change(source, 'ApexGridPoolPark', 'mCellIndexToDataIndexMap[slot]=-1;', 'ApexGridMap[slot]=-1;')
    source = change(source, 'ApexGridBind', 'else cell.visible=true;',
        'else {cell.visible=true;ApexGridPresentationBound(cell);}')
    source = change(source, 'ApexGridBind', 'ApexGridPoolRestore(cell);',
        'ApexGridPoolRestore(cell);ApexGridPresentationWatch(cell);')
    source = replace_method(source, 'ApexGridPublish', '''public function ApexGridPublish(p:Object,j:Object) : void {
         ApexGridPresentationPublish(p,j);
      }''')
    source = change(source, 'ApexGridAbort', 'if(reason=="dispose"',
        'ApexGridPresentationRollback();\n         if(reason=="dispose"')
    source = change(source, 'ApexTxnPlan', 'var a:Object=j.adapter;',
        'if(j.lease)ApexGridPresentationStart(j);\n         var a:Object=j.adapter;')
    source = change(source, 'ApexTxnAdvance',
        'if(j.index>=j.target){j.phase="publish";return false;}',
        'if(j.index>=j.target){j.index=0;j.texturePending=false;j.phase="textures";return false;}')
    anchor = '         if(j.phase=="publish") {'
    new_phase = '''         if(j.phase=="textures") {
            if(j.index>=j.target) {
               if(j.texturePending) {j.index=0;j.texturePending=false;return false;}
               j.phase="publish";return false;
            }
            j.lastOperation="texture";slot=j.index;c=a.ApexGridCells[slot];
            if(a.ApexGridMap[slot]>=0 && !ApexGridPresentationTexture(c))j.texturePending=true;
            j.index++;return true;
         }
''' + anchor
    source = change(source, 'ApexTxnAdvance', anchor, new_phase)
    source += '\n' + (ROOT / 'Source/CASUi/catalog_grid_presentation_methods.as').read_text(encoding='utf-8')
    return source



def inject_grid(original):
    source=pool.inject(original)
    before=pool.transform_helpers(grid.ADAPTER_METHODS+'\n'+grid.CORE_METHODS)
    if source.count(before)!=1:raise ValueError('Complete native pool compiler seam differs.')
    source=source.replace(before,helpers(),1)
    for name in ('olympus.events.AssetLoaderEvent','gamedata.shared.SharedIcons','flash.text.TextField','flash.text.TextFormat'):
        if 'import '+name+';' not in source:source=source.replace('   import ','   import '+name+';\n   import ',1)
    return source


def inject_image(original,kind,tgi):
    source=image.inject(original,kind,tgi)
    fragment=ROOT/('Source/CASUi/catalog_image_readiness_methods.as' if kind=='loader' else 'Source/CASUi/catalog_image_resource_readiness_methods.as')
    at=source.rfind('\n   }')
    if at<0 or 'ApexImageReadyFor' in source:raise ValueError('Native image readiness seam differs.')
    return source[:at]+'\n'+fragment.read_text(encoding='utf-8')+source[at:]

class ABC(binding._ABC):
    def namespace(self,index):
        value=super().namespace(index)
        return re.sub(r'(?<=5:)(RecyclingGridLayout|ImageLoader|ImageResource)\.as\$[0-9]+',r'\1.as$SELF',value)
    def instructions(self,raw):
        # Same strict instruction decoder, plus the reviewed compiler's switch.
        # Divide at switches only after parsing each preceding full instruction.
        r=attach._ABCReader(raw);rows=[]
        single={0x04,0x05,0x06,0x08,0x25,0x2c,0x2d,0x2e,0x2f,0x31,0x40,0x41,0x42,0x49,0x53,0x55,0x56,0x58,0x59,0x5a,0x5b,0x5c,0x5d,0x5e,0x5f,0x60,0x61,0x62,0x63,0x66,0x68,0x6a,0x6c,0x6d,0x6e,0x6f,0x80,0x86,0x92,0x94,0xb2,0xc2,0xc3,0xf0,0xf1}
        double={0x32,0x43,0x44,0x45,0x46,0x4a,0x4c,0x4e,0x4f}
        none={0x01,0x02,0x03,0x07,0x09,0x1c,0x1d,0x1e,0x1f,0x20,0x21,0x23,0x26,0x27,0x28,0x29,0x2a,0x2b,0x30,0x47,0x48,0x50,0x51,0x52,0x57,0x64,0x69,0x70,0x71,0x72,0x73,0x74,0x75,0x76,0x77,0x78,0x81,0x82,0x83,0x84,0x85,0x87,0x88,0x89,0x90,0x91,0x93,0x95,0x96,0x97,0xa0,0xa1,0xa2,0xa3,0xa4,0xa5,0xa6,0xa7,0xa8,0xa9,0xaa,0xab,0xac,0xad,0xae,0xaf,0xb0,0xb1,0xb3,0xb4,0xc0,0xc1,0xc4,0xc5,0xc6,0xc7,*range(0xd0,0xd8)}
        def s24():
            n=int.from_bytes(r.raw(3),'little');return n-(1<<24) if n&(1<<23) else n
        while r.at<len(raw):
            start=r.at;op=r.byte();args=[]
            if 0x0c<=op<=0x1a:args=[s24()]
            elif op==0x1b:
                default=s24();count=r.u30()
                if count>65535:raise ValueError('Unbounded presentation switch.')
                args=[default,count]+[s24() for _ in range(count+1)]
            elif op in single:args=[r.u30()]
            elif op in double:args=[r.u30(),r.u30()]
            elif op==0x24:
                n=r.byte();args=[n-256 if n&128 else n]
            elif op==0x65:args=[r.byte()]
            elif op==0xef:args=[r.byte(),r.u30(),r.byte(),r.u30()]
            elif op not in none:raise ValueError('Unreviewed presentation opcode: '+hex(op))
            rows.append((start,r.at,op,args))
        return rows

def named(a,owner,name):
    namespace,leaf=owner.rsplit('.',1)
    rows=[r for r in a.instances if a.qname(r['name'])=='7:'+leaf+':22:'+namespace]
    if len(rows)!=1:raise ValueError('Exact presentation class absent.')
    rows=rows[0]['traits']['rows'];traits=[r for r in rows if a.string(a.pool(6,r['value']['name'])['name'])==name]
    if len(traits)!=1 or traits[0]['value']['flags']&15 not in (1,2,3):raise ValueError('Exact presentation method/getter absent: '+name)
    bodies=[r for r in a.bodies['rows'] if r['value']['method']==traits[0]['value']['method']]
    if len(bodies)!=1:raise ValueError('Exact presentation body absent: '+name)
    return traits[0],bodies[0]

def semantic(a,row):
    b=row['value'];info=a.methods['rows'][b['method']]['value'];stack,regs,initial,maximum=b['frame']
    q=lambda n:draw._qname(a,n)
    text=str(info['flags'])+'|'+q(info['ret'])+''.join('|'+q(p) for p in info['params'])+'|'+str(regs)+'|'+str(stack)+'|'+str(maximum-initial)
    for r in b['traits']['rows']:
        t=r['value']
        if t['flags']&15 not in (0,6):raise ValueError('Presentation activation has non-slot trait.')
        text+='|local:'+q(t['name'])+':'+q(t['type'])+':'+str(t['slot'])+':'+str(t['value'])+':'+str(t.get('value_kind',0))
    code=a.instructions(b['code']);addresses={x[0]:i for i,x in enumerate(code)};addresses[len(b['code'])]=len(code)
    lines=[args[3] for _,_,op,args in code if op==0xef and len(args)==4 and args[0]==1 and args[3]>0];base=min(lines) if lines else None
    names={0x04,0x05,0x45,0x46,0x4a,0x4c,0x4e,0x4f,0x59,0x5b,0x5c,0x5d,0x5e,0x5f,0x60,0x61,0x66,0x68,0x6a,0x80,0x86,0xb2}
    for start,end,op,args in code:
        text+='\n'+str(op)
        for n,value in enumerate(args):
            target=None
            if 0x0c<=op<=0x1a:target=end+value
            elif op==0x1b and n!=1:target=start+value
            if target is not None:
                if target not in addresses:raise ValueError('Presentation branch leaves instruction boundary.')
                token='@'+str(addresses[target])
            elif n==0 and op in names:token=q(value)
            elif n==1 and op==0xef:token=a.string(value)
            elif n==3 and op==0xef and args[0]==1 and value>0:token='owned-source+'+str(value-base)
            elif n==0 and op==0xf1:token='owned-helper-source'
            elif n==0 and op==0x2c:token=a.string(value)
            elif n==0 and op in (0x2d,0x2e):
                number=a.pool(op-0x2d,value)
                if op==0x2d and number&0x80000000:number-=1<<32
                token=str(number)
            elif n==0 and op==0x2f:
                number=a.pool(2,value)
                if number not in (0.35,):raise ValueError('Unreviewed presentation double constant: '+repr(number))
                token=str(number)
            else:token=str(value)
            text+=':'+token
    for start,end,target,kind,name in b['exceptions']:
        if any(v not in addresses for v in (start,end,target)):raise ValueError('Presentation exception leaves instruction boundary.')
        text+='\ncatch:'+str(addresses[start])+':'+str(addresses[end])+':'+str(addresses[target])+':'+q(kind)+':'+q(name)
    return text

def descriptor(baseline,mode):
    _,raw=binding._abc_payload(baseline);a=ABC(raw).parse();bodies={}
    for owner in types(mode):
        for n in replaced(mode):
            row=named(a,owner,n)[1];bodies[owner+'.'+n]=raw[row['start']:row['end']].hex()
    return dict(pool_counts=[r['count'] for r in a.pools],bodies=bodies)

def reconstruct(final,proof):
    from cas_ui_build import replace_payload
    mode=proof['mode'];prefix,raw=binding._abc_payload(final);a=ABC(raw).parse();d=proof.get('rollback')
    if not isinstance(d,dict) or set(d)!={'pool_counts','bodies'}:raise ValueError('Presentation rollback absent.')
    keys={owner+'.'+n for owner in types(mode) for n in replaced(mode)}
    if not isinstance(d['bodies'],dict) or set(d['bodies'])!=keys:raise ValueError('Presentation rollback body inventory differs.')
    counts=d['pool_counts']
    if not isinstance(counts,list) or len(counts)!=7:raise ValueError('Presentation pool counts absent.')
    total=sum(len(added(mode,t)) for t in types(mode));method_count=a.methods['count']-total
    if method_count<1 or a.bodies['count']<total:raise ValueError('Presentation appended inventory absent.')
    expected_semantics=semantics();patches=[];restored={};old_bodies={};index=0
    for key,value in d['bodies'].items():
        if not isinstance(value,str) or not 0<len(value)<=200000 or re.fullmatch('[0-9a-f]+',value) is None:raise ValueError('Presentation old body invalid or unbounded.')
        bodyraw=bytes.fromhex(value);reader=ABC(bodyraw);old=reader.body();owner,name=key.rsplit('.',1);row=named(a,owner,name)[1]
        if reader.at!=len(bodyraw) or old['method']!=row['value']['method']:raise ValueError('Presentation rollback targets another method.')
        restored[old['method']]=bodyraw;old_bodies[key]=old
    for owner in types(mode):
        namespace,leaf=owner.rsplit('.',1);instance=next(r for r in a.instances if a.qname(r['name'])=='7:'+leaf+':22:'+namespace);traits=instance['traits'];new=added(mode,owner)
        if traits['count']<len(new):raise ValueError('Presentation appended class trait absent.')
        anchor='ApexGridBind' if mode=='grid' else 'LoadImage' if owner==LOADER else 'OnAddedToStage'
        scope=named(a,owner,anchor)[1]['value']['frame'][2]
        for i,n in enumerate(new):
            trait,row=named(a,owner,n);v=trait['value'];expected_id=method_count+index;index+=1
            expected_trait=17 if mode=='image' else 1
            expected_q='7:'+n+(':22:' if mode=='image' else ':5:olympus.layout:RecyclingGridLayout')
            expected_scope=scope+(1 if n=='ApexGridPresentationPublish' else 0)
            if(trait!=traits['rows'][-len(new)+i] or v['method']!=expected_id or v['flags']!=expected_trait or v['dispatch']!=0 or 'metadata' in v or
               a.qname(v['name'])!=expected_q or row!=a.bodies['rows'][-total+index-1] or row['value']['frame'][2]!=expected_scope):raise ValueError('Presentation methods must be exact appended traits/bodies/scopes: '+n)
        patches.append((traits['start'],traits['end'],attach._u30(traits['count']-len(new))+raw[traits['head']:traits['rows'][-len(new)]['start']]))
        for n in (*replaced(mode),*new):
            trait,row=named(a,owner,n);info=a.methods['rows'][row['value']['method']]['value']
            if info['optional'] or info['param_names']:raise ValueError('Presentation ABI has unreviewed optionals.')
            if n in replaced(mode) and row['value']['frame'][2]!=old_bodies[owner+'.'+n]['frame'][2]:raise ValueError('Presentation replaced lexical scope differs.')
            if sha(semantic(a,row).encode())!=expected_semantics.get(owner+'/'+n):raise ValueError('Presentation semantic/CFG identity differs: '+owner+'/'+n)
            if any(op in (0x40,0x43,0x44,0x67) for _,_,op,_ in a.instructions(row['value']['code'])):raise ValueError('Presentation nested/outer dependency.')
    for poolrow,count in zip(a.pools,counts):
        if type(count) is not int or count<0 or count>poolrow['count']:raise ValueError('Presentation constant prefix differs.')
        end=poolrow['head'] if count<=1 else poolrow['rows'][count-2]['end']
        patches.append((poolrow['start'],poolrow['end'],attach._u30(count)+raw[poolrow['head']:end]))
    table=a.methods;patches.append((table['start'],table['end'],attach._u30(method_count)+raw[table['head']:table['rows'][-total]['start']]))
    table=a.bodies;body=attach._u30(table['count']-total)+b''.join(restored.get(r['value']['method'],raw[r['start']:r['end']]) for r in table['rows'][:-total]);patches.append((table['start'],table['end'],body))
    prior=len(raw)
    for start,end,value in sorted(patches,reverse=True):
        if end>prior or start>end:raise ValueError('Presentation rollback spans overlap.')
        raw=raw[:start]+value+raw[end:];prior=start
    return replace_payload(final,prefix+raw)

def chain_adapter(previous,proof,final):
    if not isinstance(previous,dict) or not isinstance(proof,dict) or proof.get('mode') not in ('image','grid'):raise ValueError('Presentation proof absent.')
    mode=proof['mode'];required=('whole_abc_rollback_verified','serialized_owned_bodies_verified','all_unowned_bodies_retained','native_protected_bindings_verified')
    counts={'replaced_owned_bodies':0 if mode=='image' else 13,'appended_methods':2 if mode=='image' else 7,'appended_fields':0,'changed_original_native_bodies':0}
    if(proof.get('ok') is not True or any(proof.get(k) is not True for k in required) or any(type(proof.get(k)) is not int or proof[k]!=v for k,v in counts.items()) or
       proof.get('source_sha256')!=pins() or proof.get('helper_source_sha256')!=sha(helpers().encode()) or
       proof.get('previous_stage_sha256')!=comm.contract_digest(previous) or proof.get('runtime_qualified') is not False or proof.get('hitch_free_claimed') is not False):raise ValueError('Presentation contract fields/source differ.')
    if sha(final)!=proof.get('final_swf_sha256') or sha(binding._abc_payload(final)[1])!=proof.get('abc_sha256'):raise ValueError('Presentation final bytes differ.')
    baseline=reconstruct(final,proof)
    if sha(baseline)!=proof.get('baseline_swf_sha256') or sha(binding._abc_payload(baseline)[1])!=proof.get('baseline_abc_sha256'):raise ValueError('Presentation full ABC rollback differs.')
    if sha(baseline)!=previous.get('patched_resource_sha256'):raise ValueError('Presentation actual previous resource differs.')
    if mode=='grid':
        if previous.get('presentation_contract',{}).get('mode')!='image' or 'grid_pool_contract' not in previous.get('previous_stage_adapter',{}):raise ValueError('Grid presentation requires complete pooled image continuation.')
        verify_adapter(previous,baseline)
    elif 'grid_pool_contract' in previous:pool.verify_adapter(previous,baseline)
    elif 'image_boundary_profile_contract' in previous:image.verify_adapter(previous,baseline)
    else:raise ValueError('Presentation previous adapter unsupported.')
    return dict(base_resource_sha256=previous['base_resource_sha256'],patched_resource_sha256=sha(final),previous_stage_sha256=comm.contract_digest(previous),previous_stage_adapter=copy.deepcopy(previous),postproof_sha256=comm.contract_digest(proof),presentation_contract=copy.deepcopy(proof))

def verify_adapter(adapter,final):
    if not isinstance(adapter,dict) or chain_adapter(adapter.get('previous_stage_adapter'),adapter.get('presentation_contract'),final)!=adapter:raise ValueError('Presentation complete adapter differs.')
    return True


def previous(adapter,final):
    """Verify first, then reconstruct one exact reviewed continuation."""
    verify_adapter(adapter,final)
    return adapter['previous_stage_adapter'],reconstruct(final,adapter['presentation_contract'])


def historical(adapter,final):
    """Undo at most image+grid; no unrelated historical proof is relabeled."""
    count=0
    while isinstance(adapter,dict) and 'presentation_contract' in adapter:
        count+=1
        if count>2:raise ValueError('Unbounded presentation history.')
        adapter,final=previous(adapter,final)
    return adapter,final


def adapt(previous_adapter,baseline,original_swf,ffdec,work):
    """Return final SWF/adapter after full existing image/pool authentication."""
    from cas_ui_build import replace_payload
    original_swf=Path(original_swf);ffdec=Path(ffdec);work=Path(work);baseline=bytes(baseline)
    if not isinstance(previous_adapter,dict):raise ValueError('Presentation incoming adapter absent.')
    pooled='grid_pool_contract' in previous_adapter
    if pooled:pool.verify_adapter(previous_adapter,baseline)
    elif 'image_boundary_profile_contract' in previous_adapter:image.verify_adapter(previous_adapter,baseline)
    else:raise ValueError('Presentation requires the complete current pool/image chain.')
    tg_is=[tgi for tgi,value in image.RAW_PROVIDERS.items() if value==sha(original_swf.read_bytes())]
    if len(tg_is)!=1 or previous_adapter.get('base_resource_sha256')!=image.RAW_PROVIDERS[tg_is[0]]:raise ValueError('Presentation original native provider differs.')
    tgi=tg_is[0];start_pins=pins();work.mkdir(parents=True,exist_ok=True)
    incoming=work/'baseline.swf';incoming.write_bytes(baseline);private=work/'native-source'
    for kind,target,relative in [('loader',LOADER,'olympus/resources/ImageLoader.as'),('resource',IMAGE,'olympus/controls/ImageResource.as')]:
        comm.run([ffdec,'-selectclass',target,'-export','script',private,original_swf],work/(kind+'-export.log'))
        owned=work/('Apex-'+kind+'.as');owned.write_text(inject_image((private/'scripts'/relative).read_text(encoding='utf-8-sig'),kind,tgi),encoding='utf-8')
        out=work/(kind+'-compiled.swf');comm.run([ffdec,'-importAssets','yes,local','-replace',incoming,out,target,owned],work/(kind+'-compile.log'));incoming=out
    classes=work/'classes';classes.mkdir(exist_ok=True);jar=ffdec.with_name('ffdec.jar')
    comm.run(['javac','-cp',jar,'-d',classes,ROOT/'tools/CasStructuralRolesPatch.java',ROOT/'tools/CasCommunicationIndexPatch.java',ROOT/'tools/CasGridPoolPatch.java',ROOT/'tools/CasGridPresentationPatch.java'],work/'javac.log')
    adapter=previous_adapter;current=baseline
    for mode in (('image','grid') if pooled else ('image',)):
        if mode=='grid':
            comm.run([ffdec,'-selectclass',GRID,'-export','script',private,original_swf],work/'grid-export.log')
            owned=work/'RecyclingGridLayout.as';owned.write_text(inject_grid((private/'scripts/olympus/layout/RecyclingGridLayout.as').read_text(encoding='utf-8-sig')),encoding='utf-8')
            basefile=work/'image-final.swf';incoming=work/'grid-compiled.swf'
            comm.run([ffdec,'-importAssets','yes,local','-replace',basefile,incoming,GRID,owned],work/'grid-compile.log')
        basefile=work/(mode+'-baseline.swf');basefile.write_bytes(current)
        output=work/(mode+'-retained.abc');report=work/(mode+'-proof.json')
        comm.run(['java','-cp',str(jar)+os.pathsep+str(classes),'CasGridPresentationPatch',mode,basefile,incoming,output,report],work/(mode+'-transplant.log'))
        abc=output.read_bytes();proof=json.loads(report.read_text())
        if proof.get('ok') is not True or proof.get('abc_sha256')!=sha(abc):raise ValueError('Presentation retained ABC differs.')
        if pins()!=start_pins:raise ValueError('Presentation source changed during compilation; discard output.')
        final=replace_payload(current,binding._abc_payload(current)[0]+abc)
        proof.update(source_sha256=start_pins,helper_source_sha256=sha(helpers().encode()),previous_stage_sha256=comm.contract_digest(adapter),rollback=descriptor(current,mode),final_swf_sha256=sha(final))
        adapter=chain_adapter(adapter,proof,final);current=final
        (work/(mode+'-final.swf')).write_bytes(final);report.write_text(json.dumps(proof,indent=2)+'\n')
    if pins()!=start_pins:raise ValueError('Presentation source changed before return; discard output.')
    return current,adapter


def unwrap_providers(evidence,resources,dependencies=None):
    """Verify both current providers before legacy provider checks run."""
    import dbpf_build,maru_companion
    keyset={dbpf_build.tgi(maru_companion.GRID_LIBRARY),dbpf_build.tgi(maru_companion.CANONICAL_GRID_LIBRARY)}
    if not isinstance(evidence,dict) or set(evidence)!=keyset:raise ValueError('Both native presentation providers required.')
    current=any(isinstance(a,dict) and 'presentation_contract' in a for a in evidence.values())
    if not current:return evidence,resources,dependencies
    out=dict(resources);providers={};deps=copy.deepcopy(dependencies)
    for key in keyset:
        adapter=evidence[key]
        if not isinstance(adapter,dict) or adapter.get('presentation_contract',{}).get('mode')!='grid':raise ValueError('Both native providers require the complete grid presentation.')
        tgi=tuple(int(n,16) for n in key.split(':'));providers[key],out[tgi]=historical(adapter,resources.get(tgi,b''))
    dependency=maru_companion.UNMODIFIED_OLYMPUS_LIBRARY
    if dependency in resources:
        key=dbpf_build.tgi(dependency)
        if not isinstance(dependencies,dict) or set(dependencies)!={key} or dependencies[key].get('presentation_contract',{}).get('mode')!='image':raise ValueError('The third image provider presentation proof is required.')
        deps={};deps[key],out[dependency]=historical(dependencies[key],resources[dependency])
    elif dependencies:raise ValueError('Presentation dependency has no resource.')
    return providers,out,deps


def unwrap_manifest(info,resources):
    """Validate the current layer, then run unchanged strict legacy checks."""
    import dbpf_build,maru_companion
    source=info.get('source_pins',{}) if isinstance(info,dict) else {}
    providers=info.get('grid_provider_adapters') if isinstance(info,dict) else None
    dependencies=info.get('communication_dependency_adapters') if isinstance(info,dict) else None
    current=any(name in source for name in PRESENTATION_SOURCES) or any(isinstance(a,dict) and 'presentation_contract' in a for group in (providers,dependencies) for a in (group or {}).values())
    if not current:return info,resources
    if not isinstance(source,dict) or any(source.get(name)!=value for name,value in pins().items()):raise ValueError('Presentation source pins are missing, partial or stale.')
    # All three must be present even when only one declares a new stage.
    p,r,d=unwrap_providers(providers,resources,dependencies)
    if p is providers:raise ValueError('Current sources require presentation continuations, not a legacy downgrade.')
    key=dbpf_build.tgi(maru_companion.UNMODIFIED_OLYMPUS_LIBRARY)
    if not isinstance(d,dict) or set(d)!={key}:raise ValueError('Current sources require all three image domains.')
    updated=copy.deepcopy(info);updated['grid_provider_adapters']=p;updated['communication_dependency_adapters']=d
    updated['companion_code_merge']['grid_library_adapter']=p[dbpf_build.tgi(maru_companion.GRID_LIBRARY)]
    for key,adapter in {**p,**d}.items():updated['patched_resources'][key]=adapter['patched_resource_sha256']
    return updated,r
