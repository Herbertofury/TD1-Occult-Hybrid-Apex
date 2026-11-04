"""Finish accepted CAS owners at data boundaries, never from menu predicates.

The permission is the current native household acceptance plus the held
frontdoor/checkpoint capability. Appearance differences never supply intent.
No timer, speed change, UI input, old-process recovery or native save is added.
"""
import copy
import json
import os
from pathlib import Path
import threading

from . import cas_bank_transaction as bank, cas_commit_plan as primitive
from . import form_appearance as appearance, form_bank, native_cas_engine
from .overlay_loader import _unlinked


class _AcceptedReturn:
    pass


def _native_status(backend):
    from . import overlay_loader
    import paths
    return overlay_loader.native_cas_engine_control(backend.__file__, paths.DLL_PATH, {'operation':'status'})


def _frontdoor(backend):
    receipt=getattr(backend,'_APEX_CAS_FRONTDOOR_RECEIPT',None)
    token=receipt.get('id') if isinstance(receipt,dict) else None
    if (not isinstance(token,str) or len(token)!=32 or any(c not in '0123456789abcdef' for c in token) or
            receipt.get('stage')!='native-command-returned'):
        raise ValueError('Automatic preservation needs the exact completed CAS frontdoor.')
    path=_unlinked(Path(backend._data_directory())/('cas_frontdoor_'+token+'.json'))
    with path.open('rb') as stream:raw=stream.read(4*1024*1024+1)
    if len(raw)>4*1024*1024 or json.loads(raw.decode('utf-8'),object_pairs_hook=bank._pairs)!=receipt:
        raise ValueError('The complete durable CAS frontdoor changed.')
    return receipt


def _live(backend):
    bank._thread(backend)
    services=backend.services;zone=services.current_zone();household=services.active_household()
    if zone is None or zone.is_zone_running is not True or zone.is_in_build_buy is not False or household is None:
        raise ValueError('Automatic preservation is waiting for the running Live household.')
    roster=list(household.sim_info_gen())
    if not 1<=len(roster)<=8 or len({str(sim.id) for sim in roster})!=len(roster):
        raise ValueError('The current household roster is ambiguous.')
    for sim in roster:
        if sim.household_id!=household.id or backend._get_sim_info_by_id(str(sim.id)) is not sim:
            raise ValueError('Automatic preservation lost a manager-owned household member.')
    from . import cas_ui
    diagnostic=cas_ui.diagnostics()
    if diagnostic.get('native_peers')!=[]:
        raise ValueError('Native CAS still owns its editor; no automatic write is permitted.')
    return household,{str(sim.id):sim for sim in roster}


def _proof(backend,scope):
    if (scope is not native_cas_engine._LAYOUT_SCOPE or not isinstance(scope,dict) or
            scope.get('pid')!=os.getpid() or not isinstance(scope.get('epochs'),dict) or
            not 1<=len(scope['epochs'])<=8 or scope.get('retirement_attempted')):
        raise ValueError('Automatic preservation has no current held native CAS scope.')
    value=_native_status(backend);proof=value.get('household_acceptance')
    generations=proof.get('generations') if isinstance(proof,dict) else None
    cancelled=isinstance(proof,dict) and proof.get('cancelled') is True
    intent_ready=(isinstance(proof,dict) and proof.get('verified') is True and proof.get('native_accepted') is True)
    if cancelled:
        intent_ready=(proof.get('cancel_started') is True and proof.get('cancel_completed') is True and
            proof.get('native_handled') is True and proof.get('runtime_pid')==os.getpid() and
            type(proof.get('session')) is int and proof['session']==value.get('sessions_retired') and
            type(proof.get('cancel_serial')) is int and 0<proof['cancel_serial']<2**64 and
            isinstance(proof.get('member_ids'),list) and len(proof['member_ids'])==len(scope['epochs']) and
            set(proof['member_ids'])==set(scope['epochs']))
    if (value.get('ok') is not True or value.get('pid')!=os.getpid() or value.get('scope_id')!=scope.get('scope_id') or
            value.get('selection_enabled') is not True or not isinstance(proof,dict) or
            not intent_ready or
            proof.get('scope_id')!=scope['scope_id'] or not isinstance(generations,dict) or
            set(generations)!=set(scope['epochs']) or any(type(g) is not int or not 0<g<2**64 for g in generations.values())):
        raise ValueError('The native CAS acceptance is incomplete or uncertain; edited owners remain retained.')
    members=value.get('members')
    if not isinstance(members,list) or len(members)!=len(generations):
        raise ValueError('Native acceptance omitted a captured household member.')
    found={}
    for row in members:
        sid=row.get('sim_id') if isinstance(row,dict) else None
        if (sid not in generations or sid in found or row.get('native_view_fault') is not False or
                row.get('graph_generation')!=generations[sid]):
            raise ValueError('A captured native owner changed after CAS acceptance.')
        found[sid]=row
    result=dict(runtime_pid=os.getpid(),scope_id=scope['scope_id'],generations=copy.deepcopy(generations),
        intent='cancel' if cancelled else 'accept')
    if cancelled:result.update(session=proof['session'],cancel_serial=proof['cancel_serial'],native_handled=True)
    return result


def require_member(backend,sim,capability):
    """Internal capability check; JSON cannot construct or rehydrate this object."""
    if (type(capability) is not _AcceptedReturn or capability.backend is not backend or
            getattr(backend,'_APEX_CAS_AUTO_CAPABILITY',None) is not capability or
            capability.members.get(str(sim.id)) is not sim):
        raise ValueError('Automatic CAS intent lacks its held receiver capability.')
    household,roster=_live(backend)
    receipt=_frontdoor(backend)
    if (set(roster)!=set(capability.roster) or any(roster[sid] is not old for sid,old in capability.roster.items()) or
            household.id!=capability.household_id or
            receipt!=capability.frontdoor or _proof(backend,capability.scope)!=capability.proof):
        raise ValueError('The accepted household/save/frontdoor changed before preservation.')
    if bank._identity(backend,sim)!=capability.identities[str(sim.id)]:
        raise ValueError('Automatic CAS preservation changed runtime/household/save identity.')
    return copy.deepcopy(capability.witness)


def _capture(backend,pending_ids):
    household,roster=_live(backend);receipt=_frontdoor(backend);scope=native_cas_engine._LAYOUT_SCOPE
    proof=_proof(backend,scope);members=receipt.get('members');identity=scope.get('load_identity')
    if (receipt.get('household_id')!=str(household.id) or sorted(receipt.get('roster_sim_ids',[]),key=int)!=sorted(roster,key=int) or
            not isinstance(identity,dict) or identity.get('household_id')!=str(household.id) or
            identity.get('save_guid')!=str(backend.services.get_persistence_service().get_save_slot_proto_guid()) or
            not isinstance(members,list) or len(members)!=len(scope['epochs'])):
        raise ValueError('Automatic CAS acceptance lacks its exact captured household/save roster.')
    checkpoints={}
    for row in members:
        sid=row.get('sim_id') if isinstance(row,dict) else None
        checkpoint=row.get('checkpoint') if isinstance(row,dict) else None
        if (sid not in roster or sid in checkpoints or not isinstance(checkpoint,dict) or checkpoint.get('ok') is not True or
                checkpoint.get('expected_pending_sha256')!=scope['epochs'].get(sid)):
            raise ValueError('A household member lost its exact frontdoor checkpoint.')
        checkpoints[sid]=checkpoint
    if set(checkpoints)!=set(scope['epochs']) or set(pending_ids)-set(checkpoints):
        raise ValueError('Unrelated or unloaded pending owners cannot be resolved by this CAS acceptance.')
    cap=_AcceptedReturn();cap.backend=backend;cap.scope=scope;cap.proof=proof;cap.frontdoor=copy.deepcopy(receipt)
    cap.roster=roster;cap.household_id=household.id;cap.members={sid:roster[sid] for sid in checkpoints};cap.identities={}
    cap.witness=dict(proof,frontdoor_id=receipt['id'],household_id=str(household.id),save_guid=identity['save_guid'],
        captured_sim_ids=sorted(checkpoints,key=int))
    for sid,sim in cap.members.items():
        current=bank._identity(backend,sim);path,key,record,transaction=bank._selected(backend,sim,allow_consumed=True)
        held=bank._CAPTURED.get(bank._cache_key(path,key,transaction['transaction_id']))
        if (transaction['transaction_sha256']!=scope['epochs'][sid] or transaction['identity']!=current or
                held is None or held['backend'] is not backend or held['identity']!=current):
            raise ValueError('A member has no current-process checkpoint receiver; no replay is authorized.')
        phase=bank.status(backend,sim).get('phase')
        if not bank._completed(transaction) and phase not in ('captured','observed'):
            raise ValueError('An existing planned, failed or uncertain transaction cannot be automatically replaced.')
        cap.identities[sid]=current
        if proof['intent']=='cancel':
            pending=record.get('pending')
            original=pending.get('original_owners') if isinstance(pending,dict) else None
            raw=primitive.read_owners(backend,sim,lambda:bank._identity(backend,sim))
            if (not isinstance(original,dict) or raw['active']['lane']!=original['active']['lane'] or
                    set(raw['stored'])!=set(original['stored']) or
                    any(appearance.fingerprint(raw['stored'][lane])!=appearance.fingerprint(fields)
                        for lane,fields in original['stored'].items()) or
                    appearance.fingerprint(raw['active']['fields'])!=appearance.fingerprint(original['active']['fields'])):
                raise ValueError('Completed CAS cancellation does not match fresh Live originals; later edits are not overwritten.')
    return cap


def _same_raw(actual,expected):
    return (actual['identity']==expected['identity'] and actual['active']['lane']==expected['active']['lane'] and
        set(actual['stored'])==set(expected['stored']) and
        all(appearance.fingerprint(actual['stored'][lane])==appearance.fingerprint(fields)
            for lane,fields in expected['stored'].items()) and
        appearance.fingerprint(actual['active']['fields'])==appearance.fingerprint(expected['active']['fields']))


def note_native_ready(backend,tracker):
    """Memory-only return witness after the existing complete native-ready guard.

    An ordinary load cannot authorize a CAS return. This never observes a bank
    transaction, serializes a Sim, restores appearance or schedules more work.
    The first physical return is immutable; a later ready callback cannot turn
    newer Live edits into the original return. All later reads remain fresh.
    """
    scope=native_cas_engine._LAYOUT_SCOPE
    if not isinstance(scope,dict):return dict(state='not-applicable',appearance_written=False)
    try:
        bank._thread(backend);sim=tracker.sim_info;sid=str(sim.id)
        if (getattr(tracker,'_apex_native_load_pending',False) is not True or sim.occult_tracker is not tracker or
                getattr(tracker,'_apex_native_load_appearance_retention',{}).get('verified') is not True or
                backend._get_sim_info_by_id(sid) is not sim or sid not in scope.get('epochs',{})):
            raise ValueError('Native-ready return lacks its exact guarded manager-owned receiver.')
        proof=_proof(backend,scope);receipt=_frontdoor(backend);identity=bank._identity(backend,sim)
        if receipt.get('household_id')!=identity['household_id']:
            raise ValueError('Native-ready return changed the captured household.')
        members=receipt.get('members',[])
        if not any(isinstance(r,dict) and r.get('sim_id')==sid and
                r.get('checkpoint',{}).get('expected_pending_sha256')==scope['epochs'][sid] for r in members):
            raise ValueError('Native-ready return lost its exact frontdoor checkpoint.')
        existing=getattr(backend,'_APEX_CAS_NATIVE_READY_WITNESS',None)
        if not isinstance(existing,dict) or existing.get('scope') is not scope:
            existing=dict(scope=scope,proof=copy.deepcopy(proof),frontdoor=copy.deepcopy(receipt),members={})
            backend._APEX_CAS_NATIVE_READY_WITNESS=existing
        if existing['proof']!=proof or existing['frontdoor']!=receipt:
            raise ValueError('The native-ready return scope changed; its earlier physical evidence stays retained.')
        if sid in existing['members']:return dict(state='already-retained',sim_id=sid,appearance_written=False)
        physical=primitive.read_owners(backend,sim,lambda:bank._identity(backend,sim))
        if _proof(backend,scope)!=proof or _frontdoor(backend)!=receipt or bank._identity(backend,sim)!=identity:
            raise ValueError('The native-ready return changed during its complete physical read.')
        existing['members'][sid]=dict(sim=sim,identity=copy.deepcopy(identity),physical=copy.deepcopy(physical))
        return dict(state='retained',sim_id=sid,appearance_written=False,native_save_requested=False)
    except Exception as error:
        return dict(state='unavailable',error=str(error)[:2048],appearance_written=False,native_save_requested=False)


def _fresh_accepted_physical(backend,sim,cap,returned):
    """Never overwrite a later Live edit with an older accepted native graph."""
    sid=str(sim.id);actual=primitive.read_owners(backend,sim,lambda:bank._identity(backend,sim))
    held=getattr(backend,'_APEX_CAS_NATIVE_READY_WITNESS',None)
    if isinstance(held,dict) and held.get('scope') is cap.scope and sid in held.get('members',{}):
        witness=held['members'][sid]
        if (held.get('proof')!=cap.proof or held.get('frontdoor')!=cap.frontdoor or witness.get('sim') is not sim or
                witness.get('identity')!=cap.identities[sid] or not _same_raw(actual,witness['physical'])):
            raise ValueError('Live appearance changed after the witnessed CAS return; newer edits remain retained.')
    else:
        # Without a completed post-return witness, only an already exact native
        # projection is safe. A difference cannot tell EA damage from a later
        # intentional Live/F11/MCCC edit, so no inferred repair is permitted.
        from .cas_native_return import project
        if not _same_raw(actual,project(returned,actual,cap.scope['epochs'][sid])):
            raise ValueError('No physical CAS-return witness distinguishes these Live edits from older native choices.')
    return actual


def _retain_failure(backend,cap,error):
    """Keep all completed/unfinished records protected after a group failure."""
    path,key=form_bank.context(backend,next(iter(cap.members.values())))
    data=form_bank.load(path)
    for sid in cap.members:
        record=data['records'].get(cap.witness['save_guid']+':'+sid)
        if not isinstance(record,dict):raise ValueError('A failed preservation group lost a durable member.')
        record['automatic_cas_preservation_failure']=dict(schema=1,state='recovery-required',
            witness=copy.deepcopy(cap.witness),error=str(error)[:2048],automatic_replay_allowed=False)
    form_bank.save(path,data)


def settle(backend):
    """One synchronous accepted-household completion at a real data boundary."""
    from . import cas_save_boundary
    state=cas_save_boundary.admission(backend)
    if not state['locked']:return dict(ok=True,state='idle',members=[],appearance_written=False)
    if getattr(backend,'_APEX_CAS_AUTO_SETTLEMENT_BUSY',False):
        return dict(ok=False,state='busy',members=[],appearance_written=False)
    previous=getattr(backend,'_APEX_CAS_AUTO_SETTLEMENT',{})
    if isinstance(previous,dict) and previous.get('unresolved') is True:
        return dict(previous,ok=False,replayed=False)
    cap=None;started=False;receipts=[];backend._APEX_CAS_AUTO_SETTLEMENT_BUSY=True
    try:
        cap=_capture(backend,state['pending_sim_ids']);backend._APEX_CAS_AUTO_CAPABILITY=cap
        # Validate/export every final graph before the first observation/write.
        for sid,sim in cap.members.items():
            require_member(backend,sim,cap)
            returned=native_cas_engine.returned_owners(backend,sim,cap.scope['epochs'][sid])
            if returned is None or returned['identity']['generation']!=cap.proof['generations'][sid]:
                raise ValueError('The accepted native owner export is incomplete.')
            if cap.proof['intent']=='accept':_fresh_accepted_physical(backend,sim,cap,returned)
        # Observe and plan the whole captured household before any commit.
        for sid,sim in cap.members.items():
            require_member(backend,sim,cap);status=bank.status(backend,sim)
            if status.get('completed_receipt') is True:continue
            started=True
            if status['phase']=='captured':bank.observe(backend,sim,{'expected_pending_sha256':cap.scope['epochs'][sid]})
            planned=bank.prepare_native_accepted(backend,sim,cap)
            receipts.append((sid,sim,planned))
        for sid,sim,planned in receipts:
            require_member(backend,sim,cap)
            receipt=bank.commit_native_accepted(backend,sim,{'expected_pending_sha256':cap.scope['epochs'][sid],
                'expected_plan_sha256':planned['plan_sha256']},cap)
            if receipt.get('bank_committed') is not True:raise ValueError('A member completion was not durably acknowledged.')
        # A later member's serializer/setter must not damage an earlier member.
        for sid,sim in cap.members.items():
            _identity,path,key,data,_sha,record=bank._context(backend,sim)
            transaction=record.get('cas_transaction')
            if bank._blocked(record,key):raise ValueError('A captured member remains unresolved after automatic completion.')
            actual=primitive.read_owners(backend,sim,lambda:bank._identity(backend,sim))
            desired=transaction['journal']['plan']['desired']
            if (actual['active']['lane']!=transaction['journal']['plan']['active_lane'] or set(actual['stored'])!=set(desired) or
                    any(appearance.fingerprint(actual['stored'][lane])!=appearance.fingerprint(fields) for lane,fields in desired.items()) or
                    appearance.fingerprint(actual['active']['fields'])!=appearance.fingerprint(desired[actual['active']['lane']])):
                raise ValueError('Final household preservation differs after another member completed.')
        if cas_save_boundary.admission(backend)['locked']:raise ValueError('Other pending owners still require authenticated preservation.')
        retirement=[]
        for sid,sim in cap.members.items():
            _p,_k,_record,transaction=bank._selected(backend,sim,allow_consumed=True)
            try:retirement.append(native_cas_engine.complete_return(backend,sim,transaction))
            except Exception as error:
                # This releases a verified graph; it is not a native appearance
                # write and must never cause the completed transactions to replay.
                retirement.append(dict(ok=False,retired=False,error=str(error)[:2048],appearance_replay_authorized=False))
        result=dict(ok=True,state='completed',members=sorted(cap.members,key=int),witness=cap.witness,
            user_review_required=False,native_save_requested=False,save_reload_verified=False,unresolved=False,
            native_retirement=retirement)
        backend._APEX_CAS_AUTO_SETTLEMENT=result;return result
    except Exception as error:
        result=dict(ok=False,state='retained',members=sorted(cap.members,key=int) if cap else [],
            error=str(error)[:2048],unresolved=started,replayed=False,native_save_requested=False,
            originals_and_returned_edits_retained=True,save_reload_verified=False)
        if cap is not None and started:
            result['save_guid']=cap.witness['save_guid']
            try:_retain_failure(backend,cap,error)
            except Exception as storage_error:result['retention_storage_error']=str(storage_error)[:2048]
        backend._APEX_CAS_AUTO_SETTLEMENT=result;return result
    finally:
        backend._APEX_CAS_AUTO_CAPABILITY=None;backend._APEX_CAS_AUTO_SETTLEMENT_BUSY=False
