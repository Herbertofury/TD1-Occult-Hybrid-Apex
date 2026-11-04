# SPDX-License-Identifier: GPL-3.0-or-later
"""Compare a bounded selection in an explicit package against s4py privately."""
import ctypes
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tracemalloc

from large_package import HASH_CHUNK, MAX_PACKAGE, MAX_PAYLOAD_BUDGET, PinnedPackage, payload_budget


def low_priority():
    if os.name == 'nt' and os.environ.get('CAS_LOW_PRIORITY') == '1':
        kernel = ctypes.windll.kernel32
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        kernel.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        if not kernel.SetPriorityClass(kernel.GetCurrentProcess(), 0x40):
            raise OSError('failed to lower comparison priority')


def pin(path):
    size = path.stat().st_size
    if size > MAX_PACKAGE: raise ValueError('package bound')
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(HASH_CHUNK), b''): digest.update(chunk)
    return digest.hexdigest()


def main():
    if len(sys.argv) != 2 or not os.environ.get('S4PY_ROOT') or not os.environ.get('S4PY_PYTHON'):
        raise ValueError('supply one explicit package and s4py environment')
    low_priority(); tracemalloc.start()
    path = pathlib.Path(sys.argv[1]); digest = pin(path)
    types = {0x034aeecb: 'casp', 0x015a1849: 'geom', 0x3453cf95: 'rle2', 0xba856c78: 'rles', 0x8eaf13de: 'rig'}
    with PinnedPackage(path, digest) as package:
        candidates = {kind: [] for kind in types}
        other = []
        for row in package.iter_rows():
            group = candidates.get(row.key[0])
            if not row.deleted and row.committed == 1 and row.compression in (0, 0x5a42, 0xffff):
                budget = payload_budget(row)
                if budget <= MAX_PAYLOAD_BUDGET:
                    if group is not None and len(group) < 8: group.append(row)
                    elif group is None and len(other) < 8: other.append(row)
        search = [row.key for rows in candidates.values() for row in rows] + [row.key for row in other]
        search = list(dict.fromkeys(search))
        if not search: raise ValueError('no eligible sample')
        resolved = package.resolve_many(search)
        chosen, budget = [], 0
        for type_id, rows in candidates.items():
            for row in rows:
                item_budget = payload_budget(row)
                if len(resolved[row.key]) == 1 and budget + item_budget <= MAX_PAYLOAD_BUDGET:
                    chosen.append(row); budget += item_budget; break
        if not chosen:
            for row in other:
                if len(resolved[row.key]) == 1:
                    chosen.append(row); budget = payload_budget(row); break
        if not chosen: raise ValueError('no unambiguous sample')
        payloads = package.read_many([row.key for row in chosen])
        bridge = pathlib.Path(__file__).with_name('s4py_oracle.py')
        comparisons = []
        for row in chosen:
            raw = subprocess.check_output([os.environ['S4PY_PYTHON'], '-B', str(bridge), os.environ['S4PY_ROOT'], '--record-and-payload', str(path), str(row.ordinal)], text=True)
            independent = json.loads(raw)
            actual = {'key': '{:08X}:{:08X}:{:016X}'.format(*row.key), 'offset': row.offset, 'storedSize': row.stored_size,
                      'memorySize': row.memory_size, 'compression': row.compression, 'committed': row.committed,
                      'decodedSha256': hashlib.sha256(payloads[row.key]).hexdigest()}
            comparisons.append({'role': types.get(row.key[0], 'other'), 'recordAndPayloadMatched': independent == actual, 'expandedBytes': row.memory_size})
        _, peak = tracemalloc.get_traced_memory()
        print(json.dumps({'packageBytes': package.source_size, 'indexRows': package.row_count, 'selected': comparisons,
                          'pythonPeakTracedBytes': peak, 'maximumIndividualRead': package.max_read,
                          'selectedPayloadAccountingBytes': budget, 'identity': 'whole-file-sha256-verified'}))


if __name__ == '__main__': main()
