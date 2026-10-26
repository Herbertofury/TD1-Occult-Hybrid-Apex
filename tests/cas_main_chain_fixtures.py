"""Read coherent Main fixtures from the current private compiled package.

Historical library tests may replace a provider, but must not combine that
provider with an obsolete Main diagnostic envelope. No hashes are rewritten:
each Main stage is recovered by the production bytecode rollback verifier.
"""
import copy
import json
from pathlib import Path

import cas_catalog_binding as binding
import cas_draw_phase as phase
import dbpf_build
import maru_companion

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'dist/candidate/ApexCASBridge.package'
READY = PACKAGE.is_file() and Path(str(PACKAGE) + '.manifest.json').is_file()


def current_main(stage):
    info = json.loads(Path(str(PACKAGE) + '.manifest.json').read_text(encoding='utf-8'))
    final = dbpf_build.read(PACKAGE.read_bytes())[maru_companion.CUSTOMIZER]
    outer = info['draw_phase_native_bytecode_contract']
    if phase.verify_contract(outer, final) is not True:
        raise AssertionError('Current Main granular chain did not verify')
    prior = phase.reconstruct_previous(final, outer['draw_phase_contract'])
    if outer['previous_stage_contract'] != info['catalog_binding_native_bytecode_contract']:
        raise AssertionError('Current Main binding history differs')
    if stage == 'phase':
        return copy.deepcopy(outer), final, prior
    outer = info['catalog_binding_native_bytecode_contract']
    if binding.verify_contract(outer, prior) is not True:
        raise AssertionError('Current Main binding chain did not verify')
    baseline = binding.reconstruct_previous(prior, outer['catalog_binding_contract'])
    if outer['previous_stage_contract'] != info['cell_attach_native_bytecode_contract']:
        raise AssertionError('Current Main attach history differs')
    if stage == 'binding':
        return copy.deepcopy(outer), prior, baseline
    raise ValueError('Unknown Main fixture stage')
