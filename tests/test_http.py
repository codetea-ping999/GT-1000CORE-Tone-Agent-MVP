import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen

from gtcore_agent.server import Handler, HOST, PORT


class HttpSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer((HOST, PORT), Handler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=3)

    def request(self, path, payload=None):
        data = json.dumps(payload).encode() if payload is not None else None
        headers = {"Content-Type": "application/json"} if data is not None else {}
        req = Request(f"http://{HOST}:{PORT}{path}", data=data, headers=headers)
        with urlopen(req, timeout=5) as response:
            return response.status, response.read(), response.headers["Content-Type"]

    def test_ui_and_demo_workflow(self):
        status, page, mime = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn(b"GT-1000CORE", page)
        self.assertIn("text/html", mime)

        status, raw, _ = self.request("/api/read", {})
        self.assertEqual(status, 200)
        original = json.loads(raw)
        self.assertEqual(original["mode"], "demo")

        _, raw, _ = self.request("/api/suggest", {"goal": "9mmのような鋭い音", "model": "rules"})
        proposal = json.loads(raw)["proposal"]
        self.assertTrue(proposal["changes"])

        _, raw, _ = self.request("/api/apply", {"proposal_id": proposal["id"], "confirmed": True})
        after = json.loads(raw)
        self.assertTrue(after["undo_available"])

        _, raw, _ = self.request("/api/undo", {"confirmed": True})
        restored = json.loads(raw)
        self.assertFalse(restored["undo_available"])
        self.assertEqual(restored["values"], original["values"])


if __name__ == "__main__":
    unittest.main()
