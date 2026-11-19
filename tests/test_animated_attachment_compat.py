import functools
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
import weakref
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Source'))
from apex_core import animated_attachment_compat as compat


def fixture():
    calls=[]
    sim=SimpleNamespace(is_sim=True,sim_info=SimpleNamespace(id=42),current_object_set_as_head=None,
                        appearance='unchanged',animation='unchanged')
    class Obj:
        def __init__(self,tags=()):self.tags=tags;self.parent=None;self.component=None;self.animation='own-asm'
        def get_tags(self):return self.tags
        def has_component(self,kind):return self.component is not None
        def get_component(self,kind):return self.component
        @property
        def is_set_as_head(self):
            return self.parent is not None and self.parent.current_object_set_as_head is not None and self.parent.current_object_set_as_head() is self
    class Set:
        bone_name=7
        def apply(self,obj,parent):
            calls.append('apply')
            if parent.current_object_set_as_head is not None and parent.current_object_set_as_head() is not None:return False
            Set.set_head_object(parent,obj,self.bone_name)
        @classmethod
        def set_head_object(cls,parent,obj,bone_hash):
            calls.append('set');parent.current_object_set_as_head=weakref.ref(obj);obj.parent=parent
            if getattr(obj,'fail',False):raise RuntimeError('native setter failed')
            obj.component=Comp(obj,parent.sim_info.id,bone_hash)
    class Unset:
        def apply(self,obj,parent):
            calls.append('unset')
            if parent.current_object_set_as_head is None or parent.current_object_set_as_head() is not obj:return False
            obj.parent=None;obj.component=None;parent.current_object_set_as_head=None
    class Comp:
        def __init__(self,owner,sid,bone):self.owner=owner;self._parent_sim_info_id=sid;self.bone=bone;self.fail=False
        def _reparent_object(self):
            calls.append('reparent')
            if self.fail:
                self.owner.component=None;sim.current_object_set_as_head=None;return
            Set.set_head_object(sim,self.owner,self.bone)
    pins={key:compat.code_hash(fn.__code__) for key,fn in dict(apply=Set.apply,setter=vars(Set)['set_head_object'].__func__,
        unset=Unset.apply,head=Obj.is_set_as_head.fget,reparent=Comp._reparent_object).items()}
    return SimpleNamespace(sim=sim,Obj=Obj,Set=Set,Unset=Unset,Comp=Comp,pins=pins,calls=calls)


class AttachmentCompatibilityTests(unittest.TestCase):
    def setUp(self):self.f=fixture()
    def install(self):
        f=self.f;return compat.bind(f.Set,f.Unset,f.Obj,f.Comp,'head',lambda c:f.sim,f.pins)
    def attach_ordinary_head(self):
        f=self.f;head=f.Obj();f.Set().apply(head,f.sim);return head
    def test_both_animated_parts_keep_the_real_head_and_their_native_components(self):
        f=self.f;head=self.attach_ordinary_head();self.assertTrue(self.install())
        tail=f.Obj([1298798044]);wing=f.Obj([4119383130])
        for obj in (tail,wing):f.Set().apply(obj,f.sim)
        self.assertIs(f.sim.current_object_set_as_head(),head)
        for obj in (tail,wing):
            self.assertIs(obj.parent,f.sim);self.assertTrue(obj.is_set_as_head)
            self.assertEqual(obj.component._parent_sim_info_id,42);self.assertEqual(obj.component.bone,7)
            self.assertEqual(obj.animation,'own-asm')
        self.assertEqual(f.calls.count('set'),3)
        self.assertEqual((f.sim.appearance,f.sim.animation),('unchanged','unchanged'))
    def test_removing_one_tagged_part_preserves_the_other_and_ordinary_head(self):
        f=self.f;head=self.attach_ordinary_head();self.install()
        tail=f.Obj([1298798044]);wing=f.Obj([4119383130])
        for obj in (tail,wing):f.Set().apply(obj,f.sim)
        f.Unset().apply(tail,f.sim)
        self.assertIsNone(tail.parent);self.assertIsNone(tail.component)
        self.assertIs(wing.parent,f.sim);self.assertTrue(wing.is_set_as_head)
        self.assertIs(f.sim.current_object_set_as_head(),head);self.assertEqual(f.calls.count('unset'),1)
    def test_saved_parts_reparent_without_reserving_the_global_head_slot(self):
        f=self.f;head=self.attach_ordinary_head();self.install()
        for tag in compat.TAGS:
            obj=f.Obj([tag]);comp=f.Comp(obj,42,99);obj.component=comp;comp._reparent_object()
            self.assertIs(obj.parent,f.sim);self.assertTrue(obj.is_set_as_head)
            self.assertIs(f.sim.current_object_set_as_head(),head)
        self.assertEqual(f.calls.count('reparent'),2)
    def test_failed_native_reparent_does_not_clear_an_unrelated_head(self):
        f=self.f;head=self.attach_ordinary_head();self.install();obj=f.Obj([1298798044])
        comp=f.Comp(obj,42,7);comp.fail=True;comp._reparent_object()
        self.assertIs(f.sim.current_object_set_as_head(),head);self.assertEqual(f.calls.count('reparent'),1)
    def test_setter_exception_is_not_replayed_and_restores_the_previous_reference(self):
        f=self.f;head=self.attach_ordinary_head();self.install();obj=f.Obj([4119383130]);obj.fail=True
        with self.assertRaises(RuntimeError):f.Set().apply(obj,f.sim)
        self.assertIs(f.sim.current_object_set_as_head(),head);self.assertEqual(f.calls.count('set'),2)
    def test_unrelated_objects_keep_native_single_head_behavior(self):
        f=self.f;head=self.attach_ordinary_head();self.install();other=f.Obj([12345])
        self.assertIs(f.Set().apply(other,f.sim),False);self.assertIsNone(other.parent)
        self.assertIs(f.sim.current_object_set_as_head(),head);self.assertEqual(f.calls.count('set'),1)
    def test_foreign_parent_or_missing_component_is_not_reported_as_attached(self):
        f=self.f;self.install();obj=f.Obj([1298798044]);obj.parent=f.sim
        self.assertFalse(obj.is_set_as_head);obj.component=f.Comp(obj,43,7);self.assertFalse(obj.is_set_as_head)
    def test_unknown_code_refuses_every_hook_before_mutation(self):
        f=self.f;original=(f.Set.apply,vars(f.Set)['set_head_object'],f.Obj.is_set_as_head,f.Comp._reparent_object)
        f.pins['head']='0'*64;self.assertFalse(self.install())
        self.assertEqual(original,(f.Set.apply,vars(f.Set)['set_head_object'],f.Obj.is_set_as_head,f.Comp._reparent_object))
    def test_existing_other_mod_wrapper_runs_once_and_repeated_install_does_not_stack(self):
        f=self.f;original=f.Set.apply
        @functools.wraps(original)
        def other_mod(*args):f.calls.append('other-mod');return original(*args)
        f.Set.apply=other_mod;self.install();installed=f.Set.apply;self.assertTrue(self.install());self.assertIs(f.Set.apply,installed)
        f.Set().apply(f.Obj([4119383130]),f.sim)
        self.assertEqual(f.calls.count('other-mod'),1);self.assertEqual(f.calls.count('set'),1)

if __name__=='__main__':unittest.main()
