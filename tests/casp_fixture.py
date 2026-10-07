"""Synthetic CASP protocol frames; no author/game resource bytes."""
import struct


def casp(version=52, body=7, step=0.05):
    name = 'Apex test part'.encode('utf-16-be')
    raw = bytearray(struct.pack('<IIi', version, 0, 0))
    raw += bytes([len(name)]) + name
    raw += struct.pack('<fHIIBB', 0, 0, 0, 0, 0, 0)
    if version >= 50:
        raw += struct.pack('<H', 17)
    if version >= 51:
        raw += struct.pack('<iQQ', 2, 123, 456)
    else:
        raw += struct.pack('<QQ', 123, 456)
    raw += struct.pack('<Q', 0)
    raw += struct.pack('<iHIHI', 2, 10, 123, 20, 456)
    raw += struct.pack('<IIIIBIIII', 0, 0, 0, 0, 0, body, 0, 0, 1)
    raw += bytes(12)
    raw += bytes([2]) + struct.pack('<II', 0xFF00FF00, 0xFF112233)
    raw += struct.pack('<BBQBIII', 0, 0, 0, 1, 0, 0, 0)
    raw += struct.pack('<I', 32)
    if version >= 46:
        raw += struct.pack('<Q', 0)
    raw += struct.pack('<QQ', 999, 888)
    raw += struct.pack('<11f', 0.2, step, -0.5, 0.5, step, -0.25, 0.75, step, -0.125, 0.875, step)
    struct.pack_into('<I', raw, 4, len(raw) - 8)
    raw += bytes([0])  # bounded reference-table sentinel, not a full renderable CASP
    return bytes(raw)
