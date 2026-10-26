"""Fresh Git checkout must reproduce the exact archive-authorizing sources."""
import ast
import hashlib
from pathlib import Path,PurePosixPath
import subprocess
import tempfile
import unittest


ROOT=Path(__file__).resolve().parents[1]


def authority():
    tree=ast.parse((ROOT/'Source/apex_core/form_bank_seal.py').read_bytes())
    values={node.targets[0].id:ast.literal_eval(node.value) for node in tree.body
            if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name)
            and node.targets[0].id in ('UPGRADE_MODULE_PINS','UPGRADE_SELF_BODY_SHA')}
    function=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='upgrade_source_hash')
    namespace={'hashlib':hashlib}
    exec(compile(ast.Module(body=[function],type_ignores=[]),'audited-upgrade-source-hash','exec'),namespace)
    pins=dict(values['UPGRADE_MODULE_PINS'],**{'apex_core/form_bank_seal.py':values['UPGRADE_SELF_BODY_SHA']})
    return pins,namespace['upgrade_source_hash']


def git(root,*args):
    return subprocess.check_output(['git','-C',str(root),*args],stderr=subprocess.PIPE)


class PinnedCheckoutTests(unittest.TestCase):
    def test_all_audited_sources_survive_clean_add_and_fresh_checkout(self):
        pins,digest=authority()
        for name in pins:
            self.assertFalse(PurePosixPath(name).is_absolute())
            self.assertFalse(set(PurePosixPath(name).parts)&{'..','.'})
            self.assertNotIn('\\',name);self.assertNotIn(':',name)
        sources={name:(ROOT/'Source'/name).read_bytes() for name in pins}
        for name,data in sources.items():
            self.assertEqual(digest(name,data),pins[name],'Working source needs its separately audited reseal: '+name)
        for autocrlf in ('false','true','input'):
            with self.subTest(autocrlf=autocrlf),tempfile.TemporaryDirectory(prefix='apex-pinned-checkout-') as temporary:
                checkout=Path(temporary)
                git(checkout,'init','--quiet')
                git(checkout,'config','core.autocrlf',autocrlf)
                git(checkout,'config','core.eol','lf')
                (checkout/'.gitattributes').write_bytes((ROOT/'.gitattributes').read_bytes())
                for name,data in sources.items():
                    target=checkout/'Source'/name
                    target.parent.mkdir(parents=True,exist_ok=True)
                    target.write_bytes(data)
                git(checkout,'add','--','.gitattributes','Source')
                for name in sources:
                    (checkout/'Source'/name).unlink()
                git(checkout,'checkout-index','--all','--force')
                for name in sources:
                    returned=(checkout/'Source'/name).read_bytes()
                    self.assertEqual(returned,sources[name],'Git altered audited archive bytes: '+name)
                    self.assertEqual(digest(name,returned),pins[name],'Fresh checkout lost archive authority: '+name)


if __name__=='__main__':unittest.main()
