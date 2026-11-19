"""The actual F11 receiver must honor the native response framer's completion."""
from pathlib import Path
import unittest


class NativeHttpResponseIntegrationTests(unittest.TestCase):
    def test_complete_frame_exits_receive_before_json_and_without_eof(self):
        path = Path(__file__).resolve().parents[1] / "NativeOverlay/Source/TD1ApexD3D11Proxy.cpp"
        source = path.read_text(encoding="utf-8")
        begin = source.index("static bool HttpGet(")
        end = source.index("static bool HttpOwnedCommand(", begin)
        body = source[begin:end]
        self.assertIn("http::ResponseFrame frame(ui::kMaxOwnerJsonBytes)", body)
        append = body.index("raw.append(buf, buf + n)")
        inspect = body.index("frame.Observe(raw)", append)
        complete = body.index("if(progress==http::ResponseProgress::Complete) break", inspect)
        publish = body.index("body = raw.substr(frame.BodyOffset(),frame.BodySize())", complete)
        self.assertLess(complete, publish)
        self.assertIn("frame.EndOfStream(raw)!=http::ResponseProgress::Complete", body)
        self.assertIn("if(progress==http::ResponseProgress::Rejected)", body)
        self.assertIn("DWORD timeout = remainingTimeout()", body)
        self.assertIn("!ui::ReadObject(body).empty()", body)


if __name__ == "__main__":
    unittest.main()
