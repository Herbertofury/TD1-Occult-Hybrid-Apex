import copy
import hashlib
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import overlay_loader


class NativeCodeWindowTests(unittest.TestCase):
    def setUp(self):
        self.argument = {'rva': 0x1800, 'bytes': 2}
        self.reply = dict(ok=True, pid=123, exe_sha256='916b852b187b9c41b9c2d77af55e0d5ed6aaf06909661397d7aa98f2e4db78ab',
            read_only=True, game_memory_written=False, game_files_written=False, sim_data_read=False,
            native_patch_qualified=False, own_process_only=True, function_entry_verified=False,
            text_rva=0x1000, text_bytes=0x2000, code_rva=0x1800, captured_bytes=2,
            code_hex='90c3', code_sha256=hashlib.sha256(bytes.fromhex('90c3')).hexdigest())

    def test_exact_pinned_code_bytes_are_allowed_without_an_entry_or_execution_claim(self):
        self.assertEqual(overlay_loader._code_window_reply(self.argument, self.reply, 123), self.reply)

    def test_unbounded_untyped_and_pointer_arguments_refuse_before_binding(self):
        invalid = [None, {}, dict(self.argument, address=0x140000000)]
        for key, values in (('rva', (-1, 0x100000000, True, '0x1800', None)),
                            ('bytes', (0, 8193, True, 1.5, None))):
            invalid += [dict(self.argument, **{key: value}) for value in values]
        for argument in invalid:
            with self.subTest(argument=argument), self.assertRaises(ValueError):
                overlay_loader.native_cas_code_window('unused', 'unused', argument)

    def test_changed_identity_writes_sim_data_and_execution_claims_refuse(self):
        for key, value in (('pid', 124), ('pid', True), ('exe_sha256', 'a' * 64),
                           ('read_only', False), ('game_memory_written', True), ('game_files_written', True),
                           ('sim_data_read', True), ('own_process_only', False),
                           ('native_patch_qualified', True), ('function_entry_verified', True)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                overlay_loader._code_window_reply(self.argument, dict(self.reply, **{key: value}), 123)

    def test_other_sections_overflow_and_mismatched_requested_windows_refuse(self):
        for key, value in (('text_rva', 0x1900), ('text_bytes', 0x800), ('text_rva', -1),
                           ('text_bytes', 0x100000000), ('text_bytes', True),
                           ('code_rva', 0x1801), ('captured_bytes', 1), ('code_rva', True)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                overlay_loader._code_window_reply(self.argument, dict(self.reply, **{key: value}), 123)

    def test_changed_truncated_or_unfingerprinted_code_refuses(self):
        for key, value in (('code_hex', '90c2'), ('code_hex', '90'), ('code_hex', '90C3'),
                           ('code_hex', 'zzc3'), ('code_hex', None), ('code_sha256', 'a' * 64)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                overlay_loader._code_window_reply(self.argument, dict(self.reply, **{key: value}), 123)

    def test_native_failure_keeps_the_no_write_contract_without_fabricating_code(self):
        failure = {key: copy.deepcopy(self.reply[key]) for key in
                   ('read_only', 'game_memory_written', 'game_files_written', 'sim_data_read', 'native_patch_qualified')}
        failure.update(ok=False, message='Unsupported image')
        self.assertEqual(overlay_loader._code_window_reply(self.argument, failure, 123), failure)
