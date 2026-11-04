"""Finish one retained full-household CAS visit without replay or guessed edits.

Every hybrid member is observed before any member is written. Only explicitly
named Sim/form pairs keep returned edits; other changed owners restore their
fresh entry originals. Native bytes and restoration stay in the game receiver.
"""
import json
import hashlib
import math
import copy
from pathlib import Path

import cas_bank_cli
import cas_return
import reusable_profile
from source_manifest import sha256, write_json


def read_entry(path, expected, profile, original):
    if not cas_bank_cli._hash(expected):
        raise ValueError('CAS entry proof requires its exact SHA-256.')
    path = reusable_profile.legacy.unlinked(path)
    if path.suffix.lower() != '.json' or any(path == root or root in path.parents for root in (profile, original)):
        raise ValueError('Use the external retained CAS entry proof.')
    before = path.stat()
    if not path.is_file() or not 0 < before.st_size <= 16 * 1024 * 1024:
        raise ValueError('CAS entry proof exceeds its complete-packet bound.')
    raw = path.read_bytes(); after = path.stat()
    if (len(raw) > 16 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != expected or
            (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns)):
        raise ValueError('CAS entry proof changed or differs from its exact hash.')
    return json.loads(raw.decode('utf-8'), object_pairs_hook=cas_bank_cli._pairs)


def accepts(values, members):
    result = set()
    for value in values or []:
        parts = value.split(':') if isinstance(value, str) else []
        if len(parts) != 2 or parts[0] not in members or parts[1] not in cas_bank_cli.FORMS:
            raise ValueError('Each accepted edit must name an entry member and exact form: SIM_ID:FORM.')
        pair = tuple(parts)
        if pair in result:
            raise ValueError('Do not repeat an accepted Sim/form decision.')
        result.add(pair)
    return result


def owner_accepts(values, members):
    result=set()
    for value in values or []:
        parts=value.split(':') if isinstance(value,str) else []
        if len(parts)!=2 or parts[0] not in members:
            raise ValueError('Each named edit must identify an entry member and exact owner: SIM_ID:OWNER_ID.')
        cas_bank_cli._named_dispositions([dict(owner_id=parts[1],action='accept-returned')])
        pair=tuple(parts)
        if pair in result:raise ValueError('Do not repeat a named-form edit decision.')
        result.add(pair)
    return result


def retained_named_changes(profile,sid,checkpoint,identity):
    """Read an already-observed receiver journal; never repeat its observation.

    Older status replies omit named changes. Only names/decisions leave this
    read. The game receiver independently checks its held native-return digest
    again before accepting any plan; host appearance bytes are never submitted.
    """
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Source'))
    from apex_core import cas_named_return,cas_commit_plan
    path=reusable_profile.legacy.unlinked(profile/'TD1_OccultHybridApexData/form_bank.json')
    before=path.stat()
    if not path.is_file() or not 0<before.st_size<=64*1024*1024:
        raise ValueError('Retained receiver bank exceeds its complete bounded read.')
    raw=path.read_bytes();after=path.stat()
    if (len(raw)>64*1024*1024 or (before.st_size,before.st_mtime_ns,before.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino)):
        raise ValueError('Receiver journal changed during its read; no plan submitted.')
    data=json.loads(raw.decode('utf-8-sig'),object_pairs_hook=cas_bank_cli._pairs)
    rows=[row for key,row in data.get('records',{}).items() if key.endswith(':'+sid) and
          isinstance(row,dict) and isinstance(row.get('cas_transaction'),dict) and
          row['cas_transaction'].get('transaction_sha256')==checkpoint['expected_pending_sha256']]
    if len(rows)!=1:raise ValueError('Named changes lack one exact retained member checkpoint.')
    record=rows[0];transaction=record['cas_transaction'];returned=transaction.get('native_owner_return')
    if returned is None:
        if transaction.get('native_owner_return_required') is True:
            raise ValueError('Required named-form return is missing; no plan submitted.')
        return None
    if (not isinstance(returned,dict) or returned.get('checkpoint_epoch')!=checkpoint['expected_pending_sha256'] or
            returned.get('identity',{}).get('pid')!=identity['pid'] or returned.get('identity',{}).get('sim_id')!=sid or
            cas_commit_plan.digest(returned)!=transaction.get('native_owner_return_sha256')):
        raise ValueError('Named-form return belongs to another runtime or checkpoint.')
    return cas_named_return.changes(record,returned)


def entry_receipt(document):
    if (not isinstance(document, dict) or document.get('operation') != 'observe-native-cas-entry' or
            document.get('entry_accepted') is not True or document.get('entry_submitted') is not True):
        raise ValueError('Use the retained acknowledged native CAS entry proof.')
    results = [row.get('result') for row in document.get('steps', [])
               if row.get('action') in ('test_cas', 'test_cas_completion') and
               isinstance(row.get('result'), dict) and row['result'].get('ok') is True]
    if not results:
        raise ValueError('Entry proof has no acknowledged game-owned checkpoint receipt.')
    scope = results[-1].get('household_form_checkpoints')
    if (not isinstance(scope, dict) or scope.get('ok') is not True or
            not isinstance(scope.get('members'), list) or not 1 <= len(scope['members']) <= 8):
        raise ValueError('Entry lacks independent household checkpoints; old selected-only entries cannot qualify.')
    rows = {}
    for row in scope['members']:
        sid, checkpoint = row.get('sim_id'), row.get('form_checkpoint')
        if (not cas_return.decimal_id(sid) or sid in rows or not isinstance(checkpoint, dict) or
                checkpoint.get('ok') is not True or not cas_bank_cli._hash(checkpoint.get('expected_pending_sha256'))):
            raise ValueError('Entry member checkpoint identity is missing, duplicate or unacknowledged.')
        rows[sid] = checkpoint
    roster = scope.get('roster_sim_ids')
    if (not isinstance(roster, list) or not 1 <= len(roster) <= 8 or len(set(roster)) != len(roster) or
            any(not cas_return.decimal_id(sid) for sid in roster) or not set(rows) <= set(roster) or
            not cas_return.decimal_id(scope.get('household_id'))):
        raise ValueError('Entry roster or household identity is incomplete.')
    return scope, rows


def run(args, identity, request):
    from cli_identity_cache import session
    with session(args.state):
        return _run(args, identity, request)


def retained_resume(args, identity, scope, members, decisions, profile, original, owner_decisions=()):
    path, digest = getattr(args, 'resume_proof', None), getattr(args, 'resume_sha256', None)
    if path is None and digest is None:
        return None
    if path is None or digest is None:
        raise ValueError('Resume requires both the retained proof and its exact hash.')
    prior = read_entry(path, digest, profile, original)
    expected = [{'sim_id': sid, 'lane': lane} for sid, lane in sorted(decisions)]
    expected_named=[{'sim_id':sid,'owner_id':oid} for sid,oid in sorted(owner_decisions)]
    fields = ('pid', 'profile', 'test_token', 'script_sha256', 'build_version')
    if (prior.get('schema') != 1 or prior.get('operation') != 'commit-native-household-cas' or
            prior.get('ok') is not False or prior.get('entry_sha256') != args.entry_sha256 or
            prior.get('household_id') != scope['household_id'] or prior.get('member_sim_ids') != list(members) or
            prior.get('accepted_edits') != expected or prior.get('accepted_named_edits',[])!=expected_named or not isinstance(prior.get('identity'), dict) or
            any(prior['identity'].get(name) != identity.get(name) for name in fields)):
        raise ValueError('Resume differs from the retained runtime, entry, roster or explicit edit decisions.')
    steps = prior.get('steps')
    if (not isinstance(steps, list) or not steps or len(steps) > 1024 or
            not isinstance(steps[-1], dict) or steps[-1].get('request_id') is not None or
            'result' in steps[-1] or not isinstance(prior.get('error'), str) or
            not prior['error'].startswith('Test artifacts or journal changed during this CLI batch; no request sent.')):
        raise ValueError('Resume needs a certified unsent final request; observe unresolved UUIDs without replay.')
    retained = prior.get('retained_owner_steps', [])
    if not isinstance(retained, list) or len(retained) + len(steps) > 1024:
        raise ValueError('Retained owner receipt chain exceeds its bound.')
    completed = retained + steps[:-1]
    for step in completed:
        result = step.get('result') if isinstance(step, dict) else None
        if (not isinstance(result, dict) or result.get('ok') is not True or
                not cas_return.uuid_id(step.get('request_id')) or result.get('request_id') != step['request_id']):
            raise ValueError('An earlier owner receipt is unresolved; resume never repeats it.')
    for key, actions in (('observations', ('cas_bank_status', 'cas_bank_observe')),
                         ('plans', ('cas_bank_prepare',)), ('commits', ('cas_bank_commit',))):
        values = prior.get(key)
        if not isinstance(values, dict) or set(values) - set(members):
            raise ValueError('Retained household indexes name unknown members.')
        for sid, value in values.items():
            if not any(step.get('sim_id') == sid and step.get('action') in actions and
                       step.get('result') == value for step in completed):
                raise ValueError('Retained household index lacks its complete owned acknowledgement.')
    if set(prior['plans']) - set(prior['observations']) or set(prior['commits']) - set(prior['plans']):
        raise ValueError('Retained plans/commits lack their original observation and plan chain.')
    prior['_retained_completed_steps'] = completed
    return prior


def _run(args, identity, request):
    journal_path, journal, profile, original = reusable_profile.load(args.state)
    entry = read_entry(args.entry_proof, args.entry_sha256, profile, original)
    scope, members = entry_receipt(entry)
    held_identity = entry.get('identity')
    identity_fields = ('pid', 'profile', 'test_token', 'script_sha256', 'build_version')
    if (not isinstance(held_identity, dict) or
            any(held_identity.get(name) != identity.get(name) for name in identity_fields) or
            identity.get('test_token') != journal['token'] or
            identity.get('script_sha256') != next((row['sha256'] for row in journal['artifacts']
                if row['name'] == 'ApexOccultHybrid.ts4script'), None)):
        raise ValueError('Entry checkpoint belongs to another runtime, profile or candidate.')
    decisions = accepts(args.accept, members)
    owner_decisions=owner_accepts(getattr(args,'accept_owner',None),members)
    prior = retained_resume(args, identity, scope, members, decisions, profile, original,owner_decisions)
    if type(args.seconds) not in (int, float) or not math.isfinite(args.seconds) or not 0 < args.seconds <= 300:
        raise ValueError('Use a bounded per-request completion timeout.')
    output = reusable_profile.writable(args.output)
    if (output.exists() or output.suffix.lower() != '.json' or not output.parent.is_dir() or
            output == journal_path or any(output == root or root in output.parents for root in (profile, original))):
        raise ValueError('Use a new external household CAS proof filename.')
    proof = dict(schema=1, operation='commit-native-household-cas', ok=False, identity=identity,
                 entry_sha256=args.entry_sha256, household_id=scope['household_id'],
                 member_sim_ids=list(members), accepted_edits=[{'sim_id': sid, 'lane': lane}
                    for sid, lane in sorted(decisions)],
                 accepted_named_edits=[{'sim_id':sid,'owner_id':oid} for sid,oid in sorted(owner_decisions)],
                 steps=[], observations={}, plans={}, commits={},
                 automatic_replay_allowed=False, save_submitted=False, all_categories_edited_verified=False)
    if prior is not None:
        proof.update(resume_sha256=args.resume_sha256,
            retained_owner_steps=copy.deepcopy(prior['_retained_completed_steps']),
            observations=copy.deepcopy(prior['observations']), plans=copy.deepcopy(prior['plans']),
            commits=copy.deepcopy(prior['commits']), certified_unsent_resume=True)
    with output.open('x', encoding='utf-8') as stream:
        json.dump(proof, stream)

    def call(sid, action, value=None):
        step = dict(sim_id=sid, action=action, value=value, request_id=None)
        proof['steps'].append(step); write_json(output, proof)
        def submitting(submitted_action, request_id):
            if submitted_action != action or step['request_id'] is not None:
                raise ValueError('Household CAS request identity differs or was duplicated.')
            step['request_id'] = request_id; write_json(output, proof)
        result = request(args.state, action, sim_id=sid,
                         value=None if value is None else json.dumps(value, allow_nan=False),
                         seconds=args.seconds, submission_observer=submitting)
        step['result'] = result; write_json(output, proof)
        if (not isinstance(result, dict) or result.get('ok') is not True or
                step['request_id'] is None or result.get('request_id') != step['request_id']):
            raise ValueError('Household CAS result failed or is unresolved; retain its UUID without replay.')
        return result

    try:
        # Read every receiver and the whole native roster before observation.
        for sid, checkpoint in members.items():
            snapshot = call(sid, 'test_snapshot', {'test_token': journal['token'], 'value': 'forms'})
            if (not cas_return.live_snapshot(snapshot, sid, scope['household_id']) or
                    snapshot.get('clock_speed') != 0 or
                    set(snapshot.get('persistence', {}).get('household_sim_ids', [])) != set(scope['roster_sim_ids'])):
                raise ValueError('Full household did not return to paused native Live; no commit submitted.')
            status = call(sid, 'cas_bank_status')
            if status.get('current_runtime') is not True or status.get('expected_pending_sha256') != checkpoint['expected_pending_sha256']:
                raise ValueError('Member receiver is not this exact retained runtime/entry.')
            if prior is not None and sid in proof['commits']:
                if (sid not in proof['plans'] or status.get('completed_receipt') is not True or
                        status.get('native_availability_restore_verified') is not True or
                        status.get('plan_sha256') != proof['plans'][sid].get('plan_sha256') or
                        proof['commits'][sid].get('all_native_owners_verified') is not True):
                    raise ValueError('Previously committed member lacks its exact native completion receipt.')
                continue
            planned = prior is not None and status.get('phase') == 'planned' and sid in proof['plans']
            if (status.get('phase') not in ('captured', 'observed') and not planned or
                    status.get('expected_pending_sha256') != checkpoint['expected_pending_sha256'] or
                    status.get('native_write_possible') is not False or
                    status.get('native_write_attempted') is not False or status.get('metadata_commit_persisted') is not False):
                raise ValueError('Member receiver is not the retained fresh entry checkpoint.')
            if sid in proof['observations'] and (status.get('phase') not in ('observed', 'planned') or
                    status.get('raw_return_sha256') != proof['observations'][sid].get('raw_return_sha256')):
                raise ValueError('Retained raw observation changed; it cannot be repeated or replaced.')
            if sid in proof['plans'] and (not planned or
                    status.get('plan_sha256') != proof['plans'][sid].get('plan_sha256')):
                raise ValueError('Retained plan changed; no plan recreation or commit authorized.')
            # Semantic CAS return already observes its selected member once.
            # Reuse its exact retained, write-free journal rather than repeat
            # observation. Every companion is still observed before plans.
            if status['phase'] == 'observed' and sid not in proof['observations']:
                if not cas_bank_cli._hash(status.get('raw_return_sha256')):
                    raise ValueError('Retained member observation lacks its exact raw hash.')
                proof['observations'][sid] = status
                write_json(output, proof)
        for sid, checkpoint in members.items():
            observed = proof['observations'].get(sid)
            if observed is None:
                observed = call(sid, 'cas_bank_observe', {
                    'expected_pending_sha256': checkpoint['expected_pending_sha256']})
            if (observed.get('lane_change_evidence_available') is not True or
                    not isinstance(observed.get('changed_lanes'), list) or
                    not set(observed['changed_lanes']) <= cas_bank_cli.FORMS):
                raise ValueError('Complete member change evidence is unavailable; no decision guessed.')
            proof['observations'][sid] = observed; write_json(output, proof)
        named_changes={}
        for sid,checkpoint in members.items():
            observed=proof['observations'][sid]
            changes=observed.get('named_owner_changes')
            if changes is None and observed.get('phase')=='observed':
                changes=retained_named_changes(profile,sid,checkpoint,identity)
            if changes is not None:
                if not isinstance(changes,list):raise ValueError('Named changes are not a complete receiver list.')
                cas_bank_cli._named_dispositions([dict(owner_id=row.get('owner_id') if isinstance(row,dict) else None,
                    action='restore-original') for row in changes])
                named_changes[sid]=changes
        available={(sid,row['owner_id']) for sid,changes in named_changes.items() for row in changes}
        if not owner_decisions<=available:
            raise ValueError('An accepted named owner is not an actual changed receiver form; no plan submitted.')
        for sid, checkpoint in members.items():
            if sid in proof['plans']:
                continue
            observed = proof['observations'][sid]
            dispositions = [{'lane': lane, 'action': 'accept-returned' if (sid, lane) in decisions
                             else 'restore-original'} for lane in observed['changed_lanes']]
            value={
                'expected_pending_sha256': checkpoint['expected_pending_sha256'],
                'expected_raw_return_sha256': observed['raw_return_sha256'], 'dispositions': dispositions}
            if sid in named_changes:
                value['named_dispositions']=[dict(owner_id=row['owner_id'],action='accept-returned'
                    if (sid,row['owner_id']) in owner_decisions else 'restore-original') for row in named_changes[sid]]
            planned = call(sid, 'cas_bank_prepare', value)
            proof['plans'][sid] = planned; write_json(output, proof)
        for sid, checkpoint in members.items():
            if sid in proof['commits']:
                continue
            committed = call(sid, 'cas_bank_commit', {
                'expected_pending_sha256': checkpoint['expected_pending_sha256'],
                'expected_plan_sha256': proof['plans'][sid]['plan_sha256']})
            proof['commits'][sid] = committed; write_json(output, proof)
        for sid, checkpoint in members.items():
            status = call(sid, 'cas_bank_status')
            if (status.get('expected_pending_sha256') != checkpoint['expected_pending_sha256'] or
                    status.get('completed_receipt') is not True or
                    status.get('native_availability_restore_verified') is not True):
                raise ValueError('Member appearance/context completion did not verify.')
        proof.update(ok=True, every_member_native_availability_restored=True,
                     every_member_appearance_commit_verified=True)
    except (OSError, ValueError, RuntimeError) as error:
        proof.update(error=str(error), outcome='stopped-with-retained-evidence')
    write_json(output, proof)
    return {key: proof.get(key) for key in ('ok', 'error', 'member_sim_ids',
            'every_member_native_availability_restored', 'every_member_appearance_commit_verified')} | {
            'proof': str(output), 'proof_sha256': sha256(output)}
