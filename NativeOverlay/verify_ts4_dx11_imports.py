#!/usr/bin/env python3
r"""TD1 Apex DX11 proxy preflight.

Run this on Windows before installing the generated d3d11.dll proxy:

    py verify_ts4_dx11_imports.py "C:\Path\To\The Sims 4\Game\Bin\TS4_x64.exe"

The current Apex proxy exports and intercepts D3D11CreateDevice and
D3D11CreateDeviceAndSwapChain. The script checks that the target Sims 4 binary
uses those DX11 entry points and warns if other d3d11 exports appear in the
binary strings, because that would mean the proxy source must be expanded before
installing.
"""
import os
import sys

REQUIRED = [b'D3D11CreateDevice', b'D3D11CreateDeviceAndSwapChain']
KNOWN_EXTRA = [
    b'D3D11CoreCreateDevice',
    b'D3D11CoreCreateLayeredDevice',
    b'D3D11CoreGetLayeredDeviceSize',
    b'D3D11CoreRegisterLayers',
    b'D3D11On12CreateDevice',
]

def main(argv):
    if len(argv) != 2:
        print('Usage: verify_ts4_dx11_imports.py <path-to-TS4_x64.exe>')
        return 2
    path = argv[1]
    if not os.path.isfile(path):
        print('ERROR: file not found: {}'.format(path))
        return 2
    with open(path, 'rb') as fh:
        data = fh.read()
    lower = data.lower()
    print('File: {}'.format(path))
    print('Size: {} bytes'.format(len(data)))
    print('Contains d3d11.dll string: {}'.format(b'd3d11.dll' in lower))
    missing = [name.decode('ascii') for name in REQUIRED if name not in data]
    extras = [name.decode('ascii') for name in KNOWN_EXTRA if name in data]
    for name in REQUIRED:
        print('{}: {}'.format(name.decode('ascii'), 'FOUND' if name in data else 'MISSING'))
    if extras:
        print('WARNING: extra D3D11 entry strings found: {}'.format(', '.join(extras)))
        print('Do not install the proxy until TD1ApexD3D11Proxy.cpp exports/wraps those extra entry points too.')
        return 1
    if missing:
        print('ERROR: required DX11 entry point strings missing: {}'.format(', '.join(missing)))
        print('This build may be DX9, packed differently, or not compatible with the current proxy install path.')
        return 1
    print('OK: current proxy entry coverage matches this TS4_x64.exe string scan.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
