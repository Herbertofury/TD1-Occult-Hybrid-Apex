"""Bounded POST transport for the fixed native controls, including large views."""
import json

MAX_BODY = 4 * 1024 * 1024


def read(conn, initial):
    conn.settimeout(10)
    data = initial
    while b'\r\n\r\n' not in data:
        if len(data) >= 16384: raise ValueError('Native HTTP headers exceed bound.')
        chunk = conn.recv(4096)
        if not chunk: raise ValueError('Truncated native HTTP headers.')
        data += chunk
    header, body = data.split(b'\r\n\r\n', 1)
    lines = header.decode('ascii').split('\r\n')
    if len(header) > 16384 or lines[0] != 'POST /api/native HTTP/1.1':
        raise ValueError('Fixed native POST route required.')
    fields = {}
    for line in lines[1:]:
        key, value = line.split(':', 1); key = key.strip().lower()
        if key in fields: raise ValueError('Duplicate native HTTP header.')
        fields[key] = value.strip()
    if (fields.get('host') != '127.0.0.1:8017' or fields.get('content-type') != 'application/json' or
            'transfer-encoding' in fields or fields.get('origin') not in (None, 'http://127.0.0.1:8017')):
        raise ValueError('Exact loopback JSON transport required.')
    size = int(fields.get('content-length', '0'))
    if not 0 < size <= MAX_BODY or len(body) > size: raise ValueError('Native POST extent differs.')
    while len(body) < size:
        chunk = conn.recv(min(65536, size - len(body)))
        if not chunk: raise ValueError('Truncated native POST body.')
        body += chunk
    request = json.loads(body.decode('utf-8'))
    if not isinstance(request, dict) or set(request) != {'action', 'value', 'request_id'}:
        raise ValueError('Fixed native control envelope required.')
    if not all(isinstance(value, str) for value in request.values()):
        raise ValueError('Native control envelope requires strings.')
    return request
