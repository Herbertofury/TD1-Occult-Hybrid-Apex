import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import dbpf_build
import slider_catalog as catalog
from source_manifest import write_json, sha256


def hotc(version=15, ids=(123,456,0,0)):
    raw=struct.pack('<II',version,0x2078)
    if version>=14: raw+=struct.pack('<I',1)
    if version>=15: raw+=struct.pack('<I',2)
    raw+=struct.pack('<BBBI',0,100,1,4)
    if version>=14: raw+=struct.pack('<IB',8,0)
    return raw+struct.pack('<QIBBBffQQQQ',10,0,1,7,0,1,1,*ids)


def smod(version=144):
    body=struct.pack('<III',version,0x2078,4)
    if version>=144: body+=struct.pack('<I',8)
    body+=struct.pack('<I',0)+b'\0'*48+struct.pack('<IIf',1,321,.5)
    return struct.pack('<IIIII',3,0,0,0,1)+struct.pack('<II',28,len(body))+body


class SliderCatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
    def package(self,name,resources,origin='mod'):
        path=self.root/name;path.write_bytes(dbpf_build.build(resources));return path,origin
    def test_old_and_current_hotspots_keep_each_direction_uint64_and_filters(self):
        for version in (11,12,14,15):
            row=catalog.hotspot(hotc(version,ids=(2**64-1,456,0,0)))
            self.assertEqual(row['views'][0]['directions']['left'],str(2**64-1))
            self.assertEqual(row['occult'],2 if version==15 else None)
            self.assertEqual(row['species'],None if version<14 else 1)
    def test_modifier_versions_and_all_deformation_references_remain_explicit(self):
        for version in (112,128,144):
            row=catalog.sim_modifier(smod(version));self.assertEqual(row['bones'],[dict(bone_hash=321,multiplier=.5)])
            self.assertFalse(row['native_bounds_verified'])
            self.assertEqual(len(row['referenced_resources']),3)
    def test_truncation_future_versions_and_unexplained_bytes_are_not_guessed(self):
        for function,raw in ((catalog.hotspot,hotc()),(catalog.sim_modifier,smod())):
            for invalid in (raw[:-1],raw+b'\0'):
                with self.assertRaises(ValueError):function(invalid)
        with self.assertRaises(ValueError):catalog.hotspot(struct.pack('<I',99)+hotc()[4:])
    def test_distinct_modifiers_remain_visible_under_colliding_hotspot_with_no_winner_claim(self):
        sources=[self.package('a.package',{(catalog.HOTC,0,10):hotc(ids=(123,0,0,0)),(catalog.SMOD,0,123):smod()}),
                 self.package('b.package',{(catalog.HOTC,0,10):hotc(ids=(456,0,0,0)),(catalog.SMOD,0,456):smod()})]
        result=catalog.build(sources)
        hotspot=[r for r in result['resources'] if r['kind']=='hotspot'][0]
        self.assertEqual(hotspot['conflict'],'conflicting-mod-definitions')
        modifiers=[r for r in result['resources'] if r['kind']=='modifier']
        self.assertEqual({r['instance'] for r in modifiers},{'123','456'})
        self.assertTrue(all(r['hotspot_bindings'][0]['hotspot_conflict']=='conflicting-mod-definitions' for r in modifiers))
        self.assertTrue(all(not r['effective_load_source_verified'] for r in modifiers))
    def test_identical_resource_duplicates_do_not_label_whole_packages_redundant(self):
        result=catalog.build([self.package('a.package',{(catalog.SMOD,0,123):smod()}),self.package('b.package',{(catalog.SMOD,0,123):smod(),(catalog.PRESET,0,99):b'other'})])
        modifier=[r for r in result['resources'] if r['kind']=='modifier'][0]
        self.assertEqual(modifier['conflict'],'identical-mod-definitions')
        self.assertEqual(len(result['resources']),2)
    def test_ea_override_and_distinct_ea_definitions_are_not_mod_conflict(self):
        ea=dict(origin='ea',resource_sha256='a');mod=dict(origin='mod',resource_sha256='b')
        self.assertEqual(catalog.classify([ea,mod]),'ea-override-candidate')
        self.assertEqual(catalog.classify([ea,dict(origin='ea',resource_sha256='b')]),'competing-ea-definitions')
    def test_sealed_query_searches_package_and_refuses_wrong_hash_or_unbounded_input(self):
        result=catalog.build([self.package('[Author] face.package',{(catalog.SMOD,0,123):smod()})])
        path=self.root/'catalog.json';write_json(path,result);index=catalog.Catalog(path,sha256(path))
        q=dict(search='author',kind='modifier',offset=0,limit=25,conflicts_only=False)
        self.assertEqual(index.query(q)['total'],1)
        for update in (dict(limit=101),dict(offset=True),dict(search='x'*201),dict(extra=1),dict(conflicts_only=1)):
            with self.assertRaises(ValueError):index.query(dict(q,**update))
        with self.assertRaises(ValueError):catalog.Catalog(path,'0'*64)


if __name__=='__main__':unittest.main()
