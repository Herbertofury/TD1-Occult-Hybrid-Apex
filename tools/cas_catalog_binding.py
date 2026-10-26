"""One native mLayerPanels bind with a fresh, exact-message geometry receipt.

Prototype postpass only. It is not part of the CAS builder until its new native
call site and its current Main continuation have passed actual qualification.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import struct

import cas_communication_index as comm
import cas_cell_attach as attach

ROOT=Path(__file__).resolve().parents[1]
TARGET='widgets.CAS.Customizer.CASCustomizerMain'
SOURCES=('tools/cas_catalog_binding.py','tools/CasCatalogBindingPatch.java','tools/CasStructuralRolesPatch.java','tools/CasCommunicationIndexPatch.java')
NATIVE_SHA256='f91d35898c71a91be92a16ff09f1b546555b06b7beba929c51f093b729d8da0e'
NATIVE_BIND_SHA256='86157039c4e2301508bb20948b7ce9322a1a949714060f41a9d3e15220792e38'
SEMANTICS={
    'ApexCatalogBindingWidth':'c05c3790f06381df675159dab552019fc6674e7bdfbd169bd1809493ff137a3f',
    'ApexCatalogNativeBinding':'e191121a298137862c676a2a424a423107f9bf528a993555de1e86cad62561d2',
    'ApexCatalogObserveBinding':'d6603b4d21dd8fb6ee682fc55b82687108b9b21a01cc167a84787d431749f487',
}

FIELDS=r'''
      private var apexColumns:Object;
      private var apexCatalogPrefs:Object;
      private var apexCardPrefs:Object;
      private var apexCardGeometry:Object;
      private var apexCardLayout:Object;
      private var apexCatalogSignature:String;
      private var apexCatalogBinding:Object;
      private var apexCatalogBindingDirty:Boolean;
      private var apexCatalogBoundWidth:Number;
'''

HELPERS=r'''
      private function ApexCatalogBindingWidth() : Number
      {
         var panel:Object=mCurrentPanel;
         if(stage==null || panel==null || (panel!==mcClothingPanel && panel!==mcBodyModPanel && panel!==mcFaceModPanel &&
             panel!==mcGenericCatalogPanel && panel!==mcFeaturedFaceLookPanel && panel!==mcSkinColorPanel) || panel.visible!==true || panel.stage!==stage ||
            panel.mcTileList==null || panel.mcPanelBackground==null || apexCardGeometry==null || apexCardLayout==null ||
            apexCatalogPrefs==null || apexCardPrefs==null || apexCatalogSignature==null || apexCatalogSignature=="" ||
            apexCardGeometry.applying===true || apexCardGeometry.panel!==panel ||
            apexCardGeometry.grid!==panel.mcTileList.mGridLayout ||
            int(apexCardLayout.requested_columns)!=int(apexCatalogPrefs.columns) ||
            Number(apexCardLayout.requested_scale)!=Number(apexCardPrefs.scale) ||
            Number(apexCardLayout.requested_gap_x)!=Number(apexCardPrefs.gap_x) ||
            Number(apexCardLayout.gap_y)!=Number(apexCardPrefs.gap_y)) return NaN;
         var width:Number=Number(panel.mcPanelBackground.width);
         if(!isFinite(width) || width<=0 || width!==Number(apexCardLayout.width))return NaN;
         return width;
      }

      private function ApexCatalogNativeBinding(display:DisplayObject,view:Number,screen:Number,maximum:Number,message:Object) : void
      {
         var geometry:Object=apexCardGeometry;
         if(geometry!=null)delete geometry.binding_receipt;
         var width:Number=ApexCatalogBindingWidth();
         var panel:Object=mCurrentPanel;var signature:String=apexCatalogSignature;
         var sim:String=mCurrSimInfo==null ? "" : String(mCurrSimInfo.simId);var state:int=int(mCurrState);
         var fitted:Boolean=display===mLayerPanels && isFinite(width) && message!=null &&
            typeof message.view_x_offset=="number" && typeof message.screen_x_offset=="number" && typeof message.screen_x_max=="number" &&
            isFinite(message.view_x_offset) && isFinite(message.screen_x_offset) && isFinite(message.screen_x_max) &&
            view===Number(message.view_x_offset) && screen===Number(message.screen_x_offset)+CASCustomizerTunables.PANEL_SCREEN_OFFSET_X &&
            isFinite(maximum);
         var clamp:Number=fitted ? Math.max(maximum,width+12) : maximum;
         if(fitted && apexColumns!=null && typeof apexColumns.preferred_width=="number" && isFinite(apexColumns.preferred_width) &&
            apexColumns.preferred_width>=80 && typeof apexColumns.width_anchor=="number" && isFinite(apexColumns.width_anchor) &&
            apexColumns.width_panel===mCurrentPanel && mCurrSimInfo!=null && apexColumns.width_sim===String(mCurrSimInfo.simId))
            clamp=Math.max(maximum,Number(apexColumns.width_anchor));
         // This is always the original native method and is invoked exactly
         // once. Its failure/throw propagates; no successful receipt is written.
         this.BindDisplayObjectToSim(display,view,screen,clamp);
         if(!fitted || geometry!==apexCardGeometry || panel!==mCurrentPanel || width!==ApexCatalogBindingWidth() ||
            signature!==apexCatalogSignature || mCurrSimInfo==null || sim!==String(mCurrSimInfo.simId) || state!==int(mCurrState))return;
         // Same Dispatch payload, not a timer/owner guess. The later original
         // message observer consumes this one receipt; future dispatches bind
         // again through this wrapper even if their numeric values are equal.
         geometry.binding_receipt={view:Number(message.view_x_offset),screen:Number(message.screen_x_offset),maximum:maximum,
            native_message:message,native_stage:stage,native_panel:panel,native_grid:panel.mcTileList.mGridLayout,
            native_signature:signature,native_width:width,native_sim:sim,native_state:state,native_input_max:Number(message.screen_x_max)};
      }
'''

OBSERVER=r'''
      private function ApexCatalogObserveBinding(value:Object) : void
      {
         var prior:Object=apexCardGeometry==null ? null : apexCardGeometry.binding_receipt;
         if(apexCardGeometry!=null)delete apexCardGeometry.binding_receipt;
         if(value==null || typeof value.view_x_offset!="number" || typeof value.screen_x_offset!="number" ||
            typeof value.screen_x_max!="number" || !isFinite(value.view_x_offset) ||
            !isFinite(value.screen_x_offset) || !isFinite(value.screen_x_max)) return;
         var width:Number=ApexCatalogBindingWidth();
         var matched:Boolean=prior!=null && prior.native_message===value && isFinite(width) &&
            prior.native_stage===stage && prior.native_panel===mCurrentPanel &&
            prior.native_grid===mCurrentPanel.mcTileList.mGridLayout && prior.native_signature===apexCatalogSignature &&
            prior.native_width===width && mCurrSimInfo!=null && prior.native_sim===String(mCurrSimInfo.simId) &&
            prior.native_state===int(mCurrState) && prior.view===Number(value.view_x_offset) &&
            prior.screen===Number(value.screen_x_offset) && prior.native_input_max===Number(value.screen_x_max);
         // Strip the one-shot receipt, including the payload reference. A
         // different object, changed geometry or reordered listener falls back
         // to the existing corrective bind rather than suppressing the work.
         apexCatalogBinding={view:Number(value.view_x_offset),screen:Number(value.screen_x_offset),
            maximum:matched ? Number(prior.maximum) : Number(value.screen_x_max),
            native_binding_applied:matched,native_binding_width:matched ? width : 0};
         if(matched)apexCatalogBoundWidth=width;
         apexCatalogBindingDirty=!matched;
      }
'''


def digest(data):return hashlib.sha256(data).hexdigest()


class _ABC(attach._ABCReader):
    """Structural ABC parser for exact rollback, not an ActionScript executor."""
    def table(self,read,pool=False):
        start=self.at;count=self.count();head=self.at;rows=[]
        for _ in range(max(0,count-1) if pool else count):
            at=self.at;value=read();rows.append(dict(start=at,end=self.at,value=value))
        return dict(start=start,head=head,end=self.at,count=count,rows=rows)

    def traits_table(self):
        def trait():
            name=self.u30();flags=self.byte();kind=flags&15;out=dict(name=name,flags=flags)
            if kind in (0,6):
                out.update(slot=self.u30(),type=self.u30(),value=self.u30())
                if out['value']:out['value_kind']=self.byte()
            elif kind in (1,2,3):out.update(dispatch=self.u30(),method=self.u30())
            elif kind in (4,5):out.update(slot=self.u30(),other=self.u30())
            else:raise ValueError('Unknown ABC trait kind.')
            if flags&64:out['metadata']=[self.u30() for _ in range(self.count())]
            return out
        return self.table(trait)

    def method_info(self):
        count=self.count();ret=self.u30();params=[self.u30() for _ in range(count)]
        name=self.u30();flags=self.byte();optional=[];param_names=[]
        if flags&8:optional=[(self.u30(),self.byte()) for _ in range(self.count())]
        if flags&128:param_names=[self.u30() for _ in range(count)]
        return dict(ret=ret,params=params,name=name,flags=flags,optional=optional,param_names=param_names)

    def body(self):
        method=self.u30();frame=tuple(self.u30() for _ in range(4));length=self.count();code=self.raw(length)
        exceptions=[tuple(self.u30() for _ in range(5)) for _ in range(self.count())]
        return dict(method=method,frame=frame,code=code,exceptions=exceptions,traits=self.traits_table())

    def parse(self):
        self.raw(4);self.pools=[]
        for _ in range(2):self.pools.append(self.table(self.uint,True))
        self.pools.append(self.table(lambda:struct.unpack('<d',self.raw(8))[0],True))
        self.pools.append(self.table(lambda:self.raw(self.count()).decode('utf-8'),True))
        self.pools.append(self.table(lambda:(self.byte(),self.u30()),True))
        self.pools.append(self.table(lambda:[self.u30() for _ in range(self.count())],True))
        def multiname():
            kind=self.byte();q=dict(kind=kind,name=0,namespace=0,namespace_set=0,qname=0,params=[])
            if kind in (7,13):q.update(namespace=self.u30(),name=self.u30())
            elif kind in (9,14):q.update(name=self.u30(),namespace_set=self.u30())
            elif kind in (15,16):q['name']=self.u30()
            elif kind in (17,18):pass
            elif kind in (27,28):q['namespace_set']=self.u30()
            elif kind==29:
                q['qname']=self.u30();q['params']=[self.u30() for _ in range(self.count())]
            else:raise ValueError('Unknown ABC multiname kind.')
            return q
        self.pools.append(self.table(multiname,True));self.methods=self.table(self.method_info)
        def metadata():
            self.u30()
            for _ in range(self.count()*2):self.u30()
        self.table(metadata)
        count=self.count();self.instances=[]
        for _ in range(count):
            name=self.u30();sup=self.u30();flags=self.byte()
            protected=self.u30() if flags&8 else 0
            interfaces=[self.u30() for _ in range(self.count())];init=self.u30();traits=self.traits_table()
            self.instances.append(dict(name=name,super=sup,flags=flags,protected=protected,interfaces=interfaces,init=init,traits=traits))
        self.classes=[]
        for _ in range(count):self.classes.append(dict(init=self.u30(),traits=self.traits_table()))
        for _ in range(self.count()):self.u30();self.traits_table()
        self.bodies=self.table(self.body)
        if self.at!=len(self.data):raise ValueError('Trailing ABC data.')
        return self

    def pool(self,index,item):
        if type(item) is not int or not 0<item<len(self.pools[index]['rows'])+1:raise ValueError('ABC pool reference out of bounds.')
        return self.pools[index]['rows'][item-1]['value']

    def string(self,index):return '' if index==0 else self.pool(3,index)

    def namespace(self,index):
        if index==0:return '*'
        kind,name=self.pool(4,index);value=self.string(name)
        if kind==5:value=re.sub(r'^CASCustomizerMain\.as\$[0-9]+$','CASCustomizerMain.as$SELF',value)
        return str(kind)+':'+value

    def qname(self,index,depth=0):
        if index==0:return '*'
        if depth>16:raise ValueError('Unbounded ABC generic name.')
        q=self.pool(6,index);out=str(q['kind'])+':'+self.string(q['name'])+':'+self.namespace(q['namespace'])
        if q['namespace_set']:out+='['+''.join(self.namespace(n)+';' for n in self.pool(5,q['namespace_set']))+']'
        if q['qname']:out+='<'+self.qname(q['qname'],depth+1)+'>'
        for p in q['params']:out+='<'+self.qname(p,depth+1)+'>'
        return out

    def named(self,name):
        matches=[r for r in self.instances if self.qname(r['name'])=='7:CASCustomizerMain:22:widgets.CAS.Customizer']
        if len(matches)!=1:raise ValueError('Exact Main class absent.')
        traits=matches[0]['traits'];rows=[r for r in traits['rows'] if self.string(self.pool(6,r['value']['name'])['name'])==name]
        if len(rows)!=1 or rows[0]['value']['flags']&15 not in (1,2,3):raise ValueError('Exact Main method absent: '+name)
        trait=rows[0]['value'];bodies=[r for r in self.bodies['rows'] if r['value']['method']==trait['method']]
        if len(bodies)!=1:raise ValueError('Exact Main body absent: '+name)
        return matches[0],rows[0],bodies[0]

    def instructions(self,raw):
        r=attach._ABCReader(raw);rows=[]
        single={0x04,0x05,0x06,0x08,0x25,0x2c,0x2d,0x2e,0x2f,0x31,0x40,0x41,0x42,0x49,0x53,0x55,0x56,0x58,0x59,0x5a,0x5b,0x5c,0x5d,0x5e,0x5f,0x60,0x61,0x62,0x63,0x66,0x68,0x6a,0x6c,0x6d,0x6e,0x6f,0x80,0x86,0x92,0x94,0xb2,0xc2,0xc3,0xf0,0xf1}
        double={0x32,0x43,0x44,0x45,0x46,0x4a,0x4c,0x4e,0x4f}
        none={0x01,0x02,0x03,0x07,0x09,0x1c,0x1d,0x1e,0x1f,0x20,0x21,0x23,0x26,0x27,0x28,0x29,0x2a,0x2b,0x30,0x47,0x48,0x50,0x51,0x52,0x57,0x64,0x69,0x70,0x71,0x72,0x73,0x74,0x75,0x76,0x77,0x78,0x81,0x82,0x83,0x84,0x85,0x87,0x88,0x89,0x90,0x91,0x93,0x95,0x96,0x97,0xa0,0xa1,0xa2,0xa3,0xa4,0xa5,0xa6,0xa7,0xa8,0xa9,0xaa,0xab,0xac,0xad,0xae,0xaf,0xb0,0xb1,0xb3,0xb4,0xc0,0xc1,0xc4,0xc5,0xc6,0xc7,*range(0xd0,0xd8)}
        while r.at<len(raw):
            start=r.at;op=r.byte();args=[]
            if 0x0c<=op<=0x1a:
                n=int.from_bytes(r.raw(3),'little');args=[n-(1<<24) if n&(1<<23) else n]
            elif op in single:args=[r.u30()]
            elif op in double:args=[r.u30(),r.u30()]
            elif op==0x24:
                n=r.byte();args=[n-256 if n&128 else n]
            elif op==0x65:args=[r.byte()]
            elif op==0xef:args=[r.byte(),r.u30(),r.byte(),r.u30()]
            elif op not in none:raise ValueError('Unreviewed binding helper opcode: '+hex(op))
            rows.append((start,r.at,op,args))
        return rows

    def semantic(self,row):
        b=row['value'];info=self.methods['rows'][b['method']]['value'];stack,regs,initial,maximum=b['frame']
        if b['exceptions'] or b['traits']['count'] or info['optional']:raise ValueError('Binding helper has exception/activation/optional dependencies.')
        text=str(info['flags'])+'|'+self.qname(info['ret'])+''.join('|'+self.qname(p) for p in info['params'])+'|'+str(regs)+'|'+str(stack)+'|'+str(maximum-initial)
        code=self.instructions(b['code']);addresses={x[0]:i for i,x in enumerate(code)};addresses[len(b['code'])]=len(code)
        multinames={0x04,0x05,0x45,0x46,0x4a,0x4c,0x4e,0x4f,0x59,0x5b,0x5c,0x5d,0x5e,0x5f,0x60,0x61,0x66,0x68,0x6a,0x80,0x86,0xb2}
        for start,end,op,args in code:
            text+='\n'+str(op)
            for n,value in enumerate(args):
                if 0x0c<=op<=0x1a:
                    if end+value not in addresses:raise ValueError('Binding helper branch is not an instruction boundary.')
                    token='@'+str(addresses[end+value])
                elif n==0 and op in multinames:token=self.qname(value)
                elif n==1 and op==0xef:token=self.string(value)
                elif n==0 and op==0xf1:token='owned-helper-source'
                elif n==0 and op==0x2c:token=self.string(value)
                elif n==0 and op in (0x2d,0x2e):
                    number=self.pool(op-0x2d,value)
                    if op==0x2d and number&0x80000000:number-=1<<32
                    token=str(number)
                elif n==0 and op==0x2f:raise ValueError('Reviewed binding helper has no double-pool operands.')
                else:token=str(value)
                text+=':'+token
        return text


def _abc_payload(swf):
    from cas_ui_build import tags,unpack
    rows=[r[3] for r in tags(unpack(swf)[1]) if r[0]==82]
    if len(rows)!=1:raise ValueError('Exactly one Main ABC is required.')
    payload=rows[0];boundary=payload.index(b'\0',4)+1
    return payload[:boundary],payload[boundary:]


def rollback_descriptor(baseline):
    _,data=_abc_payload(baseline);a=_ABC(data).parse();bodies={}
    for n in ('HandleAlignToContextMenu','ApexCatalogObserveBinding'):
        row=a.named(n)[2];bodies[n]=data[row['start']:row['end']].hex()
    return dict(pool_counts=[r['count'] for r in a.pools],bodies=bodies)


def reconstruct_previous(final_swf,proof):
    """Undo only two owned helpers and the exact native first-call projection."""
    from cas_ui_build import replace_payload
    prefix,data=_abc_payload(final_swf);a=_ABC(data).parse();descriptor=proof.get('rollback')
    if not isinstance(descriptor,dict) or set(descriptor)!={'pool_counts','bodies'}:raise ValueError('Binding rollback descriptor absent.')
    counts=descriptor['pool_counts'];old=descriptor['bodies']
    if not isinstance(counts,list) or len(counts)!=7 or not isinstance(old,dict) or set(old)!={'HandleAlignToContextMenu','ApexCatalogObserveBinding'}:
        raise ValueError('Binding rollback inventory differs.')
    patches=[]
    for pool,count in zip(a.pools,counts):
        if type(count) is not int or count<0 or count>pool['count']:raise ValueError('Binding constant-pool prefix differs.')
        end=pool['head'] if count<=1 else pool['rows'][count-2]['end']
        patches.append((pool['start'],pool['end'],attach._u30(count)+data[pool['head']:end]))
    main=a.named('HandleAlignToContextMenu')[0];traits=main['traits'];added=('ApexCatalogBindingWidth','ApexCatalogNativeBinding')
    original_methods=a.methods['count']-2
    if original_methods<0 or traits['count']<2 or a.bodies['count']<2:raise ValueError('Binding append inventory absent.')
    initial=None
    for i,name in enumerate(added):
        _,t,b=a.named(name)
        if(t!=traits['rows'][-2+i] or t['value']['method']!=original_methods+i or t['value']['flags']!=1 or
           t['value']['dispatch']!=0 or a.qname(t['value']['name'])!='7:'+name+':5:widgets.CAS.Customizer:CASCustomizerMain' or
           b!=a.bodies['rows'][-2+i]):raise ValueError('Binding helpers must be the two appended private methods.')
    old_rows={};raw_rows={}
    for name,value in old.items():
        if not isinstance(value,str) or len(value)>16384 or re.fullmatch('[0-9a-f]+',value) is None:raise ValueError('Binding old body is unbounded or invalid.')
        raw=bytes.fromhex(value);reader=_ABC(raw);parsed=reader.body()
        if reader.at!=len(raw) or parsed['method']!=a.named(name)[1]['value']['method']:raise ValueError('Binding old body targets another method.')
        old_rows[name]=parsed;raw_rows[name]=raw
    before=old_rows['HandleAlignToContextMenu'];after=a.named('HandleAlignToContextMenu')[2]['value'];native=before['code']
    if digest(native)!=NATIVE_SHA256 or before['exceptions'] or before['traits']['count']:raise ValueError('Original alignment authority differs.')
    qname=a.named('ApexCatalogNativeBinding')[1]['value']['name']
    expected=native[:77]+b'\xd1\x4f'+attach._u30(qname)+b'\x05'+native[81:]
    if after['code']!=expected or after['frame']!=(before['frame'][0]+1,)+before['frame'][1:] or after['exceptions'] or after['traits']['count']:
        raise ValueError('Only the exact first native binding call may change.')
    initial=old_rows['ApexCatalogObserveBinding']['frame'][2]
    for name,semantic in SEMANTICS.items():
        row=a.named(name)[2]
        if row['value']['frame'][2]!=initial or digest(a.semantic(row).encode())!=semantic:raise ValueError('Final binding helper semantic/lexical identity differs: '+name)
    native_bind=a.named('BindDisplayObjectToSim')[2]
    if digest(native_bind['value']['code'])!=NATIVE_BIND_SHA256:raise ValueError('Original native binding method differs.')
    table=a.methods;patches.append((table['start'],table['end'],attach._u30(original_methods)+data[table['head']:table['rows'][-2]['start']]))
    patches.append((traits['start'],traits['end'],attach._u30(traits['count']-2)+data[traits['head']:traits['rows'][-2]['start']]))
    replacements={a.named(name)[2]['value']['method']:value for name,value in raw_rows.items()}
    table=a.bodies;restored=attach._u30(table['count']-2)+b''.join(replacements.get(row['value']['method'],data[row['start']:row['end']]) for row in table['rows'][:-2])
    patches.append((table['start'],table['end'],restored))
    prior=len(data)
    for start,end,raw in sorted(patches,reverse=True):
        if end>prior or start>end:raise ValueError('Overlapping ABC rollback spans.')
        data=data[:start]+raw+data[end:];prior=start
    return replace_payload(final_swf,prefix+data)


def inject(original):
    if 'ApexCatalogNativeBinding' in original or 'ApexCatalogObserveBinding' in original:
        raise ValueError('Use the exact original donor Main source for the binding stub.')
    at=original.rfind('\n   }')
    if at<0:raise ValueError('Original Main class boundary missing.')
    return original[:at]+FIELDS+HELPERS+OBSERVER+original[at:]


def adapt(previous,baseline_swf,original_donor_source,ffdec,work):
    from cas_ui_build import tags,unpack,replace_payload
    baseline_swf=bytes(baseline_swf);ffdec=Path(ffdec);work=Path(work)
    if attach.verify_contract(previous,baseline_swf) is not True:
        raise ValueError('The full incoming Main/cell continuation is not verified.')
    pins={n:digest((ROOT/n).read_bytes()) for n in SOURCES};work.mkdir(parents=True,exist_ok=True)
    baseline=work/'baseline.swf';baseline.write_bytes(baseline_swf)
    source=work/'CASCustomizerMain.as';source.write_text(inject(Path(original_donor_source).read_text(encoding='utf-8-sig')),encoding='utf-8')
    compiled=work/'compiled.swf'
    comm.run([ffdec,'-importAssets','yes,local','-replace',baseline,compiled,TARGET,source],work/'ffdec.log')
    classes=work/'classes';classes.mkdir(exist_ok=True);jar=ffdec.with_name('ffdec.jar')
    comm.run(['javac','-cp',jar,'-d',classes,ROOT/'tools/CasStructuralRolesPatch.java',ROOT/'tools/CasCommunicationIndexPatch.java',ROOT/'tools/CasCatalogBindingPatch.java'],work/'javac.log')
    abc=work/'retained.abc';proof=work/'proof.json'
    comm.run(['java','-cp',str(jar)+os.pathsep+str(classes),'CasCatalogBindingPatch',baseline,compiled,abc,proof,
              ROOT/'.work/research/ClassLibraryGamedata.swf',ROOT/'.work/research/maru-integrated/DynamicCASGridLibrary.swf'],work/'transplant.log')
    report=json.loads(proof.read_text());data=abc.read_bytes()
    if report.get('ok') is not True or report.get('abc_sha256')!=digest(data):raise ValueError('Binding postpass output differs.')
    if pins!={n:digest((ROOT/n).read_bytes()) for n in SOURCES}:raise ValueError('Binding source changed during compilation.')
    report['source_sha256']=pins;report['helper_source_sha256']=digest((FIELDS+HELPERS+OBSERVER).encode())
    report['previous_stage_sha256']=comm.contract_digest(previous)
    report['rollback']=rollback_descriptor(baseline_swf)
    tag=next(t[3] for t in tags(unpack(baseline_swf)[1]) if t[0]==82)
    final=replace_payload(baseline_swf,tag[:tag.index(b'\0',4)+1]+data)
    return final,report


def chain_contract(previous,proof,final_swf):
    from cas_ui_build import tags,unpack
    if not isinstance(previous,dict) or not isinstance(proof,dict):raise ValueError('Binding continuation is absent.')
    required=('native_first_bind_only_verified','other_four_binds_retained','native_binding_body_retained',
              'native_cfg_projection_verified','listener_insertion_order_verified','exact_dispatch_payload_verified',
              'protected_namespace_bindings_verified','whole_abc_rollback_verified','all_other_bodies_retained')
    counts={'changed_native_bodies':1,'replaced_owned_bodies':1,'appended_methods':2,'appended_fields':0}
    if(proof.get('ok') is not True or proof.get('phase')!='single-native-catalogue-bind' or any(proof.get(n) is not True for n in required) or
       any(type(proof.get(n)) is not int or proof[n]!=v for n,v in counts.items()) or
       proof.get('baseline_native_align_sha256')!=NATIVE_SHA256 or proof.get('native_bind_sha256')!=NATIVE_BIND_SHA256 or
       proof.get('baseline_swf_sha256')!=previous.get('final_swf_sha256') or
       proof.get('previous_stage_sha256')!=comm.contract_digest(previous) or
       proof.get('source_sha256')!={n:digest((ROOT/n).read_bytes()) for n in SOURCES} or
       proof.get('helper_source_sha256')!=digest((FIELDS+HELPERS+OBSERVER).encode()) or
       proof.get('runtime_qualified') is not False or proof.get('performance_gain_claimed') is not False):
        raise ValueError('Binding postpass proof differs.')
    payloads=[t[3] for t in tags(unpack(final_swf)[1]) if t[0]==82]
    if len(payloads)!=1 or digest(payloads[0][payloads[0].index(b'\0',4)+1:])!=proof.get('abc_sha256'):
        raise ValueError('Binding final ABC differs.')
    reconstructed=reconstruct_previous(final_swf,proof)
    if digest(reconstructed)!=proof['baseline_swf_sha256'] or digest(_abc_payload(reconstructed)[1])!=proof.get('baseline_abc_sha256'):
        raise ValueError('Binding final cannot reconstruct its exact incoming Main.')
    if attach.verify_contract(previous,reconstructed) is not True:raise ValueError('Binding reconstructed Main fails the complete prior chain.')
    return dict(previous_stage_sha256=comm.contract_digest(previous),previous_stage_contract=json.loads(json.dumps(previous)),
                postproof_sha256=comm.contract_digest(proof),catalog_binding_contract=json.loads(json.dumps(proof)),final_swf_sha256=digest(final_swf))


def verify_contract(contract,final_swf):
    if not isinstance(contract,dict) or chain_contract(contract.get('previous_stage_contract'),contract.get('catalog_binding_contract'),final_swf)!=contract:
        raise ValueError('Binding complete continuation differs.')
    return True
