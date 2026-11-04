"""Test bridge only: invoke independently obtained s4py on synthetic inputs."""
import json
import sys
import types

# s4py imports PyYAML only to register a YAML representer. Index reading does
# not use YAML; this narrow stub avoids installing a dependency into the host.
stub = types.ModuleType('yaml')
stub.add_representer = lambda *args: None
sys.modules['yaml'] = stub
sys.path.insert(0, sys.argv[1])
from s4py.package.dbpf import _DbpfReader

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
