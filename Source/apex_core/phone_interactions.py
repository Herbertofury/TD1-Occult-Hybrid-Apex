"""Extend the authorized TD1 phone picker with Apex's game-thread controls.

Verified TD1 settings and packaged icons remain available. Unsafe legacy CAS
editing/cache restoration never delegates to the old mutation paths.
Selections use the same canonical dispatcher as F11 and the CLI.
"""
import json
from apex_hybrid.CoreLib.TD1_OccultHybrid_MenuUI import (
    TD1OccultHybridMenuUIPicker, MenuUIBaseIconsEnums, parse_ui_icon_enum_to_data)
from sims4.localization import LocalizationHelperTuning
from sims4.utils import flexmethod
from ui.ui_dialog_picker import BasePickerRow
from ui.ui_dialog_notification import UiDialogNotification

_LEGACY_RESTORE = 14750162471935511872
_LEGACY_CAS_EDIT = 14551493822752611098
# Verified native tuning references. Unknown/mixed continuations are never
# accepted merely because their first row resembles a harmless navigation.
_LEGACY_VERIFIED = {_LEGACY_RESTORE, _LEGACY_CAS_EDIT, 18005779871921288443,
    10500364228855805156, 16827766500387554810, 12059503387640811203,
    12469456690192303078, 16390568676589611435, 10100061338497243401,
    12894422578383759913, 13107731844359391213, 14784139966780459732}


def _legacy_continuations(choice):
    sequence = getattr(choice, 'continuation', None)
    if not isinstance(sequence, (tuple, list)) or not 1 <= len(sequence) <= 16:
        raise ValueError('Legacy phone continuation is unknown; use the Apex controls.')
    identities = []
    for item in sequence:
        identity = getattr(getattr(item, 'affordance', None), 'guid64', None)
        if type(identity) is not int or identity not in _LEGACY_VERIFIED:
            raise ValueError('Legacy phone continuation is unverified; use the Apex controls.')
        identities.append(identity)
    return tuple(identities)


def legacy_choice(choice):
    """Classify every queued continuation before the baseline can push it."""
    identities = _legacy_continuations(choice)
    if _LEGACY_RESTORE in identities or _LEGACY_CAS_EDIT in identities:
        if len(identities) != 1:
            raise ValueError('Mixed legacy CAS continuations were refused before any mutation.')
        return {'ok': True, 'page': 'cas_review' if identities[0] == _LEGACY_RESTORE else 'studio',
            'legacy_cas_entry_supported': False, 'legacy_mutation_submitted': False}
    return None


def catalog(backend, sim_id, page):
    """Return typed choices; no arbitrary command text or settings attribute."""
    if page == 'root':
        return [
            ('page:settings', 'Apex Settings', 'SETTINGS_VARIATION'),
            ('page:forms', 'Apex Forms', 'MENU_PLACEHOLDER'),
            ('page:saved', 'Apex Saved Forms', 'MENU_PLACEHOLDER'),
            ('page:studio', 'Apex CAS History', 'MENU_PLACEHOLDER'),
            ('page:drift', 'Apex Drift Guard', 'MENU_PLACEHOLDER'),
            ('action:overlay_show', 'Show F11 Menu', 'MENU_PLACEHOLDER'),
            ('action:overlay_status', 'F11 Menu Status', 'MENU_UNKNOWN'),
            ('action:diagnostics', 'Apex Diagnostics', 'MENU_UNKNOWN')]
    if page == 'settings':
        scanning = bool(backend._APEX7_SETTINGS.get('scan_after_apex_commands'))
        shield = bool(backend._MCCC_CAS_SHIELD_ENABLED)
        return [
            ('action:drift_scan_after_commands_' + ('off' if scanning else 'on'),
             'Scan after Apex changes: ' + ('On' if scanning else 'Off'), 'SETTINGS_ENABLED' if scanning else 'SETTINGS_DISABLED'),
            ('action:mccc_cas_shield_' + ('off' if shield else 'on'),
             'CAS recovery shield: ' + ('On' if shield else 'Off'), 'SETTINGS_ENABLED' if shield else 'SETTINGS_DISABLED')]
    if page == 'forms':
        sim = backend._get_sim_info_by_id(sim_id)
        choices = [('action:human', 'Switch to Human', 'MENU_PLACEHOLDER')]
        for name in ('ALIEN', 'VAMPIRE', 'MERMAID', 'WITCH', 'WEREWOLF', 'FAIRY'):
            occult = backend._occult_by_name(name)
            if occult is None:
                continue
            member = sim is not None and backend._has_occult(sim.occult_tracker, occult)
            choices.append(('occult:' + ('switch' if member else 'add') + ':' + name,
                            ('Switch to ' if member else 'Add ') + name.title(), 'MENU_PLACEHOLDER'))
        wolf = backend._occult_by_name('WEREWOLF')
        if sim is not None and wolf is not None and backend._has_occult(sim.occult_tracker, wolf):
            choices.extend([
                ('action:werewolf_human_status', 'Human-looking Werewolf status', 'MENU_UNKNOWN'),
                ('action:werewolf_human_on', 'Use Human appearance in Werewolf form', 'SETTINGS_ENABLED'),
                ('action:werewolf_human_off', 'Restore original Werewolf appearance', 'SETTINGS_DISABLED')])
        return choices
    if page == 'saved':
        return [('action:save_current_form', 'Capture current form', 'MENU_PLACEHOLDER'),
                ('action:list_saved_forms', 'Browse saved forms', 'MENU_PLACEHOLDER'),
                ('action:save_wardrobe', 'Capture CAS preset', 'MENU_PLACEHOLDER'),
                ('action:list_wardrobes', 'Browse CAS presets', 'MENU_PLACEHOLDER')]
    if page == 'studio':
        return [('cas:begin', 'Before CAS: retain every form original', 'MENU_PLACEHOLDER'),
                ('cas:observe', 'After CAS: run, pause and review every changed form', 'MENU_PLACEHOLDER'),
                ('page:cas_review', 'Review every form decision / apply prepared plan', 'MENU_PLACEHOLDER'),
                ('action:cas_bank_status', 'CAS form transaction status', 'MENU_UNKNOWN'),
                ('action:studio_status', 'Current appearance and history', 'MENU_UNKNOWN'),
                ('action:studio_checkpoint', 'Create appearance checkpoint', 'MENU_PLACEHOLDER'),
                ('action:studio_history', 'Browse appearance history', 'MENU_PLACEHOLDER'),
                ('action:studio_hair_enable', 'Keep hair separate for every outfit and form', 'SETTINGS_ENABLED'),
                ('action:studio_hair_disable', 'Disable independent outfit hair protection', 'SETTINGS_DISABLED'),
                ('action:studio_hair_status', 'Independent outfit hair status', 'MENU_UNKNOWN'),
                ('action:studio_undo', 'Preview Undo', 'MENU_BACK'),
                ('action:studio_redo', 'Preview Redo', 'MENU_BACK'),
                ('action:studio_cancel', 'Cancel pending preview', 'MENU_EXIT')]
    if page == 'drift':
        return [('action:drift_status', 'Drift Guard status', 'MENU_UNKNOWN'),
                ('action:scan_occult_drift', 'Scan for appearance drift', 'MENU_PLACEHOLDER')]
    if page == 'cas_review' or page.startswith('cas_form:'):
        from .phone_cas import rows
        return rows(backend, sim_id, page)
    raise ValueError('Unknown Apex phone page.')


def select(backend, sim_id, tag, callback=None):
    """Revalidate the offered action on click against current Sim/settings."""
    if not isinstance(tag, str) or not tag.startswith('apex:'):
        raise ValueError('Not an Apex phone choice.')
    tag = tag[5:]
    if tag.startswith('cas:'):
        from .phone_cas import select as cas_select
        return cas_select(backend, sim_id, tag, callback)
    if tag.startswith('page:cas_form:'):
        from .phone_cas import rows
        if tag not in {row[0] for row in rows(backend, sim_id, 'cas_review')}:
            raise ValueError('Form review page is stale; reopen every changed form.')
        return {'page': tag[5:]}
    allowed = {row[0] for page in ('root', 'settings', 'forms', 'saved', 'studio', 'drift')
               for row in catalog(backend, sim_id, page)}
    if tag == 'page:root':
        return {'page': 'root'}
    if tag not in allowed:
        raise ValueError('Phone choice is stale or unsupported; reopen the menu.')
    if tag.startswith('page:'):
        return {'page': tag[5:]}
    if tag.startswith('occult:'):
        _, action, occult = tag.split(':')
        return backend.run_action(action, sim_id=sim_id, occult=occult)
    action = tag[7:]
    result = backend.run_action(action, sim_id=sim_id)
    # History restores remain previews. Never silently apply an Undo/Redo choice.
    return result


class ApexPhoneMenu(TD1OccultHybridMenuUIPicker):
    @flexmethod
    def picker_rows_gen(cls, inst, target, context, **kwargs):
        import td1_occult_hybrid_apex as backend
        sim_id = str(context.sim.sim_info.id)
        page = getattr(inst, '_apex_page', 'root')
        if page == 'root':
            for row in super(ApexPhoneMenu, inst if inst is not None else cls).picker_rows_gen(target, context, **kwargs):
                try:
                    replacement = legacy_choice(row.tag)
                except ValueError:
                    continue
                if replacement is None:
                    yield row
        choices = catalog(backend, sim_id, page)
        if page != 'root':
            choices.append(('page:root', 'Back to Occult Hybrid', 'MENU_BACK'))
        for tag, label, icon in choices:
            yield BasePickerRow(name=LocalizationHelperTuning.get_raw_text(label), tag='apex:' + tag,
                                icon=parse_ui_icon_enum_to_data(getattr(MenuUIBaseIconsEnums, icon)))

    def on_choice_selected(self, choice, **kwargs):
        if not isinstance(choice, str) or not choice.startswith('apex:'):
            if choice is None:
                return None
            try:
                replacement = legacy_choice(choice)
            except ValueError as error:
                return self._present_apex_result({'ok': False, 'message': str(error)})
            if replacement is not None:
                return self._present_apex_result(replacement)
            return super().on_choice_selected(choice)
        import td1_occult_hybrid_apex as backend
        try:
            result = select(backend, str(self.sim.sim_info.id), choice, callback=self._present_apex_result)
        except Exception as error:
            result = {'ok': False, 'message': str(error)}
        # Showing a modal notification here would pause the clock before the
        # bounded game-thread Live probe can advance. Its callback opens review.
        if result.get('pending') is True:
            return
        return self._present_apex_result(result)

    def _present_apex_result(self, result):
        if 'page' in result:
            self._apex_page = result['page']
            self._show_picker_dialog(self.sim)
            return
        text = result.get('message') or json.dumps(result, ensure_ascii=False, default=str)
        rows = result.get('saved_forms', result.get('wardrobes'))
        if isinstance(rows, list):
            text += '\n' + '\n'.join('{} — {}'.format(row.get('label', row.get('name', 'Untitled')), row.get('id', ''))
                                      for row in rows[:30])
        if result.get('preview_id'):
            text += '\nPreview prepared; it has not changed the Sim. Apply through CAS History using preview ID ' + result['preview_id']
        dialog = UiDialogNotification.TunableFactory().default(
            self.sim, title=lambda **_k: LocalizationHelperTuning.get_raw_text('Apex Occult Hybrid'),
            text=lambda **_k: LocalizationHelperTuning.get_raw_text(text[:3500]))
        dialog.show_dialog()
