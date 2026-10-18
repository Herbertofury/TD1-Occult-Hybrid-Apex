"""Player-facing forms projected from exact native owners; never rewrite looks.

Native/active storage records and legacy Human variants are not extra forms.
Every omitted owner remains available in the retained-looks inventory. No
appearance is copied, deleted, retagged or inferred from its rendering genus.
"""
import copy
import re

NATIVE = {1: ('human/shared', 'Human'), 2: ('alien/alien', 'Alien'),
          4: ('vampire/dark', 'Vampire'), 8: ('mermaid/mermaid', 'Mermaid'),
          16: ('witch/primary', 'Spellcaster'), 32: ('werewolf/beast', 'Werewolf'),
          64: ('fairy/primary', 'Fairy')}
_OWNER = re.compile(r'[a-z0-9_][a-z0-9_-]{0,63}/[a-z0-9_][a-z0-9_-]{0,63}\Z')
_PRIMARY = {'alien/alien_alien': 2, 'alien/alien': 2,
            'vampire/vampire_dark': 4, 'vampire/dark': 4,
            'mermaid/mermaid_mermaid': 8, 'mermaid/mermaid': 8,
            'witch/witch_primary': 16, 'spellcaster/primary': 16,
            'werewolf/werewolf_beast': 32, 'werewolf/beast': 32,
            'fairy/fairy_primary': 64, 'fairy/primary': 64}
_HUMAN_LOOKS = {
    'human/human_primary', 'human/primary', 'alien/alien_disguise', 'alien/disguise',
    'vampire/vampire_base', 'vampire/base', 'mermaid/mermaid_human', 'mermaid/human',
    'witch/witch_human', 'spellcaster/human', 'werewolf/werewolf_human', 'werewolf/human',
    'plantsim/plantsim_human', 'plantsim/human', 'ghost/ghost_living', 'ghost/living',
    'servo/servo_human_cc', 'servo/human_cc', 'skeleton/skeleton_human_cc', 'skeleton/human_cc',
    'scarecrow/scarecrow_human_cc', 'scarecrow/human_cc',
    'imaginary_friend/imaginary_friend_real', 'imaginary_friend/real'}
_FAMILIES = {'plantsim': 'PlantSim', 'servo': 'Servo', 'ghost': 'Ghost',
             'reaper': 'Reaper', 'skeleton': 'Skeleton', 'scarecrow': 'Scarecrow',
             'imaginary_friend': 'Imaginary Friend', 'fairy': 'Fairy', 'werewolf': 'Werewolf'}


def project(owners, human_owner_id, selected_owner_id, logical_owner_ids=None):
    """Choose display bindings, keeping every distinct original recoverable.

    A selected primary alias keeps its exact current owner; this is not a
    migration that overwrites the canonical lane with a possibly different look.
    Human uses the native engine's single explicitly designated shared owner.
    """
    if not isinstance(owners, list) or not 1 <= len(owners) <= 2048:
        raise ValueError('Forms require the complete bounded native owner inventory.')
    by_id = {}
    for row in owners:
        if (not isinstance(row, dict) or not isinstance(row.get('owner_id'), str) or
                _OWNER.fullmatch(row['owner_id']) is None or row['owner_id'] in by_id or
                type(row.get('native_kind')) is not int or row['native_kind'] not in NATIVE or
                type(row.get('ui_token')) is not int or not 0x20000000 <= row['ui_token'] <= 0x2fffffff):
            raise ValueError('A form descriptor has a duplicate or invalid exact identity/kind/token.')
        by_id[row['owner_id']] = row
        family, variant = row['owner_id'].split('/')
        if family in ('native', 'active') and variant != str(row['native_kind']):
            raise ValueError('A native storage identity has a different rendering kind.')
    if (human_owner_id not in by_id or by_id[human_owner_id]['native_kind'] != 1 or
            selected_owner_id not in by_id):
        raise ValueError('The exact shared Human or selected native owner is absent.')
    chosen = {1: human_owner_id}
    for kind in NATIVE:
        if kind == 1:
            continue
        if 'native/'+str(kind) in by_id:
            chosen[kind] = 'native/'+str(kind)
        active = 'active/'+str(kind)
        if active in by_id:
            chosen[kind] = active
    selected = by_id[selected_owner_id]
    primary_kind = _PRIMARY.get(selected_owner_id)
    if primary_kind is not None and selected['native_kind'] == primary_kind:
        chosen[primary_kind] = selected_owner_id
    if logical_owner_ids is not None:
        kinds={row['native_kind'] for row in owners if row['owner_id'].startswith('native/')}
        if (not isinstance(logical_owner_ids,dict) or set(logical_owner_ids)!={str(k) for k in kinds} or
                any(not isinstance(oid,str) or oid not in by_id or by_id[oid]['native_kind']!=int(kind)
                    for kind,oid in logical_owner_ids.items()) or logical_owner_ids.get('1')!=human_owner_id):
            raise ValueError('Visible form bindings differ from the exact native serialization bindings.')
        chosen={int(kind):oid for kind,oid in logical_owner_ids.items()}
    forms = []
    for kind in sorted(chosen):
        form_id, label = NATIVE[kind]
        forms.append(dict(copy.deepcopy(by_id[chosen[kind]]), form_id=form_id, label=label))
    for identity, row in sorted(by_id.items()):
        if identity in chosen.values() or identity.startswith(('native/', 'active/')):
            continue
        if identity in _HUMAN_LOOKS or identity in _PRIMARY:
            continue
        family, variant = identity.split('/')
        if family == 'human':
            continue # Additional saved Human looks never become more Humans.
        if variant.startswith(family+'_'):
            variant = variant[len(family)+1:]
        label = _FAMILIES.get(family, family.replace('_', ' ').title())
        if variant not in ('plant', 'robot', 'ghost', 'reaper', 'skeleton', 'scarecrow'):
            label += ' · '+variant.replace('_', ' ').title()
        forms.append(dict(copy.deepcopy(row), form_id=identity, label=label))
    visible = {row['owner_id'] for row in forms}
    return {'forms': forms,
            'human_owner_id': human_owner_id,
            'selected_form_id': next((row['form_id'] for row in forms
                                      if row['owner_id'] == selected_owner_id), None),
            'retained_looks': [copy.deepcopy(row) for row in owners if row['owner_id'] not in visible],
            'appearance_written': False}
