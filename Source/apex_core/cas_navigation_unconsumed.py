"""One original, same-peer pre-queue rejection, never timeout/success/retry."""
import re

EMITTER = 'apex-keyboard-loading-before-queue-v1'
MESSAGE = 'CAS catalog navigation rejected before consumption: catalog is still loading'
KEYS = {'left':37,'up':38,'right':39,'down':40,'home':36,'end':35,'pageup':33,'pagedown':34}
SCOPE = frozenset(('sim_id','household_id','owner_id','native_kind','shell_kind','native_mask',
                  'native_generation','session','layer','outfit_type','outfit_index','menu_state'))

def _need(value, message):
    if not value:raise ValueError('Unconsumed navigation refusal: '+message)

def _scope(value):
    _need(isinstance(value,dict) and set(value)==SCOPE,'complete exact native scope required')
    for key in ('sim_id','household_id','native_generation'):
        _need(isinstance(value[key],str) and re.fullmatch(r'[1-9][0-9]{0,19}',value[key]) is not None,'native identity type/range')
    _need(isinstance(value['owner_id'],str) and re.fullmatch(r'[a-z0-9_][a-z0-9_-]{0,63}/[a-z0-9_][a-z0-9_-]{0,63}',value['owner_id']) is not None,'exact owner identity')
    for key in SCOPE-set(('sim_id','household_id','native_generation','owner_id')):
        _need(type(value[key]) is int,'native scope integer type')
    _need(value['native_kind'] in (1,2,4,8,16,32,64) and value['shell_kind'] in (1,2,4,8,16,32,64),'native kind domain')
    _need(1<=value['native_mask']<=127 and 0<value['session']<2**31 and value['layer'] in (0,1),'native ownership range')
    _need(0<=value['outfit_type']<=255 and 0<=value['outfit_index']<5 and -2**31<=value['menu_state']<2**31,'outfit/menu range')
    return value

def validate(row, data, peers):
    """Raise on unknown/foreign/partially dispatched input; never modify a row."""
    _need(isinstance(row,dict) and isinstance(data,dict) and isinstance(peers,dict),'typed envelope required')
    request=row.get('request');lease=row.get('navigation_owner_lease')
    _need(isinstance(request,dict) and isinstance(lease,dict) and set(lease)=={'peer','context'},'original navigation owner lease required')
    op=request.get('operation');key=request.get('key')
    _need(op in ('catalog-input','catalog-key') and key in KEYS,'only typed non-Enter navigation')
    _need(set(request)==({'operation','key','focus_catalog'} if op=='catalog-input' else {'operation','key'}),'original request schema')
    _need(op!='catalog-input' or type(request['focus_catalog']) is bool,'explicit original focus choice')
    _need(set(data)=={'protocol','ok','cas_request_id','operation','scope','mutation_started','message','navigation_unconsumed'},'exact failure packet schema')
    rid=data.get('cas_request_id');wire=row.get('wire')
    _need(isinstance(rid,str) and re.fullmatch(r'[0-9a-f]{32}',rid) is not None and isinstance(wire,str) and wire.split('|',1)[0]==rid,'original UUID required')
    _need(type(data['protocol']) is int and data['protocol']==1 and data['ok'] is False and data['mutation_started'] is False and
          data['operation']==op and data['scope']=='native-cas-client' and data['message']==MESSAGE,'pinned failure type')
    token=row.get('peer');peer=peers.get(token)
    _need(isinstance(token,str) and re.fullmatch(r'[0-9a-f]{64}',token) is not None and token==lease['peer'] and
          isinstance(peer,dict) and peer.get('sim_id')==row.get('sim_id') and row.get('state')=='pending' and
          row.get('transport')=='loopback-socket' and row.get('delivery')=='claimed','exact original claimed peer')
    proof=data['navigation_unconsumed']
    _need(isinstance(proof,dict) and set(proof)=={'protocol','emitter','request_id','peer_nonce','before','after',
          'requested_key','key_code','source_route','rejection','key_listener_invoked','navigation_dispatched',
          'appearance_written','intent','queued','receipt_present','focus_requested'},'exact pre-queue proof schema')
    _need(type(proof['protocol']) is int and proof['protocol']==1 and proof['emitter']==EMITTER and
          proof['request_id']==rid and proof['peer_nonce']==token,'pinned emitter/original UUID/peer')
    scope=_scope(lease['context']);before=_scope(proof['before']);after=_scope(proof['after'])
    _need(before==scope and after==scope and scope['sim_id']==row['sim_id'],'fresh native before/after original scope mismatch')
    _need(proof['requested_key']==key and type(proof['key_code']) is int and proof['key_code']==KEYS[key] and
          proof['source_route']==('shared-keyboard-handler-before-queue' if op=='catalog-input' else 'semantic-navigation-before-queue') and
          proof['rejection']=='catalog-loading-before-consumption','exact pre-dispatch route/key')
    _need(proof['key_listener_invoked'] is (op=='catalog-input') and proof['focus_requested'] is (request['focus_catalog'] if op=='catalog-input' else False),'exact listener/focus provenance')
    _need(proof['navigation_dispatched'] is False and proof['appearance_written'] is False and proof['receipt_present'] is False and
          type(proof['intent']) is int and proof['intent']==0 and type(proof['queued']) is int and proof['queued']==0,'no consumption, appearance or queued intent')
    return True
