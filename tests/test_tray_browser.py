import io
from pathlib import Path
import struct
import tempfile
import unittest
from PIL import Image
from unittest.mock import patch
from test_tray_library import wire
import tray_browser as gallery
import tray_library


class TrayGalleryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.folder=self.root/'Tray';self.folder.mkdir()
        self.item='0x00000001!0x00f51748712e0032.trayitem'
        payload=wire(2,1,0)+wire(4,b'Alien family')+wire(5,b'A native library household')+wire(7,b'Test creator')
        (self.folder/self.item).write_bytes(struct.pack('<II',0,len(payload))+payload)
        payload=wire(1,wire(3,b'Family')+wire(6,b'Native Sim'))
        (self.folder/'0x00000000!0x00f51748712e0032.householdbinary').write_bytes(struct.pack('<II',1,len(payload)+4)+payload)
        image=io.BytesIO();Image.new('RGB',(800,600),(210,50,80)).save(image,format='JPEG')
        jpg=image.getvalue();key=bytes.fromhex('4125e6cd47bab21a')
        self.encoded=struct.pack('<I',len(jpg))+bytes(20)+bytes(v^key[i%8] for i,v in enumerate(jpg))
        self.image=self.folder/'0x00000003!0x00f51748712e0032.hhi';self.image.write_bytes(self.encoded)
        self.g=gallery.Gallery(self.folder);self.q=dict(text='',kind='all',offset=0,limit=60)

    def test_names_creator_filter_native_image_and_source_bytes_unchanged(self):
        before={p.name:p.read_bytes() for p in self.folder.iterdir()}
        page=self.g.query(dict(self.q,text='alien creator',kind='household'))
        self.assertEqual(page['total'],1);item=page['items'][0];self.assertEqual((item['name'],item['creator'],item['sim_count']),('Alien family','Test creator',1))
        selected=dict(item_id=item['item_id'],library_sha256=self.g.expected)
        image=self.g.image(dict(selected,image_index=0));self.assertEqual((image['width'],image['height']),(512,384))
        projected=dict(ok=True,game_contacted=False,disk_assets_written=False,sims=[])
        with patch.object(tray_library,'inspect',return_value=projected):self.assertTrue(self.g.inspect(selected)['ok'])
        self.assertEqual({p.name:p.read_bytes() for p in self.folder.iterdir()},before)
        self.assertEqual(self.g.query(dict(self.q,kind='room'))['total'],0)

    def test_changed_or_wrong_snapshot_and_malformed_images_are_refused(self):
        selected=dict(item_id=self.g.items[0]['item_id'],library_sha256=self.g.expected)
        with self.assertRaises(ValueError):self.g.image(dict(selected,library_sha256='a'*64,image_index=0))
        for raw in (self.encoded[:-1],struct.pack('<I',999999)+self.encoded[4:],bytes(24)+b'junk'):
            with self.assertRaises(ValueError):gallery.thumbnail(raw)
        self.image.write_bytes(self.encoded+b'x')
        with self.assertRaisesRegex(ValueError,'source changed'):self.g.image(dict(selected,image_index=0))

    def test_duplicate_metadata_and_invalid_filters_are_not_guessed(self):
        payload=wire(4,b'One')+wire(4,b'Two')
        with self.assertRaises(ValueError):gallery.metadata(struct.pack('<II',0,len(payload))+payload)
        for q in (dict(self.q,limit=True),dict(self.q,kind='unknown'),dict(self.q,text='x'*201)):
            with self.assertRaises(ValueError):self.g.query(q)
