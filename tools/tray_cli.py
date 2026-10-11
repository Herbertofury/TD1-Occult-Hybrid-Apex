"""Tray group exchange and exact appearance clipboard import through the CLI."""
import base64
import hashlib
import json
from pathlib import Path
import uuid
import time
import tray_library
from source_manifest import sha256, write_json


def execute(args):
    import reusable_profile
    output = None
    if args.output is not None:
        output = reusable_profile.writable(args.output)
        if output.exists() or output.suffix.lower() != '.json': raise ValueError('Use one new external JSON Tray receipt.')
        if args.state is not None:
            _,_,active,original=reusable_profile.load(args.state)
            if any(output==root or root in output.parents for root in (active,original)): raise ValueError('Tray evidence belongs outside game profiles.')
    if args.operation == 'list':
        if args.folder is None: raise ValueError('Provide the explicit read-only Tray folder.')
        result = {'ok': True, 'items': [{'item': name, 'files': [p.name for p in paths],
            'households': [{'file': str(p), 'sha256': sha256(p)} for p in paths if p.suffix.lower() == '.householdbinary']}
            for name, paths in tray_library.groups(args.folder).items()], 'source_files_written': False}
    elif args.operation == 'inspect':
        if args.household is None or args.expected_sha256 is None: raise ValueError('Exact native household file/hash required.')
        result = tray_library.inspect(args.household, args.expected_sha256)
    elif args.operation == 'export':
        if args.folder is None or args.item is None or args.archive is None: raise ValueError('Select the explicit Tray folder/item and new ZIP destination.')
        result = tray_library.export(args.folder, args.item, args.archive)
    elif args.operation == 'import':
        if args.archive is None or args.state is None: raise ValueError('Explicit bundle and disposable profile state required.')
        result = tray_library.import_bundle(args.archive, args.state)
    else:
        if (args.inspection is None or args.expected_sha256 is None or args.state is None
                or args.source_sim_id is None or args.form is None or args.target_sim_id is None):
            raise ValueError('Exact Tray inspection/hash, source Sim/form, target Sim and profile state required.')
        inspected=tray_library.read(args.inspection,8*1024*1024)
        if hashlib.sha256(inspected).hexdigest() != args.expected_sha256:
            raise ValueError('Tray inspection differs from its exact file/hash.')
        doc = json.loads(inspected.decode('utf-8'))
        if doc.get('ok') is not True or doc.get('game_contacted') is not False: raise ValueError('Read-only Tray inspection required.')
        sources = [s for s in doc['sims'] if s['sim_id'] == args.source_sim_id]
        if len(sources) != 1: raise ValueError('Exact Tray source Sim is absent or ambiguous.')
        forms = [s for s in sources[0]['forms'] if s['form'] == args.form]
        if len(forms) != 1: raise ValueError('Exact represented Tray appearance owner required.')
        selection=None
        if args.operation == 'paste':
            if args.target_form is None or args.selection is None: raise ValueError('Explicit destination form and paste-selection JSON required.')
            selection=json.loads(tray_library.read(args.selection,8192).decode('utf-8'))
            if not isinstance(selection,dict) or set(selection)!={'fields','outfits','source_outfit','target_outfit','body_types'}:
                raise ValueError('Explicit fields/outfits/source_outfit/target_outfit/body_types selection required.')
        from apex_cli import owned_request, verified_identity, get, poll_request
        identity = verified_identity(args.state)
        if args.operation == 'preview':
            if args.outfit_index is None: raise ValueError('Select an explicit Tray source outfit index.')
            status=owned_request(args.state,'studio_status',args.target_sim_id,value=json.dumps({'form':args.target_form,'value':None}) if args.target_form is not None else None)
            if not status.get('ok'): raise ValueError(str(status))
            from preview_cli import native
            rows=tray_library.preview_forms(sources[0],doc['household_sha256'],identity,status)
            result=native(args.state,dict(operation='tray',selection=status,forms=rows,form=args.form,outfit_index=args.outfit_index))
            if not result.get('ok'): raise ValueError(result.get('reason','Tray source display refused.'))
            deadline=time.monotonic()+95
            while result.get('busy') or not result.get('ready'):
                if time.monotonic()>deadline: raise ValueError('Tray assembly is unresolved; read preview status without replaying load.')
                time.sleep(.2);result=native(args.state,dict(operation='status'))
                if not result.get('ok') or not result.get('busy') and not result.get('ready') and not result.get('staged'):
                    raise ValueError(result.get('reason',result.get('status','Tray scene failed.')))
            if (result.get('sim_id')!=args.source_sim_id or result.get('form')!=args.form or result.get('outfit_index')!=args.outfit_index
                    or result.get('destination_sim_id')!=args.target_sim_id or not result.get('tray_source')):
                raise ValueError('Rendered Tray source or retained destination differs.')
            if output is not None: write_json(output,result)
            return result
        provenance = dict(kind='tray', sim_id=args.source_sim_id, form=args.form, label=(sources[0]['name'] + ' / ' + doc['filename'])[:256])
        raw = json.dumps(dict(fields=forms[0]['fields'], source=provenance), sort_keys=True, ensure_ascii=True,
                         allow_nan=False, separators=(',', ':')).encode('utf-8')
        if len(raw) > 8 * 1024 * 1024: raise ValueError('Tray appearance clipboard exceeds bound.')
        # Begin uses the normal full profile/process verification. Each next
        # staged chunk rechecks the cheap bridge identity and retains its own
        # UUID before submission; a lost response polls that ID without replay.
        begin = owned_request(args.state, 'studio_clipboard_begin', args.target_sim_id,
            value=json.dumps(dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())))
        if begin.get('ok') is not True: raise ValueError(str(begin))
        result = dict(ok=False, stage='uploading', begin=begin, source=provenance, requests=[], sim_appearance_written=False)
        if output is not None: write_json(output, result)
        def call(action, value):
            current = get('/api/bridge')
            if any(current.get(k) != identity.get(k) for k in ('pid', 'test_token', 'script_sha256')):
                raise ValueError('Game identity changed; staged clipboard was not replayed.')
            rid = uuid.uuid4().hex
            result['requests'].append({'action': action, 'request_id': rid})
            if output is not None: write_json(output, result)
            try: reply = get('/api/command', dict(action=action, sim_id=args.target_sim_id, value=json.dumps(value), request_id=rid))
            except OSError: reply = {'request_state': 'running'}
            if reply.get('request_state') in ('running', 'pending'): reply = poll_request(rid)
            if reply.get('ok') is not True: raise ValueError(str(reply))
            return reply
        for index, offset in enumerate(range(0, len(raw), 3072)):
            call('studio_clipboard_chunk', dict(upload_id=begin['upload_id'], index=index, data=base64.b64encode(raw[offset:offset+3072]).decode('ascii')))
        imported = call('studio_clipboard_finish', dict(upload_id=begin['upload_id']))
        result.update(ok=True, stage='clipboard-ready', imported=imported, clipboard=imported['appearance_clipboard'])
        if args.operation == 'paste':
            status = owned_request(args.state, 'studio_status', args.target_sim_id,
                value=json.dumps({'form': args.target_form, 'value': None}))
            if not status.get('ok'): raise ValueError(str(status))
            clip = imported['appearance_clipboard']
            request = dict(clipboard_id=clip['id'], clipboard_sha256=clip['sha256'], selection=selection,
                           lane=status['history_lane'], appearance_sha256=status['appearance_sha256'])
            result['paste'] = owned_request(args.state, 'studio_paste_live' if args.apply_immediately else 'studio_paste_preview', args.target_sim_id,
                value=json.dumps({'form': args.target_form, 'value': json.dumps(request)}))
            result['ok'] = result['paste'].get('ok') is True; result['sim_appearance_written'] = bool(result['paste'].get('live_paste_applied'))
    if output is not None: write_json(output, result)
    return result
