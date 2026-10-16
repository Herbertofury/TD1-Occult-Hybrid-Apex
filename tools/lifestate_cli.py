"""Exact named appearance commands over the game-owned transport; no UI input."""
import json
import re
from cas_client import IntentEvidence
from cli_identity_cache import session


def argument(args):
    operation = args.operation
    if not isinstance(args.sim_id, str) or re.fullmatch(r'[1-9][0-9]{0,19}',args.sim_id) is None or int(args.sim_id) >= 1 << 64:
        raise ValueError('Choose one exact existing uint64 Sim identity.')
    options = {name:getattr(args,name,None) for name in ('id','lifestate','label','base_form','expected_sha256')}
    reload = {name:getattr(args,name,None) for name in ('expected_document_sha256','prior_pid','household_id','save_guid')}
    if operation=='revalidate':
        if (any(value is not None for value in options.values()) or
                not isinstance(reload['expected_document_sha256'],str) or re.fullmatch(r'[0-9a-f]{64}',reload['expected_document_sha256']) is None or
                type(reload['prior_pid']) is not int or not 0 < reload['prior_pid'] <= 0xffffffff or
                any(not isinstance(reload[name],str) or re.fullmatch(r'[1-9][0-9]{0,19}',reload[name]) is None or
                    int(reload[name]) >= 1 << 64 for name in ('household_id','save_guid'))):
            raise ValueError('Revalidation requires the exact captured document/runtime/save/household and no edit payload.')
        return 'lifestate_form_revalidate',reload
    if any(value is not None for value in reload.values()):
        raise ValueError('Capture reload options cannot be attached to another operation.')
    if operation in ('catalog','list'):
        if any(value is not None for value in options.values()):
            raise ValueError('Life-state inventory accepts no appearance mutation options.')
        return 'lifestate_catalog' if operation=='catalog' else 'lifestate_form_list', None
    if not isinstance(options['id'], str) or re.fullmatch(r'[a-z][a-z0-9_]{0,63}',options['id']) is None:
        raise ValueError('Choose one named independent appearance ID.')
    if operation=='capture':
        if (options['expected_sha256'] is not None or type(options['base_form']) is not int or
                options['base_form'] not in (1,2,4,8,16,32,64) or
                not isinstance(options['lifestate'], str) or not options['lifestate'].strip() or
                not isinstance(options['label'],str) or not 0<len(options['label'].strip())<=128):
            raise ValueError('Capture requires life state, label and existing native base; no guessed checksum.')
        return 'lifestate_form_capture', {key:options[key] for key in ('id','lifestate','label','base_form')}
    if operation not in ('bind','select'):
        raise ValueError('Unknown life-state appearance operation.')
    if (any(options[name] is not None for name in ('lifestate','label','base_form')) or
            not isinstance(options['expected_sha256'],str) or re.fullmatch(r'[0-9a-f]{64}',options['expected_sha256']) is None):
        raise ValueError('Bind/Select requires the inspected appearance checksum and no replacement data.')
    return 'lifestate_form_'+operation, dict(id=options['id'],expected_sha256=options['expected_sha256'])


def run(args, request):
    action, value = argument(args)
    with session(args.state):
        evidence = IntentEvidence(args)
        try:
            reply = evidence.wrap(request)(args.state,action,args.sim_id,
                value=None if value is None else json.dumps(value,ensure_ascii=True,allow_nan=False))
            return evidence.finish(reply)
        except BaseException as error:
            evidence.fail(error)
            raise
