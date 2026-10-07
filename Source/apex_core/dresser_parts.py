"""Authorized MCCC 2026.5.0 DresserOutfitObject helper port.

Deaderpool's add_part_shift/remove_body_type/get_part_id/get_color_shift behavior
was traced from the exact mc_utils.pyc instructions (see provenance). This port
adds alignment/range checks, owns its state, and never imports or hooks MCCC.
"""
NEUTRAL_SHIFT = 4611686018427387904  # Exact MCCC fallback; not an HSV decoder.


def uint(value, bits):
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < (1 << bits):
        raise ValueError('Expected an unsigned {}-bit integer.'.format(bits))
    return value


class DresserParts:
    def __init__(self, body_types, part_ids, color_shifts):
        self._body_types = [uint(value, 32) for value in body_types]
        self._part_ids = [uint(value, 64) for value in part_ids]
        self._color_shifts = [uint(value, 64) for value in color_shifts]
        if len(self._body_types) != len(self._part_ids) or len(self._color_shifts) != len(self._part_ids):
            raise ValueError('Ambiguous parallel outfit arrays; no parts/colors were changed.')
        if len(set(self._body_types)) != len(self._body_types):
            raise ValueError('Duplicate body types require layered-part targeting.')

    def add_part_shift(self, body_type, part_id, color_shift):
        body_type, part_id, color_shift = uint(body_type, 32), uint(part_id, 64), uint(color_shift, 64)
        if body_type in self._body_types:
            index = self._body_types.index(body_type)
            if self._part_ids[index] == part_id and self._color_shifts[index] == color_shift:
                return False
            self._part_ids[index] = part_id
            self._color_shifts[index] = color_shift
        else:
            self._body_types.append(body_type)
            self._part_ids.append(part_id)
            self._color_shifts.append(color_shift)
        return True

    def remove_body_type(self, body_type):
        if body_type not in self._body_types:
            return False
        index = self._body_types.index(body_type)
        del self._part_ids[index]
        del self._color_shifts[index]
        self._body_types.remove(body_type)
        return True

    def get_part_id(self, body_type):
        if body_type not in self._body_types:
            return 0
        return self._part_ids[self._body_types.index(body_type)]

    def get_color_shift(self, body_type):
        if body_type not in self._body_types:
            return 0
        return self._color_shifts[self._body_types.index(body_type)]


ARRAY_FIELDS = (('id', 'parts', 'ids', 64), ('body_type', 'body_types_list', 'body_types', 32),
                ('color_shift', 'part_shifts', 'color_shift', 64),
                ('object_id', 'object_ids', 'object_id', 64), ('layer_id', 'layer_ids', 'layer_id', 32))


def read_rows(outfit):
    arrays = {key: list(getattr(getattr(outfit, outer), inner)) for key, outer, inner, _ in ARRAY_FIELDS}
    count = len(arrays['id'])
    if len(arrays['body_type']) != count or count > 4096:
        raise ValueError('Outfit part/body-type arrays are misaligned or exceed the bound.')
    for key, _, _, _ in ARRAY_FIELDS[2:]:
        if len(arrays[key]) not in (0, count):
            raise ValueError('Ambiguous {} array; refusing silent padding/truncation.'.format(key))
    return [{key: uint(arrays[key][index], bits) if arrays[key] else None
             for key, _, _, bits in ARRAY_FIELDS} for index in range(count)]


def write_rows(outfit, rows):
    rows = list(rows)
    if len(rows) > 4096:
        raise ValueError('Too many parts.')
    prepared = {}
    for key, outer, inner, bits in ARRAY_FIELDS:
        values = [row[key] for row in rows]
        if key in ('id', 'body_type') or any(value is not None for value in values):
            if any(value is None for value in values):
                raise ValueError('Mixed absent/present {} values require an explicit compatible conversion.'.format(key))
            values = [uint(value, bits) for value in values]
        else:
            values = []
        prepared[(outer, inner)] = values
    targets = {key: getattr(getattr(outfit, key[0]), key[1]) for key in prepared}
    originals = {key: list(value) for key, value in targets.items()}
    try:
        for key, target in targets.items():
            del target[:]
            target.extend(prepared[key])
    except Exception:
        for key, target in targets.items():
            del target[:]
            target.extend(originals[key])
        raise
    # Keep row order, absent arrays and unknown composite protobuf fields.
    return len(rows)
