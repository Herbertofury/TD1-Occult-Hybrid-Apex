"""Exact final-Main postpass deleting only a dead donor half-scale write."""
import hashlib
import json
import os
from pathlib import Path

import cas_communication_index as comm

ROOT=Path(__file__).resolve().parents[1]
SOURCES=('tools/cas_cell_attach.py','tools/CasCellAttachPatch.java','tools/CasStructuralRolesPatch.java')
DONOR='c97afa8f0362a0452b359074769b9c99174444dd211927d08972091db3391969'
CONFIG_UI_SHA256='266769576ea606d8b6ad4096be8341bb6c7ff9dd05ac4f18ec73e94a220bf5fd'
EDITED_CONFIG_UI_SHA256='2577d3fdffeb9aa8af07fa45b2cf6b83cbefcd0adc4b0c21c8c27712e7aca779'
CONFIG_UI_CODE=bytes.fromhex(
    'd030d04efc1100d0d066e50666d91768e606d0d066e50666da1768e706d0d066e70666951268ec06d026618b13d066fc0527618212d066eb142cb91761db13'
    'd066cc05120a0000d0d066cc0566db176860d066e106d066e106272ad7618b13d3080361fa15d066e00627618212d066e206d066e206272ad7618b13d3080361fa15d066e40627618212'
    'd066e4066004668612d066f406272400264f891205d066e406600466aa12d066f206272400264f891205d066e40666dc17809b03d5d160c01466c11461c214d160ec0a66d01161dc14d160ec0a66d11161c414'
    'd066e8062761fa15d066e80660e71266dd17618212d06686068019d6d227618212d2600d66aa12d066f106272400264f891205d226618f13d266eb142cbc1761db13'
    'd024012402a361d413d0604966bc1c61d413d0604966bc1c61d31362002661a41dd0600d66aa12d066a51d272564264f89120547')


class _ABCReader:
    """Strict structural walk to code vectors; never interpret arbitrary code."""
    def __init__(self,data):self.data=data;self.at=0
    def raw(self,count):
        if count<0 or self.at+count>len(self.data):raise ValueError('Truncated ABC structure.')
        value=self.data[self.at:self.at+count];self.at+=count;return value
    def byte(self):return self.raw(1)[0]
    def uint(self):
        value=0
        for shift in range(0,35,7):
            part=self.byte()
            if shift==28 and part&0xf0:raise ValueError('Invalid ABC variable integer.')
            value|=(part&127)<<shift
            if not part&128:return value
        raise ValueError('Invalid ABC variable integer.')
    def u30(self):
        value=self.uint()
        if value>0x3fffffff:raise ValueError('Invalid ABC u30.')
        return value
    def count(self):
        value=self.u30()
        if value>len(self.data):raise ValueError('Unbounded ABC structure count.')
        return value
    def traits(self):
        for _ in range(self.count()):
            self.u30();flags=self.byte();kind=flags&15
            if kind in(0,6):
                self.u30();self.u30();value=self.u30()
                if value:self.byte()
            elif kind in(1,2,3,4,5):self.u30();self.u30()
            else:raise ValueError('Unknown ABC trait kind.')
            if flags&64:
                for _ in range(self.count()):self.u30()
    def code_vectors(self):
        self.raw(4)
        for _ in range(2):
            for _ in range(max(0,self.count()-1)):self.uint()
        self.raw(max(0,self.count()-1)*8)
        for _ in range(max(0,self.count()-1)):self.raw(self.count())
        for _ in range(max(0,self.count()-1)):self.byte();self.u30()
        for _ in range(max(0,self.count()-1)):
            for _ in range(self.count()):self.u30()
        for _ in range(max(0,self.count()-1)):
            kind=self.byte()
            if kind in(7,13,9,14):self.u30();self.u30()
            elif kind in(15,16,27,28):self.u30()
            elif kind in(17,18):pass
            elif kind==29:
                self.u30()
                for _ in range(self.count()):self.u30()
            else:raise ValueError('Unknown ABC multiname kind.')
        for _ in range(self.count()):
            parameters=self.count();self.u30()
            for _ in range(parameters):self.u30()
            self.u30();flags=self.byte()
            if flags&8:
                for _ in range(self.count()):self.u30();self.byte()
            if flags&128:
                for _ in range(parameters):self.u30()
        for _ in range(self.count()):
            self.u30()
            for _ in range(self.count()*2):self.u30()
        classes=self.count()
        for _ in range(classes):
            self.u30();self.u30();flags=self.byte()
            if flags&8:self.u30()
            for _ in range(self.count()):self.u30()
            self.u30();self.traits()
        for _ in range(classes):self.u30();self.traits()
        for _ in range(self.count()):self.u30();self.traits()
        vectors=[]
        for _ in range(self.count()):
            method=self.u30();frame=tuple(self.u30()for _ in range(4));length_at=self.at;length=self.u30();code_at=self.at;code=self.raw(length);code_end=self.at
            exceptions=self.count()
            for _ in range(exceptions):
                for _ in range(5):self.u30()
            self.traits();vectors.append(dict(method=method,frame=frame,length_at=length_at,code_at=code_at,code_end=code_end,code=code,exceptions=exceptions))
        if self.at!=len(self.data):raise ValueError('Trailing ABC data.')
        return vectors


def _u30(value):
    output=bytearray()
    while True:
        part=value&127;value>>=7;output.append(part|(128 if value else 0))
        if not value:return bytes(output)


def reconstruct_previous(final_swf):
    """Undo only the exact native deletion, then qualify old full Draw proof."""
    from cas_ui_build import tags,unpack,replace_payload
    if digest(CONFIG_UI_CODE)!=CONFIG_UI_SHA256:raise ValueError('Pinned original ConfigUI authority differs.')
    values=[t[3]for t in tags(unpack(final_swf)[1])if t[0]==82]
    if len(values)!=1:raise ValueError('Exactly one Main ABC is required.')
    payload=values[0];boundary=payload.index(b'\0',4)+1;abc=payload[boundary:]
    matches=[row for row in _ABCReader(abc).code_vectors()if digest(row['code'])==EDITED_CONFIG_UI_SHA256]
    if len(matches)!=1:raise ValueError('Exact unique edited ConfigUI body is absent.')
    row=matches[0]
    if row['exceptions']!=0:raise ValueError('Edited ConfigUI exception inventory differs.')
    previous=abc[:row['length_at']]+_u30(len(CONFIG_UI_CODE))+CONFIG_UI_CODE+abc[row['code_end']:]
    return replace_payload(final_swf,payload[:boundary]+previous)


def digest(data):return hashlib.sha256(data).hexdigest()


def previous(base,structural,fast):
    import cas_draw_fast_path as draw
    import cas_structural_roles as roles
    draw.validate_contract(fast)
    if (structural.get('ok')is not True or structural.get('donor_swf_sha256')!=DONOR or
        structural.get('serialized_whole_abc_rollback_projection')is not True or structural.get('main_and_height_preserved')is not True or
        structural.get('base_contract_sha256')!=draw.contract_digest(base) or fast.get('base_contract_sha256')!=draw.contract_digest(base) or
        fast.get('structural_contract_sha256')!=draw.contract_digest(structural) or fast.get('baseline_abc_sha256')!=structural.get('abc_sha256') or
        fast.get('baseline_swf_sha256')!=structural.get('final_swf_sha256') or fast.get('baseline_draw_sha256')!=structural.get('draw_sha256') or
        structural.get('source_sha256')!={n:digest((ROOT/n).read_bytes())for n in('tools/CasStructuralRolesPatch.java','tools/cas_structural_roles.py')}or
        structural.get('private_source_sha256')!=roles.PRIVATE_SOURCE_PINS or fast.get('source_sha256')!={n:digest((ROOT/n).read_bytes())for n in draw.SOURCES}):
        raise ValueError('Cell attach requires the authenticated prior structural/Draw chain.')
    return dict(native_bytecode_contract=json.loads(json.dumps(base)),structural_roles_native_bytecode_contract=json.loads(json.dumps(structural)),
                draw_fast_path_native_bytecode_contract=json.loads(json.dumps(fast)))


def adapt(original_donor,base,structural,fast,baseline_swf,ffdec_jar,work):
    original_donor,ffdec_jar,work=map(Path,(original_donor,ffdec_jar,work));prior=previous(base,structural,fast)
    import cas_draw_fast_path as draw
    if digest(original_donor.read_bytes())!=DONOR or digest(baseline_swf)!=fast.get('final_swf_sha256')or digest(draw.abc_payload(baseline_swf))!=fast.get('abc_sha256'):
        raise ValueError('Cell attach baseline bytes differ from original donor/final Draw identity.')
    if draw.chain_contract(base,structural,fast,baseline_swf)!=fast:
        raise ValueError('Cell attach must pass the complete existing final Draw verifier before mutation.')
    pins={n:digest((ROOT/n).read_bytes())for n in SOURCES};work.mkdir(parents=True,exist_ok=True);incoming=work/'baseline.swf';incoming.write_bytes(baseline_swf);classes=work/'classes';classes.mkdir(exist_ok=True)
    comm.run(['javac','-cp',ffdec_jar,'-d',classes,ROOT/'tools/CasStructuralRolesPatch.java',ROOT/'tools/CasCellAttachPatch.java'],work/'javac.log')
    abc,proof=work/'retained.abc',work/'proof.json'
    comm.run(['java','-cp',str(ffdec_jar)+os.pathsep+str(classes),'CasCellAttachPatch',original_donor,incoming,digest(baseline_swf),fast['abc_sha256'],abc,proof],work/'transplant.log')
    data=abc.read_bytes();report=json.loads(proof.read_text())
    if report.get('ok')is not True or report.get('abc_sha256')!=digest(data):raise ValueError('Cell attach postpass identity differs.')
    if pins!={n:digest((ROOT/n).read_bytes())for n in SOURCES}:raise ValueError('Cell attach source changed during compilation; discard output.')
    report['source_sha256']=pins;report['previous_chain_sha256']=comm.contract_digest(prior);return data,report


def chain_contract(base,structural,fast,postproof,final_swf):
    prior=previous(base,structural,fast)
    import cas_draw_fast_path as draw
    required=('dead_immediate_overwrite_verified','authoritative_static_slot_verified','final_xy_writes_retained','rightclick_favorite_body_retained',
              'native_cfg_projection_verified','whole_abc_rollback_verified','all_other_methods_retained')
    counts={'edited_existing_methods':1,'removed_instructions':5,'appended_methods':0,'appended_traits':0,'appended_pool_entries':0}
    if(not isinstance(postproof,dict)or postproof.get('ok')is not True or any(postproof.get(n)is not True for n in required)or
        any(type(postproof.get(name)) is not int or postproof[name]!=value for name,value in counts.items())or
        postproof.get('phase')!='dead-cell-attach-scale-write'or postproof.get('donor_swf_sha256')!=DONOR or
        postproof.get('baseline_swf_sha256')!=fast.get('final_swf_sha256')or postproof.get('baseline_abc_sha256')!=fast.get('abc_sha256')or
        postproof.get('previous_chain_sha256')!=comm.contract_digest(prior) or postproof.get('edited_existing_methods')!=1 or
        postproof.get('removed_instructions')!=5 or postproof.get('appended_methods')!=0 or postproof.get('appended_traits')!=0 or postproof.get('appended_pool_entries')!=0 or
        postproof.get('runtime_qualified')is not False or postproof.get('performance_gain_claimed')is not False):raise ValueError('Dead attach-write contract differs.')
    if postproof.get('source_sha256')!={n:digest((ROOT/n).read_bytes())for n in SOURCES}:raise ValueError('Cell attach source pins differ.')
    if digest(draw.abc_payload(final_swf))!=postproof.get('abc_sha256'):raise ValueError('Final Main ABC does not contain authenticated dead-write deletion.')
    if postproof.get('baseline_config_ui_sha256')!=CONFIG_UI_SHA256 or postproof.get('config_ui_sha256')!=EDITED_CONFIG_UI_SHA256:
        raise ValueError('Exact ConfigUI authority differs.')
    reconstructed=reconstruct_previous(final_swf)
    if digest(reconstructed)!=fast.get('final_swf_sha256') or digest(draw.abc_payload(reconstructed))!=fast.get('abc_sha256'):
        raise ValueError('Final Main cannot reconstruct its exact historical Draw stage.')
    if draw.chain_contract(base,structural,fast,reconstructed)!=fast:
        raise ValueError('Reconstructed Main fails the complete historical Draw verifier.')
    return dict(previous_chain_sha256=comm.contract_digest(prior),previous_chain=prior,postproof_sha256=comm.contract_digest(postproof),
                cell_attach_contract=json.loads(json.dumps(postproof)),final_swf_sha256=digest(final_swf))


def verify_contract(contract,final_swf):
    if not isinstance(contract,dict)or not isinstance(contract.get('previous_chain'),dict):raise ValueError('Cell attach history absent.')
    p=contract['previous_chain']
    if chain_contract(p.get('native_bytecode_contract',{}),p.get('structural_roles_native_bytecode_contract',{}),p.get('draw_fast_path_native_bytecode_contract',{}),contract.get('cell_attach_contract'),final_swf)!=contract:
        raise ValueError('Cell attach final chain differs.')
    return True
