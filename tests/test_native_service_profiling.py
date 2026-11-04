"""Only explicit scoped diagnostics may enable engine-service measurement."""
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Source'))
from apex_core.native_cas_engine import argument


class NativeServiceProfilingTests(unittest.TestCase):
    def test_explicit_scope_and_bounded_integer_duration(self):
        for duration in [0,1,15000,30000]:
            argument(dict(operation='profile-services',scope_id='a'*32,milliseconds=duration))
        for duration in [-1,30001,True,False,'1000',1.5,None]:
            with self.subTest(duration=duration):
                with self.assertRaises(ValueError):argument(dict(operation='profile-services',scope_id='a'*32,milliseconds=duration))
        for scope in ['',None,'b'*31,'foreign-scope']:
            with self.assertRaises(ValueError):argument(dict(operation='profile-services',scope_id=scope,milliseconds=1000))


if __name__ == '__main__':unittest.main()
