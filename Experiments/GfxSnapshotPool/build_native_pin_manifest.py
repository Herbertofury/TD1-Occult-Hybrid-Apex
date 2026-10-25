"""Read-only receipt for the isolated recycler experiment; never opens a process."""
from pathlib import Path
import hashlib
import json
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
TEXT_SHA256 = '87d6eeacc8813cf60af07800f66f7cdcc2a5bc9e1caf423a89c170d8c42c4367'
EXE_SHA256 = '916b852b187b9c41b9c2d77af55e0d5ed6aaf06909661397d7aa98f2e4db78ab'
SPANS = {
    'context_constructor': (0x1005AE0, 0x1005C70),
    'context_capture': (0x1006A20, 0x1006DA5),
    'snapshot_destructor': (0x10063D0, 0x1006509),
    'retire_finalized_snapshot': (0x10086D0, 0x1008812),
    'context_next_capture': (0x1008820, 0x10089D0),
    'context_destructor': (0x1005EE0, 0x100602E),
    'context_shutdown': (0x1007E30, 0x1007FF3),
    'context_shutdown_rendering': (0x1008B00, 0x1008BE3),
    'native_aligned_allocate': (0x10026E0, 0x100277C),
    'native_free': (0x1002DA0, 0x1002F11),
    'global_heap_shutdown': (0x1003930, 0x10039D4),
    'heap_constructor': (0x109DF80, 0x109E0BC),
    'movie_advance': (0xFF6AE0, 0xFF74AA),
}
SITES = {
    'capture_allocate_virtual_call_span': (0x1006B80, 0x1006B8A),
    'final_pointer_page_free_virtual_call_span': (0x10064B1, 0x10064B7),
    'movie_context_constructor_call': (0xFF4F04, 0xFF4F10),
    'movie_dirty_capture_call': (0xFF7E7C, 0xFF7E88),
    'movie_clean_final_capture_call': (0xFF791D, 0xFF7929),
    'movie_context_destructor_call': (0xFF5A7D, 0xFF5A89),
    'native_free_release_on_free_check': (0x1002EF7, 0x1002F06),
    'heap_global_clear_after_release': (0x100398C, 0x10039A3),
}


def sha(data): return hashlib.sha256(data).hexdigest()


def build(text):
    if sha(text) != TEXT_SHA256: raise ValueError('Authenticated runtime text differs; no manifest or hook eligibility.')
    def row(begin, end, include_bytes=False):
        raw = text[begin - 0x1000:end - 0x1000]
        if len(raw) != end - begin: raise ValueError('Native span outside authenticated text.')
        item = dict(begin_rva=hex(begin), end_rva=hex(end), bytes=len(raw), sha256=sha(raw))
        if include_bytes: item['expected_bytes_hex'] = raw.hex()
        return item
    # Exact native call ABI, not a hand-entered function-name label.
    assert text[0x1006B80-0x1000:0x1006B8A-0x1000] == bytes.fromhex('488b01458d4110ff5048')
    assert text[0x10064B1-0x1000:0x10064B7-0x1000] == bytes.fromhex('488b01ff5060')
    # Native full initialization: five 8-byte header stores; four 128-byte
    # copies followed by four 16-byte copies. This checks the actual pinned
    # loop count and branch before deriving the complete destination coverage.
    assert text[0x1006BA5-0x1000:0x1006BAB-0x1000] == bytes.fromhex('41b804000000')
    assert text[0x1006C0D-0x1000:0x1006C13-0x1000] == bytes.fromhex('4983e80175ad')
    header = set(range(0x28)); payload = set()
    for iteration in range(4):
        for lane in range(8): payload.update(range(0x28 + iteration * 0x80 + lane * 16, 0x28 + iteration * 0x80 + (lane + 1) * 16))
    for lane in range(4): payload.update(range(0x228 + lane * 16, 0x228 + (lane + 1) * 16))
    assert not header & payload and header | payload == set(range(0x268))
    return dict(
        schema=1, experiment_only=True, runtime_qualified=False, game_hooks_implemented=False,
        performance_gain_claimed=False, native_lifetime_review_complete=False,
        game_executable_sha256=EXE_SHA256, runtime_text_sha256=TEXT_SHA256,
        runtime_text_rva='0x1000', image_base_normalized='0x140000000',
        authenticated_spans={name:row(*bounds) for name,bounds in SPANS.items()},
        exact_callsite_spans={name:row(*bounds, include_bytes=True) for name,bounds in SITES.items()},
        native_heap=dict(global_pointer_rva='0x29640d0', expected_vtable_rva='0x201ede0',
            aligned_allocate_vtable_slot='0x48', aligned_allocate_rva='0x10026e0',
            free_vtable_slot='0x60', free_rva='0x1002da0', release_on_free_marker_offset='0x30',
            native_accounting='retained blocks remain real outstanding native allocations until drained'),
        object_layout=dict(movie_context_offset='0x5330',context_heap_offsets=['0x0','0x18'],
            context_lock_state_offset='0x70',context_shutdown_flag_offset='0x94',
            context_snapshot_offsets=dict(current='0xc8',captured='0xd0',rendering='0xd8',finalized='0xe0'),
            current_frame_id_offset='0xe8', finalized_frame_id_offset='0x108',
            snapshot_context_offset='0x10', snapshot_pointer_page_list_head_offset='0x18',
            entry_page_current_pointer_page_offset='0x20',pointer_page_bytes='0x268',
            pointer_page_alignment=16,pointer_page_header_bytes='0x28',pointer_payload_bytes='0x240',pointer_slots=72),
        full_initialization=dict(header_bytes=len(header),payload_bytes=len(payload),total_overwritten=0x268,
            first_destination_offset=0,last_destination_offset=0x267, native_copy_and_header_instructions_retained=True),
        preservation_requirements=[
            'Never skip, defer, coalesce or replace Context Capture, NextCapture, propagation or node callbacks.',
            'Take only at capture allocation call with original RCX heap/RDX size/R8 alignment/R9 info; cached return substitutes only RAX.',
            'Retain only after exact native pointer-page neighbor unlink and prior native finalization; derive owner from live Snapshot+0x10.',
            'Require authenticated active same-thread Capture scope, same context/heap and live nonce; every other native call forwards unchanged.',
            'Reject non-root/changed/ReleaseOnFree heaps; bounds include all retained native bytes in honest heap accounting.',
            'Mark closing and drain before native Context destructor; keep closing tombstone until original destructor returns.',
            'Terminal disable/drain, including concurrent drain completion, before global heap shutdown leak check or heap release.',
            'All native frees run outside pool lock; prevent callback reentry, cross-thread reuse and stale-context/address-reuse scopes.',
        ],
        open_native_adapter_gates=[
            'No actual-game hooks, exact-thunk ABI tests or unwind/exception qualification exist yet.',
            'Actual per-Capture allocate/free/page counts and hit rates are not measured by ETW CPU sample weights.',
            'Runtime root-heap vtable/global identity and ReleaseOnFree marker reads must be independently authenticated before arming.',
            'Native adapter must preserve x64 stack alignment, shadow space, all nonvolatile registers, original volatile return behavior and tail flags.',
            'Context Capture return AL and original exceptions must propagate through every shutdown/reentrant/fault route.',
            'The isolated drain callback is noexcept; native Free exception/unwind compatibility is not yet qualified.',
            'Unknown heap lifecycle, third-party patches, partial hook install or module unload must refuse arming and drain while native heap is alive.',
        ],
        primary_sdk_references=[
            'https://help.autodesk.com/cloudhelp/ENU/Scaleform-Help/cpp_ref/03124.html',
            'https://help.autodesk.com/cloudhelp/ENU/Scaleform-Help/cpp_ref/03146.html',
            'https://help.autodesk.com/cloudhelp/ENU/Scaleform-Help/cpp_ref/02315.html',
            'https://help.autodesk.com/cloudhelp/ENU/Scaleform-Help/scaleform_help/renderer_guide/renderer_snapshot.html',
        ])


if __name__ == '__main__':
    source=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'.work/private-v204-runtime-text.bin'
    result=build(source.read_bytes())
    output=Path(__file__).with_name('native_pin_manifest.json')
    output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(output)
