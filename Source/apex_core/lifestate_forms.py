"""Independent named appearance variants on existing native form owners.

Variants contain complete appearance payloads, never whole-Sim replacement data.
An explicit switch changes only its selected native appearance; it does not
claim to grant an NPC role, career, ghost death state or Imaginary Friend link.
All existing occult memberships and other native appearances remain intact.
"""
import copy
import hashlib
import os
import re
import uuid
from . import form_appearance as appearance, form_bank, lifestates

KEY = 'lifestate_forms'
_ID = re.compile(r'[a-z][a-z0-9_]{0,63}\Z')
MAX_FORMS = 1024
HUMAN_WEREWOLF = 'werewolf_human_cc'


def human_werewolf_variant(row):
    """The built-in Human/CC look has Human geometry, Werewolf gameplay."""
    return (row['id'] == HUMAN_WEREWOLF and row['lifestate'] == 'WEREWOLF'
            and row['base_form'] == 32)


def visual_form(row):
    return 1 if human_werewolf_variant(row) else row['base_form']


def _bind_runtime(record, sim):
    epoch = uuid.uuid4().hex
    record['lifestate_runtime_pid'] = os.getpid()
    record['lifestate_runtime_epoch'] = epoch
    sim.occult_tracker._apex_named_runtime_epoch = epoch


def _owns_runtime(record, sim):
    epoch = record.get('lifestate_runtime_epoch')
    return (record.get('lifestate_runtime_pid') == os.getpid() and isinstance(epoch, str) and
            re.fullmatch(r'[0-9a-f]{32}', epoch) is not None and
            getattr(sim.occult_tracker, '_apex_named_runtime_epoch', None) == epoch)


def handle(identity):
    """Studio-only numeric appearance handle; never a native occult bit mask."""
    return 0x40000000 | (int(hashlib.sha256(identity.encode('ascii')).hexdigest()[:8], 16) & 0x3fffffff)


def validate(document):
    if (not isinstance(document, dict) or set(document) != {'schema', 'forms', 'active'} or
            type(document['schema']) is not int or document['schema'] != 1 or
            not isinstance(document['forms'], dict) or not isinstance(document['active'], dict) or
            len(document['forms']) > MAX_FORMS):
        raise ValueError('Invalid independent life-state appearance document.')
    handles = set()
    for identity, row in document['forms'].items():
        if (not isinstance(identity, str) or not _ID.fullmatch(identity) or not isinstance(row, dict) or
                set(row) != {'id', 'lifestate', 'label', 'base_form', 'fields', 'appearance_sha256'} or
                row['id'] != identity or lifestates.name(row['lifestate']) != row['lifestate'] or
                type(row['base_form']) is not int or row['base_form'] not in lifestates.NATIVE.values() or
                not isinstance(row['label'], str) or not 0 < len(row['label'].strip()) <= 128 or
                not isinstance(row['fields'], dict) or
                '__outfits__' not in row['fields'] or
                appearance.fingerprint(row['fields'])['appearance_sha256'] != row['appearance_sha256']):
            raise ValueError('Life-state appearance identity, complete payload or checksum differs.')
        token = handle(identity)
        if token in handles:
            raise ValueError('Independent Studio appearance handles collide; no owner guessed.')
        handles.add(token)
    for lane, identity in document['active'].items():
        if (not isinstance(lane, str) or lane not in {str(i) for i in lifestates.NATIVE.values()} or
                identity not in document['forms'] or str(document['forms'][identity]['base_form']) != lane):
            raise ValueError('Active life-state appearance does not own its native lane.')
    return document


def document(record):
    return validate(copy.deepcopy(record.get(KEY, {'schema': 1, 'forms': {}, 'active': {}})))


def native_cas_owners(backend, sim):
    """Read all named owners during pre-entry, even with a captured checkpoint.

    Does not select a form, replace its native backing lane, or invent a
    membership. CAS's native graph receives complete independent appearances.
    """
    lifestates.owner_thread(backend, sim)
    path, key = form_bank.context(backend, sim)
    record = form_bank.load(path)['records'].get(key)
    if record is None or KEY not in record:
        return []
    if not _owns_runtime(record, sim):
        raise ValueError('Named CAS owners require their current native capture runtime.')
    data = document(record)
    from .cas_owner_payload import owner_id
    return [dict(owner_id=owner_id(row['lifestate'], row['id']), native_kind=visual_form(row),
                 fields=copy.deepcopy(row['fields']), appearance_sha256=row['appearance_sha256'])
            for row in data['forms'].values()]


def sync(record, lane, fields):
    """Called by existing accepted appearance transactions, never a polling hook."""
    if KEY not in record:
        return
    data = document(record)
    identity = data['active'].get(str(lane))
    if identity is not None:
        data['forms'][identity]['fields'] = copy.deepcopy(fields)
        data['forms'][identity]['appearance_sha256'] = appearance.fingerprint(fields)['appearance_sha256']
        validate(data)
        record[KEY] = data


def _context(backend, sim, native_capture=False):
    lifestates.owner_thread(backend, sim)
    form_bank.assert_idle(backend, sim)
    path, key = form_bank.context(backend, sim)
    bank = form_bank.load(path)
    record = bank['records'].get(key)
    if record is not None and KEY in record and not _owns_runtime(record, sim):
        from .form_bank_seal import admit_saved_named
        if admit_saved_named(backend, sim):
            bank = form_bank.load(path); record = bank['records'].get(key)
    if record is not None and not native_capture and not form_bank.current_runtime_authorized(backend, sim, record):
        raise ValueError('Life-state forms require the current accepted native bank; no old sidecar replay.')
    if record is not None and KEY in record and not _owns_runtime(record, sim):
        raise ValueError('Independent life-state reload is not yet qualified; prior appearances remain retained.')
    return path, key, bank, record


def _fields(backend, sim, base):
    if backend._get_current_flags(sim) == base:
        return appearance.packed(backend, sim)
    owners = backend._form_map(sim.occult_tracker)
    owner = owners.get(backend._coerce_flags(base))
    if owner is None:
        raise ValueError('A life-state appearance requires an existing native base owner.')
    return appearance.packed(backend, owner)


def capture(backend, sim, argument):
    if (not isinstance(argument, dict) or set(argument) != {'id', 'lifestate', 'label', 'base_form'} or
            not isinstance(argument['id'], str) or not _ID.fullmatch(argument['id']) or
            type(argument['base_form']) is not int or argument['base_form'] not in lifestates.NATIVE.values()):
        raise ValueError('Use an explicit named appearance ID, life state, label and existing base form.')
    state = lifestates.name(argument['lifestate'])
    # A new capture reads the current native owner, never an older bank lane.
    # Retain that older bank and its authority exactly; capture is not a rebase
    # or permission to restore it. Existing prior-runtime named forms still stop.
    path, key, bank, record = _context(backend, sim, native_capture=True)
    data = document(record or {})
    if argument['id'] in data['forms']:
        raise ValueError('That independent appearance already exists; no user edit was replaced.')
    if len(data['forms']) >= MAX_FORMS:
        raise ValueError('Life-state appearance capacity reached; no prior form was discarded.')
    # Initializing the built-in Human look must read the COMPLETE Human
    # appearance, including its outfits, shape, genetics and body paint. Its
    # gameplay lane remains Werewolf; no trait or native owner is changed.
    prototype = dict(argument, lifestate=state)
    fields = _fields(backend, sim, 1 if human_werewolf_variant(prototype) else argument['base_form'])
    data['forms'][argument['id']] = dict(argument, lifestate=state, fields=fields,
        appearance_sha256=appearance.fingerprint(fields)['appearance_sha256'])
    validate(data)
    if record is None:
        record = {'bank': form_bank.capture(backend, sim), 'history': [], 'runtime_pid': os.getpid()}
        bank['records'][key] = record
    record[KEY] = data
    _bind_runtime(record, sim)
    form_bank.save(path, bank)
    return {'ok': True, 'form': copy.deepcopy(data['forms'][argument['id']]),
            'appearance_modified': False, 'gameplay_modified': False, 'save_reload_verified': False}


def list_forms(backend, sim):
    _, _, _, record = _context(backend, sim, native_capture=True)
    data = document(record or {})
    return {'ok': True, 'forms': [dict(id=row['id'], label=row['label'], lifestate=row['lifestate'],
        base_form=row['base_form'], appearance_sha256=row['appearance_sha256'],
        active=data['active'].get(str(row['base_form'])) == row['id']) for row in data['forms'].values()],
        'appearance_modified': False, 'gameplay_modified': False, 'save_reload_verified': False}


def stored(backend, sim, identity):
    _, _, _, record = _context(backend, sim)
    data = document(record or {})
    row = data['forms'].get(identity)
    if row is None:
        raise ValueError('No existing independent life-state appearance has that ID.')
    return copy.deepcopy(row)


def by_handle(backend, sim, token, include_active=False):
    _, _, _, record = _context(backend, sim)
    data = document(record or {})
    matches = [row for identity, row in data['forms'].items() if handle(identity) == token]
    if len(matches) != 1:
        raise ValueError('No unique existing independent appearance owns this Studio handle.')
    row = copy.deepcopy(matches[0])
    active = data['active'].get(str(row['base_form'])) == row['id'] and backend._get_current_flags(sim) == row['base_form']
    return (row, active) if include_active else row


def is_active(backend, sim, identity):
    _, _, _, record = _context(backend, sim)
    data = document(record or {})
    row = data['forms'].get(identity)
    return bool(row and data['active'].get(str(row['base_form'])) == identity and
                backend._get_current_flags(sim) == row['base_form'])


def update(backend, sim, identity, fields, expected):
    """Studio edits an inactive variant without activating it or writing a Sim."""
    path, _, bank, record = _context(backend, sim)
    data = document(record or {})
    row = data['forms'].get(identity)
    if row is None or row['appearance_sha256'] != expected:
        raise ValueError('Independent appearance changed after inspection; no edit accepted.')
    if data['active'].get(str(row['base_form'])) == identity:
        raise ValueError('Edit the active native appearance; its accepted changes synchronize this variant.')
    if not isinstance(fields, dict) or set(fields) != set(row['fields']):
        raise ValueError('Independent appearance edits must retain every captured field.')
    row['fields'] = copy.deepcopy(fields)
    row['appearance_sha256'] = appearance.fingerprint(fields)['appearance_sha256']
    validate(data)
    record[KEY] = data
    form_bank.save(path, bank)


def initialize_human_werewolf(backend, sim, argument):
    """Explicit whole-body reset; archive the prior CC look before replacing it.

    Old captures incorrectly seeded this option from the beast. Never repair an
    existing player's look merely by opening the inventory or starting CAS.
    """
    if (not isinstance(argument, dict) or set(argument) != {'id', 'expected_sha256'}
            or argument['id'] != HUMAN_WEREWOLF):
        raise ValueError('Choose the built-in Human/CC Werewolf look and its inspected checksum.')
    path, _, bank, record = _context(backend, sim)
    data = document(record or {})
    row = data['forms'].get(HUMAN_WEREWOLF)
    if (row is None or not human_werewolf_variant(row)
            or row['appearance_sha256'] != argument['expected_sha256']):
        raise ValueError('Human/CC Werewolf appearance changed after inspection; no look replaced.')
    if data['active'].get('32') == HUMAN_WEREWOLF:
        raise ValueError('Leave this active appearance before initializing its stored Human/CC look.')
    fields = _fields(backend, sim, 1)
    if set(fields) != set(row['fields']):
        raise ValueError('Whole-body initialization must preserve every captured appearance field.')
    digest = appearance.fingerprint(fields)['appearance_sha256']
    if digest == row['appearance_sha256']:
        return dict(ok=True, changed=False, appearance_sha256=digest, native_appearance_modified=False)
    history = record.setdefault('human_werewolf_look_history', [])
    if not isinstance(history, list) or len(history) >= 256:
        raise ValueError('Human/CC appearance recovery history is full or invalid; no look replaced.')
    history.append(dict(operation='initialize-complete-human-look', before=copy.deepcopy(row),
                        after_sha256=digest, runtime_pid=os.getpid()))
    row['fields'] = copy.deepcopy(fields)
    row['appearance_sha256'] = digest
    record[KEY] = validate(data)
    form_bank.save(path, bank)
    return dict(ok=True, changed=True, appearance_sha256=digest, native_appearance_modified=False,
                previous_look_retained=True, visual_form=1, gameplay_form=32, save_file_written=False)


def select(backend, sim, argument):
    """Explicit appearance-only selection with durable originals and readback."""
    if (not isinstance(argument, dict) or set(argument) != {'id', 'expected_sha256'} or
            not isinstance(argument['id'], str)):
        raise ValueError('Select one existing life-state appearance and its inspected checksum.')
    path, key, bank, record = _context(backend, sim)
    data = document(record or {})
    row = data['forms'].get(argument['id'])
    if row is None or row['appearance_sha256'] != argument['expected_sha256']:
        raise ValueError('Selected appearance changed after inspection; no switch submitted.')
    base = row['base_form']
    if backend._get_current_flags(sim) != base:
        raise ValueError('Select this appearance\'s native base form first; no other occult was converted.')
    if str(base) not in data['active']:
        raise ValueError('Capture and activate an original appearance first with lifestate_form_bind.')
    owners = dict(backend._form_map(sim.occult_tracker))
    membership = backend._get_occult_flags(sim)
    traits = copy.deepcopy(backend._disk_trait_snapshot(sim))
    native = owners.get(backend._coerce_flags(base))
    if native is None:
        raise ValueError('Selected native appearance owner disappeared.')
    current = form_bank.capture(backend, sim)
    sync(record, base, current[str(base)])
    data = document(record)
    selected = data['forms'][argument['id']]
    if set(selected['fields']) != set(current[str(base)]):
        raise ValueError('Native appearance fields changed; retain both looks and capture a new checkpoint.')
    # Selecting the current variant retains later accepted CAS/Live edits.
    if selected['appearance_sha256'] != argument['expected_sha256']:
        raise ValueError('Current native appearance changed; inspect it again before selection.')
    intent = {'id': uuid.uuid4().hex, 'state': 'applying', 'kind': 'lifestate-appearance',
              'originals': current, 'target': copy.deepcopy(selected),
              'stored_originals': {str(kind): appearance.packed(backend, owner) for kind, owner in owners.items()},
              'active_original': appearance.packed(backend, sim),
              'prior_active': copy.deepcopy(data['active']), 'runtime_pid': os.getpid()}
    record['switch_pending'] = intent
    form_bank.save(path, bank)
    try:
        form_bank.restore(backend, sim, str(base), selected['fields'])
        lifestates.owner_thread(backend, sim)
        if form_bank.context(backend, sim) != (path, key):
            raise ValueError('Native appearance save context changed during selection.')
        fresh = backend._form_map(sim.occult_tracker)
        if set(fresh) != set(owners) or any(fresh[kind] is not owner for kind, owner in owners.items()):
            raise ValueError('Native appearance owner map changed during life-state selection.')
        if (backend._get_current_flags(sim) != base or backend._get_occult_flags(sim) != membership or
                backend._disk_trait_snapshot(sim) != traits):
            raise ValueError('Gameplay membership or traits changed during appearance selection.')
        after = form_bank.capture(backend, sim)
        for lane, fields in current.items():
            expected = selected['fields'] if lane == str(base) else fields
            if appearance.fingerprint(after[lane]) != appearance.fingerprint(expected):
                raise ValueError('Life-state selection changed another native appearance.')
        record[KEY] = data
        record[KEY]['active'][str(base)] = selected['id']
        record['bank'][str(base)] = copy.deepcopy(selected['fields'])
        from . import outfit_hair
        outfit_hair.sync(backend, record, base, selected['fields'])
        intent.update(state='completed', after={lane: appearance.fingerprint(fields) for lane, fields in after.items()})
        record.setdefault('lifestate_history', []).append(copy.deepcopy(intent))
        record['switch_pending'] = None
        form_bank.save(path, bank)
    except Exception as error:
        intent.update(state='recovery-required', error=str(error)[:2048], retry_safe=False)
        record['switch_pending'] = intent
        form_bank.save(path, bank)
        raise
    return {'ok': True, 'id': selected['id'], 'base_form': base, 'appearance_modified': True,
            'gameplay_modified': False, 'other_native_forms_verified': True,
            'save_reload_verified': False, 'unpaused_visual_verification_required': True}


def bind(backend, sim, argument):
    """Name the exact current original before first switching a native lane."""
    if not isinstance(argument, dict) or set(argument) != {'id', 'expected_sha256'}:
        raise ValueError('Bind one captured original appearance and its checksum.')
    path, _, bank, record = _context(backend, sim)
    data = document(record or {})
    row = data['forms'].get(argument['id'])
    if row is None or row['appearance_sha256'] != argument['expected_sha256']:
        raise ValueError('Original life-state appearance changed after inspection.')
    base = row['base_form']
    if str(base) in data['active']:
        raise ValueError('This lane already has an independent appearance owner.')
    if backend._get_current_flags(sim) != base or appearance.evidence(backend, sim)['appearance_sha256'] != row['appearance_sha256']:
        raise ValueError('Only the exact current appearance can be bound as original.')
    data['active'][str(base)] = row['id']
    record[KEY] = validate(data)
    form_bank.save(path, bank)
    return {'ok': True, 'appearance_modified': False, 'gameplay_modified': False, 'id': row['id']}


def _requalify(backend, sim, argument, as_draft=False):
    """Requalify unchanged native captures after restart, without restoring one.

    Edited/inactive saved variants which differ from native data require the
    separate persistence path; this operation cannot bless or replay them.
    """
    from .form_bank_seal import _hash, _sha
    required = {'expected_document_sha256', 'prior_pid', 'household_id', 'save_guid'}
    if (not isinstance(argument, dict) or set(argument) != required or
            not _sha(argument['expected_document_sha256']) or type(argument['prior_pid']) is not int or
            not 0 < argument['prior_pid'] <= 0xffffffff or argument['prior_pid'] == os.getpid() or
            any(not isinstance(argument[name], str) or not argument[name].isascii() or
                not argument[name].isdecimal() or argument[name].startswith('0') or
                not 0 < int(argument[name]) < 1 << 64 for name in ('household_id', 'save_guid'))):
        raise ValueError('Revalidate one exact prior native capture document and save/household identity.')
    lifestates.owner_thread(backend, sim);form_bank.assert_idle(backend, sim)
    path, key = form_bank.context(backend, sim)
    bank = form_bank.load(path);record = bank['records'].get(key)
    if (not isinstance(record, dict) or KEY not in record or
            record.get('lifestate_runtime_pid') != argument['prior_pid'] or
            key != argument['save_guid'] + ':' + str(sim.id) or str(sim.household_id) != argument['household_id']):
        raise ValueError('Named captures belong to another runtime, Sim, household or save.')
    data = document(record)
    if not data['forms'] or _hash(data) != argument['expected_document_sha256']:
        raise ValueError('Named capture document changed; no runtime authority updated.')
    if not form_bank._old_process_absent(argument['prior_pid']):
        raise ValueError('The captured runtime is still alive; no cross-runtime selection allowed.')
    def live():
        zone = backend.services.current_zone()
        if (zone is None or not zone.is_zone_running or
                int(backend.services.game_clock_service().clock_speed) != 0 or
                str(backend.services.active_household().id) != argument['household_id'] or
                form_bank.context(backend, sim) != (path, key)):
            raise ValueError('Named capture revalidation requires the exact paused Live household.')
        lifestates.owner_thread(backend, sim)
    live()
    if as_draft:
        actual = form_bank.capture(backend, sim)
        lane = str(backend._get_current_flags(sim))
        if lane not in actual or any(str(row['base_form']) not in actual for row in data['forms'].values()):
            raise ValueError('Every resumed draft requires its existing native backing owner.')
        for fields in actual.values():appearance.fingerprint(fields)
        history = record.setdefault('named_draft_history', [])
        if not isinstance(history, list):raise ValueError('Named draft history is malformed.')
        history.append(dict(prior_pid=argument['prior_pid'],runtime_pid=os.getpid(),
            document_sha256=argument['expected_document_sha256'],prior_bank=copy.deepcopy(record['bank']),
            prior_bank_runtime_pid=record.get('runtime_pid'),saved_names_certified=False))
        record.update(bank=actual,active_lane=lane,runtime_pid=os.getpid(),lifestate_runtime_pid=os.getpid())
        _bind_runtime(record,sim)
        live();form_bank.save(path,bank)
        return dict(ok=True,named_draft_resumed=True,saved_names_certified=False,
            captured_forms_retained=len(data['forms']),appearance_modified=False,
            bank_authority_updated=True,save_file_written=False,save_reload_verified=False)
    observations = []
    for row in data['forms'].values():
        actual = appearance.fingerprint(_fields(backend, sim, row['base_form']))['appearance_sha256']
        if actual != row['appearance_sha256']:
            raise ValueError('A named appearance differs from native data; every retained edit was preserved.')
        observations.append(dict(id=row['id'], native_sha256=actual))
    live()
    history = record.setdefault('lifestate_revalidation_history', [])
    if not isinstance(history, list): raise ValueError('Named capture audit history is invalid.')
    history.append(dict(prior_pid=argument['prior_pid'], runtime_pid=os.getpid(),
        document_sha256=argument['expected_document_sha256'], observations=observations,
        appearance_restored=False, bank_authority_updated=False))
    _bind_runtime(record,sim)
    form_bank.save(path, bank)
    return dict(ok=True, captured_forms_verified=len(observations), appearance_modified=False,
        bank_authority_updated=False, save_file_written=False, save_reload_verified=False)


def revalidate(backend, sim, argument):
    return _requalify(backend, sim, argument)


def resume_draft(backend, sim, argument):
    """Explicitly keep a prior look as an unsaved draft, never a saved receipt."""
    return _requalify(backend, sim, argument, as_draft=True)


def dispatch(backend, sim, action, value):
    if action == 'lifestate_catalog':
        if value not in (None, ''):
            raise ValueError('The native life-state catalog takes no external payload.')
        return lifestates.catalog(backend, sim)
    if action == 'lifestate_form_list':
        if value not in (None, ''):
            raise ValueError('Life-state form inventory takes no external payload.')
        return list_forms(backend, sim)
    argument = backend._apex_cas_transaction_argument(value)
    operation = {'lifestate_form_capture': capture, 'lifestate_form_bind': bind,
                 'lifestate_form_select': select, 'lifestate_form_revalidate': revalidate,
                 'lifestate_form_resume_draft': resume_draft,
                 'lifestate_form_human_look': initialize_human_werewolf}.get(action)
    if operation is None:
        raise ValueError('Unknown independent life-state form operation.')
    return operation(backend, sim, argument)
