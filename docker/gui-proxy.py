"""Expose the localhost-only ray gui on the LAN for Umbrel.

ray gui binds 127.0.0.1 and requires a per-run token in the URL (GET) or in an
x-rayfish-token header (POST). Umbrel links straight to http://<device>:8480
with no way to carry a token, so this proxy listens on 0.0.0.0 and injects the
token into every forwarded request. The LAN is trusted here, the same
trade-off the official Tailscale Umbrel app makes with its tokenless web UI.
Delete this shim once ray gui grows --host/--no-token flags.
"""

import http.client
import json
import os
import shutil
import stat
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote, unquote

TOKEN = os.environ["GUI_TOKEN"]
UPSTREAM_PORT = int(os.environ.get("GUI_UPSTREAM_PORT", "8481"))
LISTEN_PORT = int(os.environ.get("LISTEN_PORT", "8480"))
# App icon served at /icon.png for the umbrelOS home screen: its CSP
# (img-src * blob:) blocks data: URIs, so the manifest points here instead.
ICON_PATH = os.environ.get("ICON_PATH", "/usr/local/lib/rayfish/icon.png")
HTML_PATH = os.environ.get("HTML_PATH", "/usr/local/lib/rayfish/gui.html")
DOWNLOAD_DIR = os.environ.get("DOWNLOAD_DIR", "/etc/rayfish/downloads")
MAX_BODY = 64 * 1024
# ray gui kills commands after 300s; outlive that so the error page arrives.
UPSTREAM_TIMEOUT = 310

HOP_BY_HOP = {"connection", "keep-alive", "transfer-encoding", "host"}


class Proxy(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _forward(self):
        if self.command == "GET" and self.path == "/icon.png":
            return self._serve_icon()
        if self.command == "GET" and self.path.partition("?")[0] in ("/", "/index.html"):
            return self._serve_gui()
        if self.command == "GET" and self.path == "/downloads":
            return self._list_downloads()
        if self.command == "GET" and self.path.startswith("/downloads/"):
            return self._serve_download()
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            self.send_error(413)
            return
        body = self.rfile.read(length) if length else None

        path = self.path
        if self.command == "GET":
            path += ("&" if "?" in path else "?") + "token=" + TOKEN
        headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in HOP_BY_HOP
        }
        headers["x-rayfish-token"] = TOKEN
        headers["Connection"] = "close"

        conn = http.client.HTTPConnection(
            "127.0.0.1", UPSTREAM_PORT, timeout=UPSTREAM_TIMEOUT
        )
        try:
            conn.request(self.command, path, body=body, headers=headers)
            resp = conn.getresponse()
            data = resp.read()
        except OSError as err:
            self.send_error(502, explain=str(err))
            return
        finally:
            conn.close()

        self.send_response(resp.status)
        for key, value in resp.getheaders():
            if key.lower() not in HOP_BY_HOP and key.lower() != "content-length":
                self.send_header(key, value)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_icon(self):
        try:
            with open(ICON_PATH, "rb") as fh:
                data = fh.read()
        except OSError:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=86400")
        self.end_headers()
        self.wfile.write(data)

    def _serve_gui(self):
        try:
            with open(HTML_PATH, encoding="utf-8") as fh:
                data = fh.read().replace("__TOKEN__", TOKEN).encode("utf-8")
        except OSError:
            self.send_error(503)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _list_downloads(self):
        try:
            with os.scandir(DOWNLOAD_DIR) as entries:
                files = sorted(
                    (entry.name for entry in entries if entry.is_file(follow_symlinks=False)),
                    key=str.casefold,
                )
        except OSError:
            files = []
        data = json.dumps(files).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _serve_download(self):
        name = unquote(self.path[len("/downloads/"):].partition("?")[0])
        if not name or name in (".", "..") or "/" in name or "\\" in name or "\x00" in name:
            self.send_error(404)
            return
        try:
            directory = os.open(DOWNLOAD_DIR, os.O_RDONLY | os.O_DIRECTORY)
            try:
                fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
            finally:
                os.close(directory)
            with os.fdopen(fd, "rb") as fh:
                size = os.fstat(fh.fileno())
                if not stat.S_ISREG(size.st_mode):
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + quote(name))
                self.send_header("Content-Length", str(size.st_size))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                shutil.copyfileobj(fh, self.wfile)
        except OSError:
            self.send_error(404)

    do_GET = _forward
    do_POST = _forward

    def log_message(self, *_args):
        pass


def main():
    server = ThreadingHTTPServer(("0.0.0.0", LISTEN_PORT), Proxy)
    server.serve_forever()


if __name__ == "__main__":
    main()
