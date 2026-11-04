"""Test bridge only: invoke independently obtained s4py on synthetic inputs."""
import json
import binascii
import hashlib
import sys
import types
import zlib

# s4py imports PyYAML only to register a YAML representer. Index reading does
# not use YAML; this narrow stub avoids installing a dependency into the host.
stub = types.ModuleType('yaml')
stub.add_representer = lambda *args: None
sys.modules['yaml'] = stub
sys.path.insert(0, sys.argv[1])
from s4py.package.dbpf import _DbpfReader, decodeRefPack

if sys.argv[2] == '--refpack':
    print(binascii.hexlify(bytes(decodeRefPack(bytes.fromhex(sys.argv[3])))).decode('ascii'))
elif sys.argv[2] == '--payload-hash':
    with open(sys.argv[3], 'rb') as handle:
        reader = _DbpfReader(handle)
        item = list(reader.get_index())[int(sys.argv[4])]
        method = item.locator.compression[0]
        if method not in (0, 0x5a42, 0xffff) or item.size > 64 * 1024 * 1024 or item.locator.raw_len > 64 * 1024 * 1024:
            raise ValueError('unsupported bounded sample')
        handle.seek(item.locator.offset)
        stored = handle.read(item.locator.raw_len)
        if len(stored) != item.locator.raw_len:
            raise ValueError('invalid sample extent')
        if method == 0xffff:
            if len(stored) < 5 or stored[1] != 0xfb:
                raise ValueError('invalid sample header')
            size_bytes = 4 if stored[0] & 0x80 else 3
            if int.from_bytes(stored[2:2 + size_bytes], 'big') != item.size:
                raise ValueError('sample size mismatch')
            decoded = bytes(decodeRefPack(stored))
        elif method == 0x5a42:
            decoder = zlib.decompressobj()
            decoded = decoder.decompress(stored, item.size + 1)
            if not decoder.eof or decoder.unconsumed_tail or decoder.unused_data:
                raise ValueError('invalid compressed sample')
        else:
            decoded = stored
        if len(decoded) != item.size:
            raise ValueError('decoded size mismatch')
        print(hashlib.sha256(decoded).hexdigest())
else:
    with open(sys.argv[2], 'rb') as handle:
        reader = _DbpfReader(handle)
        rows = []
        for resource in reader.get_index():
            rows.append({
                'key': '{:08X}:{:08X}:{:016X}'.format(resource.id.type, resource.id.group, resource.id.instance),
                'offset': resource.locator.offset,
                'storedSize': resource.locator.raw_len,
                'memorySize': resource.size,
                'compression': resource.locator.compression[0],
                'committed': resource.locator.compression[1],
                'deleted': resource.locator.deleted,
            })
        print(json.dumps(rows))
