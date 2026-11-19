"""Read every committed native form owner without changing or accepting CAS.

Requires the matching paged-export candidate in the running disposable game.
Receipts retain complete bytes; the summary records hashes and graph metadata.
The output is an appearance DTO collection, never whole-Sim restore authority.
"""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace


def run(state,output,sim_id=None):
    import sys
    root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'Source'))
    from apex_cli import execute,parser
    from cas_client import IntentEvidence
    from cas_owner_matrix import inventory
    from cli_identity_cache import session
    from source_manifest import sha256
    from apex_core.cas_owner_export_page import Collector
    state=Path(state);output=Path(output)
    evidence=IntentEvidence(SimpleNamespace(operation='native-owner-export',state=state,output=output,sim_id=sim_id))
    summary=dict(ok=False,operation='complete-committed-owner-export',members=[],receipts=[],
                 appearance_written=False,model_harvested=False,cas_accept_submitted=False,
                 save_submitted=False,production_ready=False)
    evidence.proof['read_only_export']=summary;evidence.record();sequence=0

    def call(value):
        nonlocal sequence
        path=output.with_name(output.stem+'-'+format(sequence,'04d')+'.json');sequence+=1
        if path.exists():raise ValueError('Retain the existing export receipt; do not replace it.')
        execute(parser().parse_args(['game','native-cas-engine','--state',str(state),
                                    '--value',json.dumps(value),'--output',str(path)]))
        result=json.loads(path.read_text(encoding='utf-8'))
        summary['receipts'].append(dict(path=str(path),sha256=sha256(path)))
        evidence.record()
        if result.get('ok') is not True:
            raise ValueError('Owner export failed; retain '+str(path)+': '+str(result.get('message',result.get('error'))))
        return result

    try:
        with session(state):
            native=call(dict(operation='status'));members,_=inventory(native)
            if sim_id is not None:
                members=[member for member in members if member['sim_id']==sim_id]
                if not members:raise ValueError('The requested Sim is outside the captured native household.')
            expected={row['sim_id']:row for row in native['members']}
            for member in members:
                sid=member['sim_id'];row=expected[sid]
                identity=dict(pid=native['pid'],scope_id=native['scope_id'],sim_id=sid,
                    generation=row['graph_generation'],owned_mask=member['owned_mask'],
                    selected_owner_id=row['graph_selected_owner_id'])
                collector=Collector(identity,{owner['owner_id']:owner['native_kind'] for owner in member['owners']})
                cursor=''
                while not collector.complete:
                    page=call(dict(operation='export-owner-page',scope_id=identity['scope_id'],sim_id=sid,
                                   expected_generation=identity['generation'],after_owner_id=cursor))
                    cursor=collector.append(page)['next_owner_id']
                document=collector.document()
                summary['members'].append(dict(identity=document['identity'],owners=[
                    {key:item[key] for key in ('owner_id','native_kind','revision','linked_targets','bytes','sha256')}
                    for item in document['owners']]))
                evidence.record()
            final=call(dict(operation='status'))
            rows={row['sim_id']:row for row in final['members']}
            if (final['pid']!=native['pid'] or final['scope_id']!=native['scope_id'] or
                    set(rows)!=set(expected) or any(rows[sid]['graph_generation']!=expected[sid]['graph_generation']
                        for sid in expected)):
                raise ValueError('The native household changed during export; no complete collection certified.')
            summary['ok']=True
    except Exception as error:
        summary['error']=str(error)
    return evidence.finish(summary)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--state',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--sim-id')
    args=p.parse_args();result=run(args.state,args.output,args.sim_id)
    print(json.dumps({key:result.get(key) for key in ('ok','error','output','proof_sha256','production_ready')}))
    raise SystemExit(0 if result['ok'] else 1)
