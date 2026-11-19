"""Restore two orphaned 1.13.7 pickers through the authorized working base.

The baseline package references this class but its script omits it. Reuse the
actual HybridOccultPickerSuperInteraction; never reduce membership for a panel.
"""
from apex_hybrid.IC_Hybrid.interactions import HybridOccultPickerSuperInteraction
from interactions import ParticipantTypeSim
from sims.occult.occult_enums import OccultType
from sims.occult.occult_tracker import OccultTracker
from sims4.common import Pack, is_available_pack
from sims4.localization import LocalizationHelperTuning
from sims4.tuning.tunable import TunableEnumEntry, TunableList, TunableTuple
from sims4.tuning.tunable_base import GroupNames
from sims4.utils import flexmethod
from ui.ui_dialog_picker import ObjectPickerRow


class TD1HybridOccultPickerSuperInteraction(HybridOccultPickerSuperInteraction):
    INSTANCE_TUNABLES = {
        'picker_target': TunableEnumEntry(tunable_type=ParticipantTypeSim, default=ParticipantTypeSim.Actor,
                                         tuning_group=GroupNames.PICKERTUNING),
        'picker_row_mapping': TunableList(tunable=TunableTuple(
            occult=TunableEnumEntry(tunable_type=OccultType, default=OccultType.HUMAN),
            occult_data=TunableTuple(pack=TunableEnumEntry(tunable_type=Pack, default=Pack.BASE_GAME))))}

    @flexmethod
    def picker_rows_gen(cls, inst, target, context, **kwargs):
        owner = inst if inst is not None else cls
        participant = owner.get_participant(cls.picker_target, target=target, context=context, **kwargs)
        sim = getattr(participant, 'sim_info', participant)
        if sim is None or getattr(sim, 'occult_tracker', None) is None:
            return
        pack_map = {row.occult: row.occult_data.pack for row in cls.picker_row_mapping}
        choices = [OccultType.HUMAN] + [kind for kind in OccultTracker.OCCULT_DATA if kind != OccultType.HUMAN]
        for kind in choices:
            if kind in pack_map and not is_available_pack(pack_map[kind]):
                continue
            if kind != OccultType.HUMAN and not sim.occult_tracker.has_occult_type(kind):
                continue
            tuning = OccultTracker.OCCULT_DATA.get(kind)
            if kind != OccultType.HUMAN and (tuning is None or tuning.current_occult_trait is None):
                continue
            trait = getattr(tuning, 'occult_trait', None)
            name = trait.display_name(participant) if trait is not None and trait.display_name else LocalizationHelperTuning.get_raw_text(kind.name)
            yield ObjectPickerRow(name=name, icon=getattr(trait, 'icon', None), tag=int(kind), is_enable=True)

    def on_choice_selected(self, choice_tag, **kwargs):
        if choice_tag is None:
            return
        participant = self.get_participant(self.picker_target)
        sim = getattr(participant, 'sim_info', participant)
        from td1_occult_hybrid_apex import run_action
        kind = OccultType(choice_tag)
        if kind != OccultType.HUMAN and not sim.occult_tracker.has_occult_type(kind):
            return
        return run_action('human' if kind == OccultType.HUMAN else 'switch', sim_id=str(sim.id), occult=kind.name)
