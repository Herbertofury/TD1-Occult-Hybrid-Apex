"""Execute actual Main GRIDSTATE method bodies against fresh native doubles."""
import shutil
import unittest

import test_cas_main_grid_transaction as fixture


@unittest.skipUnless(shutil.which('node'), 'Node required for actual Main AS bodies')
class MainFreshGridStateTests(unittest.TestCase):
    def harness(self):
        return fixture.MainGridLeaseTests.harness(self)

    def run_js(self, suffix):
        fixture.MainGridLeaseTests.run_js(self, suffix)

    def test_bootstrap_rebind_and_every_write_keep_the_full_fresh_read_fence(self):
        self.run_js(r'''
ApexCatalogGridBootstrap();assert.equal(fullInfoReads,0);assert.equal(stateReads,0);assert.equal(gridStateReads,0);
ApexCatalogGridFrame();assert.deepEqual(reads,['CASGetSimInfo','CasGetCurrSimOutfitSlot']);
assert.equal(fullInfoReads,1);assert.equal(stateReads,0);assert.equal(gridStateReads,1);
pump();const before=reads.length,full=fullInfoReads,states=stateReads,grids=gridStateReads;
for(let i=0;i<5;i++)assert.equal(grid.click(),true);
assert.equal(writes,5);assert.equal(fullInfoReads,full+5);assert.equal(stateReads,states);assert.equal(gridStateReads,grids+5);
assert.deepEqual(reads.slice(before),Array.from({length:5},()=>['CASGetSimInfo','CasGetCurrSimOutfitSlot']).flat());
messages.CASSetSimInfo({});nativeGeneration='74';apexFormsNativeGeneration='74';
const rebindReads=reads.length,rebindFull=fullInfoReads,rebindStates=stateReads,rebindGrid=gridStateReads;
ApexCatalogGridFrame();assert.deepEqual(reads.slice(rebindReads),['CASGetSimInfo','CasGetCurrSimOutfitSlot']);
assert.equal(fullInfoReads,rebindFull+1);assert.equal(stateReads,rebindStates);assert.equal(gridStateReads,rebindGrid+1);
''')

    def test_full_observation_rejects_cached_ea_row_when_native_household_or_masks_disagree(self):
        changes = ("nativeSim.householdId='808';", 'nativeViewMask=63;',
                   'nativeModelMask=63;', 'nativeViewMask=63;nativeModelMask=63;',
                   "nativeModelContext={id:'replaced-model'};")
        for change in changes:
            for phase in ('bootstrap', 'input'):
                with self.subTest(change=change, phase=phase):
                    self.run_js(r'''
ApexCatalogGridBootstrap();
''' + ("pump();" if phase == 'input' else '') + r'''
// This is the stale EA getter row as well as the unchanged presentation cache.
simRowOverride={...nativeSim};const old=apexCatalogGrid.lease;
const full=fullInfoReads,grids=gridStateReads,steps=grid.steps,previousReads=reads.length;
''' + change + (r'''
assert.equal(grid.click(),false);assert.equal(old.active,false);
''' if phase == 'input' else r'''
ApexCatalogGridFrame();assert.equal(apexCatalogGrid.lease.phase,'bootstrap');
''') + r'''
assert.equal(grid.steps,steps);assert.equal(writes,0);assert.equal(fullInfoReads,full+1);
assert.equal(gridStateReads,grids+1);assert.equal(stateReads,0);
assert.deepEqual(reads.slice(previousReads),['CASGetSimInfo','CasGetCurrSimOutfitSlot']);
assert.equal(mCurrSimInfo.householdId,'909');assert.equal(mCurrSimInfo.allOccultTypes,127);
assert.equal(simRowOverride.householdId,'909');assert.equal(simRowOverride.allOccultTypes,127);
''')

    def test_repeated_visual_work_frames_read_one_fresh_outfit_and_gridstate_without_full_getter(self):
        self.run_js(r'''
ApexCatalogGridBootstrap();pump();const before=reads.length,full=fullInfoReads,states=stateReads,grids=gridStateReads;
const service=CommunicationManager.CallGameService;
CommunicationManager.CallGameService=function(name,...args){if(name==='CASGetSimInfo')throw Error('visual frame attempted full info getter');return service.call(this,name,...args);};
for(let i=0;i<40;i++){grid.phase='bind';grid.dirty=true;ApexCatalogGridFrame();assert.equal(apexCatalogGrid.error,'');}
assert.equal(fullInfoReads,full);assert.equal(stateReads,states);assert.equal(gridStateReads,grids+40);
assert.deepEqual(reads.slice(before),Array(40).fill('CasGetCurrSimOutfitSlot'));
assert.equal(nativeExchanges.filter(command=>command==='GRIDSTATE|77').length,gridStateReads);
assert.equal(writes,0);
''')

    def test_fresh_native_identity_masks_owner_generation_layer_and_model_context_gate_publish(self):
        changes = ("nativeSim.simId='202';", "nativeSim.householdId='808';", "nativeOwner='ghost/manifested';",
                   "nativeGeneration='74';", 'nativeSim.occultLayer=0;', 'nativeRendererKind=8;',
                   'nativeViewMask=63;', 'nativeModelMask=63;', "nativeModelContext={id:'different-model'};")
        for change in changes:
            with self.subTest(change=change):
                self.run_js(r'''
ApexCatalogGridBootstrap();pump();const lease=apexCatalogGrid.lease;grid.phase='bind';grid.dirty=true;
const beforeSteps=grid.steps,beforeReads=reads.length,full=fullInfoReads,states=stateReads,grids=gridStateReads;
''' + change + r'''
ApexCatalogGridFrame();assert.equal(grid.steps,beforeSteps);assert.equal(writes,0);assert.equal(lease.active,false);
assert.equal(fullInfoReads,full);assert.equal(stateReads,states);assert.equal(gridStateReads,grids+1);
assert.deepEqual(reads.slice(beforeReads),['CasGetCurrSimOutfitSlot']);
assert.equal(grid.click(),false);assert.equal(writes,0);
// Main's cached presentation identity has not been substituted for fresh native authority.
assert.equal(mCurrSimInfo.simId,'101');assert.equal(mCurrSimInfo.householdId,'909');assert.equal(mCurrSimInfo.occultLayer,1);
''')

    def test_model_mask_is_distinct_from_view_mask_and_both_are_required(self):
        for view, model in ((127, 63), (63, 127), (63, 63)):
            with self.subTest(view=view, model=model):
                self.run_js(r'''
ApexCatalogGridBootstrap();pump();grid.phase='bind';grid.dirty=true;const before=grid.steps;
''' + 'nativeViewMask=' + str(view) + ';nativeModelMask=' + str(model) + ';' + r'''
const packet=freshGridWire().split('|');assert.equal(packet.length,9);
assert.equal(packet[6],String(nativeViewMask));assert.equal(packet[7],String(nativeModelMask));
ApexCatalogGridFrame();assert.equal(grid.steps,before);assert.equal(apexCatalogGrid.lease.active,false);assert.equal(writes,0);
''')

    def test_missing_or_malformed_gridstate_never_falls_back_to_cached_or_full_observation(self):
        packets = ('WAIT', '', 'VIEWSTATE|101|909|alien/alien|2|1|127|127|73',
                   'GRIDSTATE|101|909|alien/alien|2|1|127|73',
                   'GRIDSTATE|101|909|alien/alien|2|1|127|127|73|extra',
                   'GRIDSTATE|101|0|alien/alien|2|1|127|127|73',
                   'GRIDSTATE|101|909|alien/alien|2|1|127|127|073')
        for packet in packets:
            with self.subTest(packet=packet):
                self.run_js(r'''
ApexCatalogGridBootstrap();pump();grid.phase='bind';grid.dirty=true;
const steps=grid.steps,full=fullInfoReads,states=stateReads,grids=gridStateReads;
''' + 'gridStateOverride=' + repr(packet) + ';' + r'''
ApexCatalogGridFrame();assert.equal(grid.steps,steps);assert.equal(fullInfoReads,full);assert.equal(stateReads,states);
assert.equal(gridStateReads,grids+1);assert.equal(apexCatalogGrid.lease.active,false);assert.equal(writes,0);
''')

    def test_outfit_is_fresh_and_new_slot_requires_full_observation_before_rebind(self):
        self.run_js(r'''
ApexCatalogGridBootstrap();pump();const previous=apexCatalogGrid.lease,full=fullInfoReads;
nativeSlot={outfit_type:3,outfit_index:2};grid.phase='bind';grid.dirty=true;const beforeSteps=grid.steps;ApexCatalogGridFrame();
assert.equal(previous.active,false);
if(grid.steps>beforeSteps)assert.equal(fullInfoReads,full+1,'a new outfit cannot step before its full freshness fence');
pump();assert.notEqual(apexCatalogGrid.lease,previous);assert.equal(fullInfoReads,full+1);
assert.equal(apexCatalogGrid.lease.outfit_type,3);assert.equal(apexCatalogGrid.lease.outfit_index,2);
const beforeWrite=fullInfoReads;assert.equal(grid.click(),true);assert.equal(fullInfoReads,beforeWrite+1);assert.equal(writes,1);
''')
        for slot in ('null', '{outfit_type:-1,outfit_index:0}', '{outfit_type:0,outfit_index:1.5}',
                     '{outfit_type:"0",outfit_index:0}'):
            with self.subTest(slot=slot):
                self.run_js(r'''
ApexCatalogGridBootstrap();pump();grid.phase='bind';grid.dirty=true;const steps=grid.steps,full=fullInfoReads;
''' + 'nativeSlot=' + slot + ';' + r'''
ApexCatalogGridFrame();assert.equal(grid.steps,steps);assert.equal(fullInfoReads,full);assert.equal(apexCatalogGrid.lease.active,false);assert.equal(writes,0);
''')

    def test_context_change_between_outfit_read_and_gridstate_is_observed_before_step(self):
        self.run_js(r'''
ApexCatalogGridBootstrap();pump();grid.phase='bind';grid.dirty=true;const steps=grid.steps,full=fullInfoReads;
onOutfitRead=()=>{nativeGeneration='74';};
ApexCatalogGridFrame();assert.equal(grid.steps,steps);assert.equal(fullInfoReads,full);assert.equal(writes,0);
assert.equal(apexCatalogGrid.lease.active,false);assert.equal(apexCatalogGrid.waiting,'fresh-native-grid');
''')

    def test_visual_context_contains_only_primitives_and_preserves_renderer_shell_distinction(self):
        self.run_js(r'''
nativeSim.occultType=4;ApexCatalogGridBootstrap();pump();const full=fullInfoReads;
apexCatalogGrid.running=true;let context;
try{context=ApexCatalogGridFrameObserve();}finally{apexCatalogGrid.running=false;}
assert.ok(context);assert.equal(context.native_kind,2);assert.equal(context.shell_kind,4);assert.equal(context.native_mask,127);
assert.equal(fullInfoReads,full);assert.ok(JSON.stringify(context));
for(const value of Object.values(context))assert.ok(['string','number','boolean'].includes(typeof value));
for(const key of ['root','stage','panel','grid','feed','validate','inputValidate','info','appearance'])assert.equal(key in context,false);
const outside=reads.length;assert.equal(ApexCatalogGridFrameObserve(),null);assert.equal(reads.length,outside);
''')


if __name__ == '__main__':
    unittest.main()
