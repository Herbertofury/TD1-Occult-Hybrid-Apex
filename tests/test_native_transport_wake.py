"""Keep new transport producers compatible with an indefinitely sleeping worker.

Runtime retention/FIFO/deadline behavior is tested by native-transport-wake.
These integration checks catch a producer or lifecycle write bypassing that
signal, which would leave a valid command asleep until an unrelated UI action.
"""
from pathlib import Path
import re
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "NativeOverlay/Source/TD1ApexD3D11Proxy.cpp"


def cpp_code(text):
    # Blank comments/literals while retaining positions for scope comparisons.
    return re.sub(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',
                  lambda match: " " * len(match[0]), text, flags=re.S)


def function_span(code, name):
    match = re.search(r"\b" + re.escape(name) + r"\([^;{}]*\)[^{;]*\{", code)
    if match is None:
        raise AssertionError("Missing function: " + name)
    start = match.end() - 1
    depth = 1
    for position in range(start + 1, len(code)):
        depth += (code[position] == "{") - (code[position] == "}")
        if not depth:
            return start, position + 1
    raise AssertionError("Unclosed function: " + name)


class TransportWakeIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code = cpp_code(SOURCE.read_text(encoding="utf-8"))

    def body(self, name):
        begin, end = function_span(self.code, name)
        return self.code[begin:end]

    def test_all_queue_insertions_pass_through_the_signaling_helper(self):
        inserts = list(re.finditer(
            r"\bg_commands\s*\.\s*(push_back|push_front|emplace_back|emplace_front|emplace|insert|assign|swap)\s*\(",
            self.code))
        self.assertEqual(len(inserts), 1, "A direct producer can strand work while the worker sleeps")
        begin, end = function_span(self.code, "EnqueueCommandLocked")
        self.assertTrue(begin < inserts[0].start() < end)
        self.assertRegex(self.body("EnqueueCommandLocked"), r"push_back\([^;]+;\s*WakeWorker\(\)")

    def test_idle_conditions_and_shutdown_have_no_unsignaled_writers(self):
        for field, helper in (("g_visible", "SetOverlayVisible"),
                              ("g_nativeCasPaneVisible", "SetNativeCasPaneVisible"),
                              ("g_ownerBlocked", "SetOwnerBlocked"),
                              ("g_done", "StopWorker")):
            begin, end = function_span(self.code, helper)
            writes = list(re.finditer(r"\b" + field + r"\s*(?:=(?!=)|\.\s*(?:store|exchange)\s*\()", self.code))
            self.assertTrue(writes, field)
            self.assertTrue(all(begin < match.start() < end for match in writes), field)
            self.assertIn("WakeWorker()", self.body(helper))
        detach = self.code[self.code.index("DLL_PROCESS_DETACH"):]
        self.assertRegex(detach, r"td1::StopWorker\(\)")

    def test_signal_is_ready_before_worker_and_never_closed_during_detach(self):
        start = self.body("EnsureWorker")
        self.assertIn("std::call_once", start)
        self.assertLess(start.index("g_workerWake.store"), start.index("std::thread(WorkerLoop)"))
        self.assertNotRegex(self.code, r"(?:delete\s+g_workerWake|CloseHandle\s*\([^)]*g_workerWake)")
        self.assertNotRegex(self.body("StopWorker"), r"\b(?:new|delete|lock_guard|unique_lock)\b")

    def test_worker_uses_retained_wait_and_original_metadata_deadline(self):
        self.assertIn("WaitForWorkerWork()", self.body("WorkerLoop"))
        self.assertIn("g_lastStatusMs >= transport::StatusIntervalMs", self.body("WorkerLoop"))
        self.assertNotRegex(self.body("WorkerLoop"), r"Sleep\(g_visible")
        idle = self.body("WaitForWorkerWork")
        self.assertRegex(idle, r"lock_guard<std::mutex>\s+lock\(g_dataMutex\);\s*if\(!g_commands.empty\(\)\)\s*return;")
        self.assertLess(idle.index("if(!g_commands.empty())"), idle.index("wake->Wait(wait)"))
        self.assertRegex(idle, r"if\(!g_commands.empty\(\)\)\s*return;\s*\}")
        for field in ("g_lastStatusMs.load()", "g_nativeCasPaneVisible.load()", "g_ownerBlocked.load()"):
            self.assertIn(field, idle)
        self.assertIn("transport::IdleWaitMilliseconds", idle)
        self.assertIn("wake->Wait(wait)", idle)
        self.assertRegex(idle, r"Sleep\(visible\?120:250\)")


if __name__ == "__main__":
    unittest.main()
