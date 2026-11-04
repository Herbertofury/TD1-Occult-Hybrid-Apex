# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded source-over atlas comparison for private CAS diagnostics.

Counts only. Does not establish native-game behavior, geometry visibility,
material fidelity, or whether an item should be displayed as equipped.
"""
import argparse
import json
import os
import stat
import numpy as np

CHUNK_PIXELS = 131072
MAX_BYTES = 64 * 1024 * 1024


def _source_over(dst, rgba):
    """Match the preview's integer RGBA source-over on an opaque RGB base."""
    src = rgba.astype(np.uint32)
    alpha = src[:, 3:4]
    return ((src[:, :3] * alpha + dst * (255 - alpha) + 127) // 255)


def compare_chunks(base, old, new, upper):
    """Compare one or more equally sized RGBA chunks, returning only counts."""
    arrays = [base, old, new, *upper]
    if not arrays or any(not isinstance(x, bytes) for x in arrays):
        raise ValueError('byte buffers required')
    if not 0 < len(base) <= CHUNK_PIXELS * 4 or len(base) % 4 or any(len(x) != len(base) for x in arrays):
        raise ValueError('RGBA chunk extent mismatch')
    arrays = [np.frombuffer(x, dtype=np.uint8).reshape(-1, 4) for x in arrays]
    base, old, new, *upper = arrays
    if np.any(base[:, 3] != 255):
        raise ValueError('base must be opaque')
    before = _source_over(base[:, :3].astype(np.uint32), old)
    after = _source_over(base[:, :3].astype(np.uint32), new)
    changed = np.any(before != after, axis=1)
    initially_changed = int(np.count_nonzero(changed))
    opaque_cover = np.zeros(len(base), dtype=bool)
    counts = []
    for layer in upper:
        opaque_cover |= layer[:, 3] == 255
        before = _source_over(before, layer)
        after = _source_over(after, layer)
        counts.append(int(np.count_nonzero(np.any(before != after, axis=1))))
    return {'pixels': len(base), 'initially_changed': initially_changed,
            'initial_changes_under_opaque_upper': int(np.count_nonzero(changed & opaque_cover)),
            'changed_after_each_upper': counts,
            'final_changed': int(np.count_nonzero(np.any(before != after, axis=1)))}


def compare_streams(streams):
    if len(streams) < 3 or len(streams) > 67:
        raise ValueError('base, two candidates, and at most 64 upper layers required')
    total = None
    while True:
        blocks = [stream.read(CHUNK_PIXELS * 4) for stream in streams]
        if not any(blocks):
            break
        result = compare_chunks(blocks[0], blocks[1], blocks[2], blocks[3:])
        if total is None:
            total = result
        else:
            for key in ('pixels', 'initially_changed', 'initial_changes_under_opaque_upper', 'final_changed'):
                total[key] += result[key]
            total['changed_after_each_upper'] = [a + b for a, b in zip(total['changed_after_each_upper'], result['changed_after_each_upper'])]
        if total['pixels'] * 4 > MAX_BYTES:
            raise ValueError('atlas exceeds budget')
    if total is None:
        raise ValueError('empty atlas')
    return total


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base', required=True)
    p.add_argument('--old', required=True)
    p.add_argument('--new', required=True)
    p.add_argument('--upper', action='append', default=[])
    a = p.parse_args()
    paths = [a.base, a.old, a.new, *a.upper]
    files = []
    try:
        for path in paths:
            # Reject symlinks where the OS supports O_NOFOLLOW. This is not a hostile-filesystem sandbox.
            fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
            f = os.fdopen(fd, 'rb'); files.append(f)
            s = os.fstat(f.fileno())
            if not stat.S_ISREG(s.st_mode) or not 0 < s.st_size <= MAX_BYTES or s.st_size % 4:
                raise ValueError('bounded RGBA regular file required')
        if len({os.fstat(f.fileno()).st_size for f in files}) != 1:
            raise ValueError('atlas extent mismatch')
        result = compare_streams(files)
        result['scope'] = 'atlas composition only; native fidelity and geometry visibility unverified'
        print(json.dumps(result, sort_keys=True))
    finally:
        for f in files:
            f.close()

if __name__ == '__main__':
    main()
