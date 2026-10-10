"""Fail-closed x64 PE import validation for the Apex DX11 proxy.

Reads normal and delay-import tables; arbitrary strings are not import evidence.
No executable is loaded or run. Dynamic imports and hooking require runtime proof.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

SUPPORTED = {'D3D11CreateDevice', 'D3D11CreateDeviceAndSwapChain'}


class PEError(ValueError):
    pass


class PE:
    def __init__(self, data):
        self.data = data
        if self.take(0, 2) != b'MZ':
            raise PEError('Not a DOS/PE image.')
        pe = self.unpack('<I', 0x3c)[0]
        if self.take(pe, 4) != b'PE\0\0':
            raise PEError('PE signature missing.')
        machine, count = self.unpack('<HH', pe + 4)
        if machine != 0x8664 or not 1 <= count <= 96:
            raise PEError('Expected an x64 PE with a bounded section table.')
        optional_size = self.unpack('<H', pe + 20)[0]
        optional = pe + 24
        self.take(optional, optional_size)
        if optional_size < 112 or self.unpack('<H', optional)[0] != 0x20b:
            raise PEError('Expected a PE32+ optional header.')
        self.image_base = self.unpack('<Q', optional + 24)[0]
        self.header_size = self.unpack('<I', optional + 60)[0]
        directories = self.unpack('<I', optional + 108)[0]
        if directories > 16 or 112 + directories * 8 > optional_size:
            raise PEError('Invalid data-directory table.')
        self.directories = [self.unpack('<II', optional + 112 + index * 8) for index in range(directories)]
        self.sections = []
        for index in range(count):
            section = optional + optional_size + index * 40
            self.take(section, 40)
            virtual_size, virtual, raw_size, raw = self.unpack('<IIII', section + 8)
            self.take(raw, raw_size)
            self.sections.append((virtual, raw_size, raw, virtual_size))

    def take(self, offset, size):
        if offset < 0 or size < 0 or offset + size > len(self.data):
            raise PEError('Truncated or out-of-bounds PE field.')
        return self.data[offset:offset + size]

    def unpack(self, format_, offset):
        return struct.unpack(format_, self.take(offset, struct.calcsize(format_)))

    def offset(self, rva, size=1):
        if 0 <= rva < self.header_size and rva + size <= self.header_size:
            self.take(rva, size)
            return rva
        matches = [raw + rva - virtual for virtual, length, raw, _ in self.sections
                   if virtual <= rva and rva + size <= virtual + length]
        if len(matches) != 1:
            raise PEError('Unmapped, ambiguous or zero-filled RVA: {}'.format(hex(rva)))
        self.take(matches[0], size)
        return matches[0]

    def string(self, rva):
        value = bytearray()
        for index in range(1024):
            char = self.data[self.offset(rva + index)]
            if char == 0:
                try:
                    return value.decode('ascii')
                except UnicodeDecodeError:
                    raise PEError('Non-ASCII import name.')
            value.append(char)
        raise PEError('Import name exceeds bounded length.')

    def thunks(self, rva, va_based=False):
        names = []
        for index in range(65536):
            pointer = self.unpack('<Q', self.offset(rva + index * 8, 8))[0]
            if pointer == 0:
                return names
            if pointer & (1 << 63):
                names.append({'ordinal': pointer & 0xffff})
            else:
                name_rva = pointer - self.image_base if va_based else pointer
                self.offset(name_rva, 2)
                names.append(self.string(name_rva + 2))
        raise PEError('Import thunk table exceeds bounded length.')

    def imports(self):
        rows = []
        for entry, stride, delayed in ((1, 20, False), (13, 32, True)):
            if entry >= len(self.directories):
                continue
            rva, size = self.directories[entry]
            if not rva and not size:
                continue
            if not rva or size < stride or size > 1024 * 1024:
                raise PEError('Invalid import directory extent.')
            terminated = False
            for index in range(min(size // stride, 4096)):
                descriptor = self.take(self.offset(rva + index * stride, stride), stride)
                if not any(descriptor):
                    terminated = True
                    break
                if delayed:
                    attrs, name, _, iat, lookup, _, _, _ = struct.unpack('<8I', descriptor)
                    if attrs & ~1:
                        raise PEError('Unsupported delay-import attributes.')
                    va_based = not (attrs & 1)
                    if va_based:
                        name -= self.image_base
                        lookup = (lookup or iat) - self.image_base
                    else:
                        lookup = lookup or iat
                else:
                    lookup, _, _, name, iat = struct.unpack('<5I', descriptor)
                    lookup = lookup or iat
                    va_based = False
                if not name or not lookup:
                    raise PEError('Missing import name/lookup table.')
                rows.append({'dll': self.string(name), 'delay_load': delayed,
                             'symbols': self.thunks(lookup, va_based)})
            if not terminated:
                raise PEError('Unterminated import descriptors.')
        return rows


def verify(data):
    imports = PE(data).imports()
    d3d = [row for row in imports if row['dll'].lower() == 'd3d11.dll']
    symbols = [symbol for row in d3d for symbol in row['symbols']]
    unsupported = [symbol for symbol in symbols if not isinstance(symbol, str) or symbol not in SUPPORTED]
    if not symbols:
        raise PEError('No D3D11 import surface found; this proxy cannot be validated for this executable.')
    if unsupported:
        raise PEError('Proxy does not forward these D3D11 imports: {}'.format(unsupported))
    return {'ok': True, 'machine': 'x64', 'sha256': hashlib.sha256(data).hexdigest(),
            'd3d11_imports': d3d, 'supported_proxy_exports': sorted(SUPPORTED),
            'proof_scope': 'PE import coverage only; dynamic GetProcAddress and live hooking require runtime proof.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('executable', type=Path)
    args = parser.parse_args(argv)
    try:
        result = verify(args.executable.read_bytes())
        result['file'] = str(args.executable.resolve())
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, PEError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
