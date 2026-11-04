from pathlib import Path
import sys
import unittest
from types import SimpleNamespace as Obj
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Source'))
import td1_occult_hybrid_apex as backend


class OutfitList:
    def ParseFromString(self,raw):self.raw=raw
    def SerializeToString(self):return self.raw


class StoredOutfitRestoreTests(unittest.TestCase):
    def test_stored_owner_without_mixin_serializer_is_captured_and_restored(self):
        before=b'\x0a\x04\x08\x01\x10\x00'
        after=b'\x0a\x04\x08\x02\x10\x05'
        owner=Obj(id=123,_base=Obj(outfits=before))
        captured=backend._snapshot_siminfo_payload(owner)
        self.assertEqual(captured['__outfits__'],('protobuf',before))
        modules={'protocolbuffers':Obj(Outfits_pb2=Obj(OutfitList=OutfitList))}
        with patch.dict(sys.modules,modules):
            self.assertTrue(backend._restore_siminfo_payload(owner,{'__outfits__':('protobuf',after)}))
        self.assertEqual(owner._base.outfits,after)
        self.assertIsNone(backend._APEX_APPEARANCE_RESTORE_DIAGNOSTICS['123']['outfit_assignment_error'])

    def test_native_outfit_loader_errors_are_retained_for_the_readback_failure(self):
        def fail(message):raise ValueError('Native outfit rejection')
        owner=Obj(id=124,load_outfits=fail)
        modules={'protocolbuffers':Obj(Outfits_pb2=Obj(OutfitList=OutfitList))}
        with patch.dict(sys.modules,modules):
            self.assertFalse(backend._restore_siminfo_payload(owner,{'__outfits__':('protobuf',b'\x0a\x04\x08\x01\x10\x00')}))
        self.assertEqual(backend._APEX_APPEARANCE_RESTORE_DIAGNOSTICS['124']['outfit_assignment_error'],'Native outfit rejection')
