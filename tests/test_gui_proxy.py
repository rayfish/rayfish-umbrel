import http.client
import importlib.util
import json
import os
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path


os.environ["GUI_TOKEN"] = "test-token"
spec = importlib.util.spec_from_file_location(
    "gui_proxy", Path(__file__).resolve().parents[1] / "docker" / "gui-proxy.py"
)
proxy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proxy)


class DashboardControlsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (Path(__file__).resolve().parents[1] / "docker" / "gui.html").read_text(
            encoding="utf-8"
        )

    def test_ssh_controls_use_mesh_ssh_commands(self):
        self.assertIn('["firewall", "ssh", ssh ? "off" : "on"]', self.html)
        self.assertIn('["firewall", "ssh", "allow", network, peer]', self.html)
        self.assertIn('["firewall", "ssh", "deny", t.dataset.sshNetwork', self.html)
        self.assertNotIn('["firewall", "add", "in", "allow", "--proto", "tcp", "--port", "22"', self.html)

    def test_magic_dns_offers_every_mode(self):
        for mode in ("partial", "off", "on"):
            self.assertIn(f'<option value="{mode}">', self.html)
        self.assertIn('["dns", $("dnsMode").value]', self.html)


class ProxyRoutesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        root = Path(cls.temp.name)
        proxy.HTML_PATH = str(root / "gui.html")
        proxy.DOWNLOAD_DIR = str(root / "downloads")
        Path(proxy.HTML_PATH).write_text("token=__TOKEN__", encoding="utf-8")
        Path(proxy.DOWNLOAD_DIR).mkdir()
        (Path(proxy.DOWNLOAD_DIR) / "sample.txt").write_text("sample", encoding="utf-8")
        (Path(proxy.DOWNLOAD_DIR) / "outside.txt").symlink_to(root / "gui.html")
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), proxy.Proxy)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.temp.cleanup()

    def get(self, path):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        conn.request("GET", path)
        response = conn.getresponse()
        status = response.status
        body = response.read()
        conn.close()
        return status, body

    def test_gui_uses_current_token(self):
        status, body = self.get("/")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"token=test-token")

    def test_downloads_only_regular_files_inside_directory(self):
        status, body = self.get("/downloads")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), ["sample.txt"])
        self.assertEqual(self.get("/downloads/sample.txt"), (200, b"sample"))
        for path in ("/downloads/outside.txt", "/downloads/%2e%2e", "/downloads/%2fetc%2fpasswd"):
            with self.subTest(path=path):
                self.assertEqual(self.get(path)[0], 404)


if __name__ == "__main__":
    unittest.main()
