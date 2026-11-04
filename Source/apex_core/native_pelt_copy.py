"""Scope the inspected generator's Human-paint assignment to vanilla pairs.

The 1.128 generator explicitly copies Werewolf/Fairy paint into Human. Replace
that one balanced wordcode statement with a scoped call, preserving its other
instructions, jumps, defaults, aliases and existing wrappers. The permanent
appearance guards remain independent of this change.
"""
import dis
import hashlib
import opcode
import os
import sys
import types
import weakref

NATIVE_SHA = '1ac1d9af62bff2172a6d95d08e774e223eee0bf5513fac570a340ed7c5cc94b7'
NATIVE_NAMES = ('_sim_info_map','OccultType','HUMAN','OCCULT_DATA','generate_new_human_form_on_add',
    '_generate_sim_info','_create_new_sim_info_base_wrapper','_sim_info','_base','current_occult_types',
    'occult_types','_copy_trait_ids','generate_occult_siminfo','FAIRY','load_outfits','save_outfits',
    'OccultTracker','_get_occult_outfit_blacklist','REGULAR_OUTFIT_CATEGORIES',
    '_is_outfit_category_forbidden','generate_outfit','_copy_shared_attributes','WEREWOLF',
    'pelt_layers','_add_sim_info_to_map')
NATIVE_VARS = ('self','occult_type','generate_new','generate_new_human_form','preserve_skin_tone',
               'sim_info','outfit_category_blacklist','outfit_category')
NATIVE_CONSTS = (None,('generate_new',),('outfit_category',))
HELPER = '_apex_scoped_human_pelt_copy_v1'
MARKER = '_apex_native_pelt_copy_patch'
_CACHE = weakref.WeakKeyDictionary()
_PATTERN = (('LOAD_FAST','sim_info'),('LOAD_ATTR','pelt_layers'),('LOAD_FAST','self'),
    ('LOAD_ATTR','_sim_info_map'),('LOAD_GLOBAL','OccultType'),('LOAD_ATTR','HUMAN'),
    ('BINARY_SUBSCR',None),('STORE_ATTR','pelt_layers'))


def _native(code):
    return (hashlib.sha256(code.co_code).hexdigest()==NATIVE_SHA and code.co_names==NATIVE_NAMES and
        code.co_varnames==NATIVE_VARS and code.co_consts==NATIVE_CONSTS and
        code.co_argcount==3 and code.co_kwonlyargcount==0 and not code.co_freevars and not code.co_cellvars)


def _patched_code(code):
    if sys.version_info[:2]!=(3,7) or not _native(code):
        raise ValueError('Native pelt assignment requires the inspected Python 3.7 generator.')
    instructions=list(dis.get_instructions(code));matches=[]
    for index in range(len(instructions)-len(_PATTERN)+1):
        part=instructions[index:index+len(_PATTERN)]
        if all((item.opname,item.argval)==expected for item,expected in zip(part,_PATTERN)):
            matches.append(part)
    if len(matches)!=1:
        raise ValueError('Native Human-paint write is absent or ambiguous.')
    part=matches[0];start=part[0].offset;end=part[-1].offset+2
    if (end-start!=16 or any(item.offset!=start+2*i for i,item in enumerate(part)) or
            any(item.is_jump_target for item in part[1:]) or len(code.co_names)>255 or code.co_stacksize<3):
        raise ValueError('Native Human-paint statement has an unsupported control-flow layout.')
    pairs=[('LOAD_GLOBAL',len(code.co_names)),('LOAD_FAST',part[2].arg),('LOAD_FAST',part[0].arg),
           ('CALL_FUNCTION',2),('POP_TOP',0),('NOP',0),('NOP',0),('NOP',0)]
    replacement=bytes(value for name,arg in pairs for value in (opcode.opmap[name],arg))
    raw=code.co_code[:start]+replacement+code.co_code[end:]
    result=types.CodeType(code.co_argcount,code.co_kwonlyargcount,code.co_nlocals,code.co_stacksize,
        code.co_flags,raw,code.co_consts,code.co_names+(HELPER,),code.co_varnames,code.co_filename,
        code.co_name,code.co_firstlineno,code.co_lnotab,code.co_freevars,code.co_cellvars)
    if result.co_code[:start]!=code.co_code[:start] or result.co_code[end:]!=code.co_code[end:]:
        raise ValueError('Native pelt patch changed an unrelated instruction.')
    return result


def _independent(tracker):
    sim=getattr(tracker,'_sim_info',None)
    try:
        mask=int(sim.occult_types)
    except (AttributeError,TypeError,ValueError):
        return False
    others=mask&~1
    forms=getattr(tracker,'_sim_info_map',None)
    if (0<mask<=127 and others and others&(others-1) and
            isinstance(forms,dict) and forms.get(1) is not None):
        return True
    # A captured single-occult pair can also have an independent shared Human.
    # This is an in-process capability, not a bank lookup or a saved-profile guess.
    module=sys.modules.get('apex_core.native_cas_engine')
    scope=getattr(module,'_LAYOUT_SCOPE',None)
    sid=str(getattr(sim,'id',''))
    if not isinstance(scope,dict) or scope.get('pid')!=os.getpid():return False
    binding=scope.get('logical_owners',{}).get(sid,{})
    human=binding.get('human_owner_id')
    return (human in ('native/1','active/1') and binding.get('logical_owner_ids',{}).get('1')==human and
            (sid,human) in scope.get('owners',{}))


def _policy(native_globals):
    def copy_human_pelt(tracker,generated):
        enums=native_globals['OccultType']
        try:qualified=(int(enums.HUMAN)==1 and int(enums.WEREWOLF)==32 and int(enums.FAIRY)==64)
        except (AttributeError,TypeError,ValueError):qualified=False
        suppress=qualified and _independent(tracker)
        if not suppress:
            # Preserve the original getter/lookup/setter order for ordinary Sims.
            value=generated.pelt_layers
            tracker._sim_info_map[enums.HUMAN].pelt_layers=value
        previous=getattr(tracker,'_apex_native_pelt_policy',{})
        count=previous.get('calls',0) if isinstance(previous,dict) else 0
        count=count if type(count) is int and 0<=count<2147483647 else 0
        tracker._apex_native_pelt_policy=dict(calls=count+1,human_write_suppressed=bool(suppress),
            native_default_copy_called=not suppress,bank_read=False,appearance_restored=False)
    return copy_human_pelt


def _functions(root):
    pending=[root];seen=set()
    while pending:
        item=pending.pop()
        if isinstance(item,types.MethodType):item=item.__func__
        if not isinstance(item,types.FunctionType) or id(item) in seen:continue
        seen.add(id(item))
        if len(seen)>32:raise ValueError('Native generator wrapper chain exceeds its inspection bound.')
        yield item
        pending.extend(value for value in item.__dict__.values() if isinstance(value,(types.FunctionType,types.MethodType)))
        pending.extend(item.__defaults__ or ())
        pending.extend((item.__kwdefaults__ or {}).values())
        for cell in item.__closure__ or ():
            try:pending.append(cell.cell_contents)
            except ValueError:pass


def install(cls):
    root=getattr(cls,'_generate_sim_info',None)
    cached=_CACHE.get(cls)
    if cached and cached[0] is root:
        target,code,helper=cached[1:4]
        if target.__code__ is code and target.__globals__.get(HELPER) is helper:
            return dict(cached[4])
    try:
        if sys.version_info[:2]!=(3,7):raise ValueError('Inspected game Python 3.7 required.')
        candidates=[fn for fn in _functions(root) if _native(fn.__code__) or getattr(fn,MARKER,None)]
        if len(candidates)!=1:raise ValueError('One exact native generator is required through the existing wrappers.')
        target=candidates[0];marked=getattr(target,MARKER,None)
        if marked:
            if target.__code__ is not marked['code'] or target.__globals__.get(HELPER) is not marked['helper']:
                raise ValueError('Previously installed native pelt routing changed; no foreign patch overwritten.')
            code,helper=marked['code'],marked['helper']
        else:
            if HELPER in target.__globals__:raise ValueError('Native pelt helper name is already occupied.')
            code=_patched_code(target.__code__);helper=_policy(target.__globals__)
            target.__globals__[HELPER]=helper
            try:target.__code__=code
            except Exception:
                del target.__globals__[HELPER]
                raise
            setattr(target,MARKER,dict(code=code,helper=helper))
        receipt=dict(installed=True,native_code_sha256=NATIVE_SHA,write_sites_replaced=1,
            other_instructions_preserved=True,existing_wrappers_preserved=True,
            scope='hybrid-or-captured-independent-owner',permanent_guard_retained=True)
        _CACHE[cls]=(root,target,code,helper,receipt)
        return dict(receipt)
    except (ValueError,TypeError,AttributeError,KeyError) as error:
        return dict(installed=False,reason=str(error)[:512],permanent_guard_retained=True)
