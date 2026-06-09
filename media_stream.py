"""Small authenticated HTTP Range server for host video streaming."""

import mimetypes
import os
import secrets
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse


def discover_local_ip(server_url: str) -> str:
    override = os.getenv("WATCH_PARTY_STREAM_HOST", "").strip()
    if override:
        return override

    hostname = urlparse(server_url).hostname
    targets = []
    if hostname and hostname not in ("127.0.0.1", "localhost"):
        targets.append(hostname)
    targets.append("8.8.8.8")

    for target in targets:
        try:
            probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            probe.connect((target, 80))
            address = probe.getsockname()[0]
            probe.close()
            if address and not address.startswith("127."):
                return address
        except OSError:
            pass

    try:
        return socket.gethostbyname(socket.gethostname())
    except socket.gaierror:
        return "127.0.0.1"


class MediaStreamServer:
    def __init__(self, advertised_host: str):
        self.advertised_host = advertised_host
        self.file_path = ""
        self.token = secrets.token_urlsafe(24)
        self.httpd = None
        self.thread = None

    def start(self) -> None:
        if self.httpd:
            return

        owner = self

        class StreamHandler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_HEAD(self):
                self._serve(send_body=False)

            def do_GET(self):
                self._serve(send_body=True)

            def _serve(self, send_body: bool):
                if self.path.split("?", 1)[0] != f"/stream/{owner.token}":
                    self.send_error(404)
                    return
                path = owner.file_path
                if not path or not os.path.isfile(path):
                    self.send_error(404, "No video is currently available")
                    return

                size = os.path.getsize(path)
                start = 0
                end = size - 1
                range_header = self.headers.get("Range")
                if range_header:
                    try:
                        unit, value = range_header.strip().split("=", 1)
                        if unit != "bytes":
                            raise ValueError
                        first, last = value.split("-", 1)
                        if first:
                            start = int(first)
                            end = int(last) if last else end
                        elif last:
                            suffix = int(last)
                            start = max(0, size - suffix)
                        if start < 0 or end < start or start >= size:
                            raise ValueError
                        end = min(end, size - 1)
                    except (ValueError, TypeError):
                        self.send_response(416)
                        self.send_header("Content-Range", f"bytes */{size}")
                        self.send_header("Content-Length", "0")
                        self.end_headers()
                        return

                length = end - start + 1
                self.send_response(206 if range_header else 200)
                content_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
                self.send_header("Content-Type", content_type)
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Length", str(length))
                if range_header:
                    self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                self.send_header("Connection", "close")
                self.end_headers()

                if not send_body:
                    return
                try:
                    with open(path, "rb") as video:
                        video.seek(start)
                        remaining = length
                        while remaining > 0:
                            chunk = video.read(min(1024 * 1024, remaining))
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            remaining -= len(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def log_message(self, format_string, *args):
                print(f"Media stream: {self.address_string()} - {format_string % args}")

        port = int(os.getenv("WATCH_PARTY_STREAM_PORT", "8766"))
        self.httpd = ThreadingHTTPServer(("0.0.0.0", port), StreamHandler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def set_file(self, file_path: str) -> str:
        self.file_path = os.path.abspath(file_path)
        self.start()
        port = self.httpd.server_address[1]
        return f"http://{self.advertised_host}:{port}/stream/{self.token}"

    def close(self) -> None:
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
        self.httpd = None
        self.thread = None
        self.file_path = ""
