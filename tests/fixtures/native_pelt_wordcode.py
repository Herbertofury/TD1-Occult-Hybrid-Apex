"""Own synthetic generator: exercise actual Python 3.7 calls, not EA source."""
import dis
import hashlib
import sys
import types

sys.path.insert(0,sys.argv[1])
from apex_core import native_pelt_copy as pelt


class OccultType:
    HUMAN=1
    WEREWOLF=32
    FAIRY=64


class Owner:
    def __init__(self,kind,value):self.kind=kind;self.pelt_layers=value


class Tracker:
    def __init__(self,mask):
        self._sim_info=types.SimpleNamespace(id=44,occult_types=mask)
        self._sim_info_map={1:Owner(1,b'nonempty authored Human')}
        self.calls=0

    def _generate_sim_info(self,occult_type,generate_new=False):
        self.calls+=1
        sim_info=Owner(occult_type,b'new generated paint')
        if occult_type==OccultType.WEREWOLF or occult_type==OccultType.FAIRY:
            self._sim_info_map[OccultType.HUMAN].pelt_layers=sim_info.pelt_layers
        self._sim_info_map[occult_type]=sim_info
        return sim_info


original=Tracker._generate_sim_info;before=original.__code__;defaults=original.__defaults__
# The fixture contract stays private to this subprocess; production has one
# literal inspected game pin and accepts no request-provided code or pin.
pelt.NATIVE_SHA=hashlib.sha256(before.co_code).hexdigest()
pelt.NATIVE_NAMES=before.co_names;pelt.NATIVE_VARS=before.co_varnames;pelt.NATIVE_CONSTS=before.co_consts
def wrap(native):
    def existing_wrapper(self,kind,generate_new=False):return native(self,kind,generate_new=generate_new)
    existing_wrapper.__wrapped__=native
    return existing_wrapper
outer=wrap(original);Tracker._generate_sim_info=outer
receipt=pelt.install(Tracker);assert receipt['installed'],receipt
after=original.__code__;assert Tracker._generate_sim_info is outer and original.__defaults__==defaults
assert after.co_consts==before.co_consts and after.co_varnames==before.co_varnames and after.co_lnotab==before.co_lnotab
assert after.co_names==before.co_names+(pelt.HELPER,) and len(after.co_code)==len(before.co_code)
changed=[i for i,(a,b) in enumerate(zip(before.co_code,after.co_code)) if a!=b]
assert changed and max(changed)-min(changed)<16
assert pelt.install(Tracker)['installed'] and original.__code__ is after
for mask in (127,33,65):
    for kind in (32,64):
        tracker=Tracker(mask);human=tracker._sim_info_map[1];generated=tracker._generate_sim_info(kind,generate_new=True)
        assert tracker.calls==1 and tracker._sim_info_map[kind] is generated
        assert generated.pelt_layers==b'new generated paint'
        assert human.pelt_layers==(b'nonempty authored Human' if mask==127 else b'new generated paint')
        assert tracker._apex_native_pelt_policy['human_write_suppressed']==(mask==127)
# Unknown native code cannot be replaced, even through an existing wrapper.
class Foreign:
    def _generate_sim_info(self,kind,generate_new=False):return kind
saved=Foreign._generate_sim_info.__code__
assert not pelt.install(Foreign)['installed'] and Foreign._generate_sim_info.__code__ is saved
print('wordcode preservation and scoped generation passed')
