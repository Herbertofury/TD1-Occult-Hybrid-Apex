"""Complete native Sim save-model export and schema catalog.

Every declared field remains visible, including absent fields. Exact native
bytes retain unknown/extension fields. This is not arbitrary Python execution
or permission to reload a live Sim through unvalidated raw protobuf writes.
"""
import base64
import hashlib
import json
import math

TYPE_NAMES = {1: 'double', 2: 'float', 3: 'int64', 4: 'uint64', 5: 'int32', 6: 'fixed64',
              7: 'fixed32', 8: 'bool', 9: 'string', 10: 'group', 11: 'message', 12: 'bytes',
              13: 'uint32', 14: 'enum', 15: 'sfixed32', 16: 'sfixed64', 17: 'sint32', 18: 'sint64'}
INTEGER_TYPES = (3, 4, 5, 6, 7, 13, 15, 16, 17, 18)


def scalar(field, value, visit):
    if field.type in (10, 11):
        return visit(value)
    if field.type == 12:
        return {'encoding': 'base64', 'value': base64.b64encode(bytes(value)).decode('ascii')}
    if field.type in INTEGER_TYPES:
        return str(int(value))  # JS cannot represent uint64 without loss.
    if field.type == 14:
        number = int(value)
        item = field.enum_type.values_by_number.get(number)
        return {'number': number, 'name': item.name if item else None}
    if field.type in (1, 2) and not math.isfinite(value):
        return {'special_float': str(value)}
    if isinstance(value, (str, bool, float)):
        return value
    raise ValueError('Unsupported protobuf scalar; exact bytes must not be silently lost.')


def catalog(message):
    nodes = [0]
    schemas = {}

    def schema(descriptor):
        if descriptor.full_name in schemas:
            return
        if len(schemas) >= 2048:
            raise ValueError('Sim schema catalog exceeds its bound.')
        rows = []
        schemas[descriptor.full_name] = rows
        for field in descriptor.fields:
            row = {'name': field.name, 'number': field.number, 'type': TYPE_NAMES[field.type],
                   'repeated': field.label == 3,
                   'owner_edit_handler': None, 'editable_now': False}
            if field.message_type is not None:
                row['message_type'] = field.message_type.full_name
                schema(field.message_type)
            if field.enum_type is not None:
                row['enum_values'] = {str(key): value.name for key, value in field.enum_type.values_by_number.items()}
            rows.append(row)

    def visit(value, depth=0):
        if depth > 32:
            raise ValueError('Sim data nesting exceeds its bound; no partial export was accepted.')
        nodes[0] += 1
        if nodes[0] > 100000:
            raise ValueError('Sim data field count exceeds its bound; no fields were silently omitted.')
        descriptor = value.DESCRIPTOR
        schema(descriptor)
        present = {field.number: (field, item) for field, item in value.ListFields()}
        fields = []
        for field in descriptor.fields:
            item = present.pop(field.number, None)
            row = {'name': field.name, 'number': field.number, 'present': item is not None}
            if item is not None:
                convert = lambda nested: visit(nested, depth + 1)
                row['value'] = ([scalar(field, child, convert) for child in item[1]]
                                if field.label == 3 else scalar(field, item[1], convert))
            fields.append(row)
        for field, item in present.values():
            fields.append({'name': field.full_name, 'number': field.number, 'present': True, 'extension': True,
                           'value': [scalar(field, child, lambda nested: visit(nested, depth + 1)) for child in item]
                           if field.label == 3 else scalar(field, item, lambda nested: visit(nested, depth + 1))})
        return {'message_type': descriptor.full_name, 'fields': fields}

    raw = message.SerializeToString()
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError('Native Sim snapshot exceeds its transport bound; no partial export was accepted.')
    tree = visit(message)
    result = {'schema': 1, 'native_message_type': message.DESCRIPTOR.full_name,
              'native_sha256': hashlib.sha256(raw).hexdigest(), 'native_bytes': len(raw),
              'native_base64': base64.b64encode(raw).decode('ascii'), 'data': tree,
              'field_schemas': schemas, 'unknown_fields_retained_in_native_bytes': True,
              'runtime_only_fields_complete': False,
              'scope': 'Complete native Sim save-model bytes and every declared schema field; runtime-only owners and editing handlers remain unfinished.'}
    if len(json.dumps(result, ensure_ascii=True, allow_nan=False).encode('utf-8')) > 7 * 1024 * 1024:
        raise ValueError('Complete catalog exceeds bridge capacity; no truncated catalog was accepted.')
    return result


def snapshot(backend, sim):
    if sim is None:
        raise ValueError('Select a Sim for complete data capture.')
    # Inspected exact 1.128.90 save_sim/_save_sim_base contracts. The real game's
    # full serializer refreshes its in-memory persistence record; it does not
    # write a save file or load/reconstruct an instanced Sim.
    message = sim.save_sim(for_cloning=False, full_service=True)
    result = catalog(message)
    result.update({'sim_id': str(sim.id), 'save_guid': str(backend.services.get_persistence_service().get_save_slot_proto_guid()),
                   'native_serializer_called': True, 'save_file_written': False})
    return result
