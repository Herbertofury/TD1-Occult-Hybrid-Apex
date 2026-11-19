"""Recognize an old completed target mismatch for normal unsaved closure only.

Older scripts retain a valid failed swatch readback as pending. This read-only
classification cannot unlock their CAS writer, submit a save, or resend input.
The complete Source receipt stays in the lifecycle evidence without alteration.
"""
from pathlib import Path
import copy
import re
import sys


def classify(diagnostic, receipts, sim_id):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
    from apex_core.cas_ui import validate_client
    projected = copy.deepcopy(diagnostic)
    eligible = [row for row in projected['requests'] if
                row.get('state') == 'pending' and row.get('operation') == 'swatch']
    if projected['native_peers'] or not eligible or set(receipts) != {row['cas_request_id'] for row in eligible}:
        raise ValueError('Only detached completed failed swatches can permit unsaved closure.')
    evidence = []
    for row in eligible:
        rid = row['cas_request_id']
        reply = receipts[rid]
        if (not isinstance(reply, dict) or reply.get('ok') is not False or
                reply.get('cas_request_id') != rid or reply.get('cas_request_state') != 'pending' or
                reply.get('outcome') != 'invalid-native-acknowledgement' or
                reply.get('message') != 'Native swatch did not read back its exact selected identity.'):
            raise ValueError('Retained response is not a completed typed target mismatch.')
        packet = reply.get('native_acknowledgement')
        if (not isinstance(packet, dict) or type(packet.get('protocol')) is not int or packet['protocol'] != 1 or
                packet.get('cas_request_id') != rid or packet.get('ok') is not True or
                packet.get('operation') != 'swatch' or packet.get('mutation_started') is not True):
            raise ValueError('Retained native acknowledgement lacks its exact completed swatch identity.')
        client = packet.get('client')
        validate_client(client, sim_id, {'operation': 'status'})
        control = client.get('control')
        selected = control.get('selected') if isinstance(control, dict) else None
        if (not isinstance(control, dict) or control.get('operation') != 'swatch' or
                not isinstance(selected, str) or re.fullmatch(r'[1-9][0-9]{0,19}', selected) is None or
                not 0 < int(selected) < 2**64):
            raise ValueError('Retained native swatch readback is incomplete or untyped.')
        row.update(state='failed', outcome='failed')
        evidence.append({'cas_request_id': rid, 'source_receipt': copy.deepcopy(reply),
                         'source_request_state_changed': False, 'native_success_verified': False,
                         'save_authorized': False, 'cas_writer_unlocked': False, 'input_retried': False,
                         'scope': 'Complete failed readback permits only normal exit without saving.'})
    return projected, evidence
