#!/usr/bin/env python3
"""Local POST-only HTTP proxy with bounded retries for dropped upload responses.

The proxy never logs request headers or bodies. It is intended only as a
temporary workaround for Tencent slice-upload EOF errors.
"""

from __future__ import annotations

import argparse
import http.client
import http.server
import socketserver
import time
import urllib.parse


HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "proxy-connection",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


class RetryingProxyHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    upstream_attempts = 8

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length)
        target = urllib.parse.urlsplit(self.path)
        if target.scheme != "http" or not target.hostname:
            self.send_error(400, "absolute HTTP target required")
            return

        upstream_path = urllib.parse.urlunsplit(("", "", target.path or "/", target.query, ""))
        upstream_headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in HOP_BY_HOP_HEADERS and key.lower() != "host"
        }
        upstream_headers["Host"] = target.netloc
        upstream_headers["Connection"] = "close"
        upstream_headers["Content-Length"] = str(len(body))

        last_error: Exception | None = None
        for attempt in range(self.upstream_attempts):
            connection = http.client.HTTPConnection(target.hostname, target.port or 80, timeout=45)
            try:
                connection.request("POST", upstream_path, body=body, headers=upstream_headers)
                response = connection.getresponse()
                response_body = response.read()
                self.send_response(response.status, response.reason)
                for key, value in response.getheaders():
                    if key.lower() not in HOP_BY_HOP_HEADERS and key.lower() != "content-length":
                        self.send_header(key, value)
                self.send_header("Content-Length", str(len(response_body)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(response_body)
                return
            except (OSError, http.client.HTTPException) as error:
                last_error = error
                if attempt + 1 < self.upstream_attempts:
                    time.sleep(min(0.25 * (2**attempt), 3.0))
            finally:
                connection.close()

        self.send_error(502, f"upstream unavailable after retries: {type(last_error).__name__}")


class ThreadingServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=18765)
    args = parser.parse_args()
    server = ThreadingServer(("127.0.0.1", args.port), RetryingProxyHandler)
    print(f"READY 127.0.0.1:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
