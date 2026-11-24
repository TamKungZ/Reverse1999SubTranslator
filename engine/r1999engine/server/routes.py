import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

GET_ROUTES = {
    "/info": lambda host: host.info(),
    "/view": lambda host: host.session.view(),
    "/config": lambda host: host.cfg.snapshot(),
}


def _reset(host, body, headers):
    host.session.reset()
    return {"ok": True}


def _download(host, body, headers):
    host.download_model()
    return {"ok": True}


def _cancel(host, body, headers):
    host.downloader.cancel()
    return {"ok": True}


POST_ROUTES = {
    "/frame": lambda host, body, headers: host.frame(body, headers),
    "/config": lambda host, body, headers: {"changed": host.update_config(json.loads(body or b"{}"))},
    "/reset": _reset,
    "/model/download": _download,
    "/model/cancel": _cancel,
}


def make_handler(host):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
            pass

        def _send(self, payload, status=200):
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            route = GET_ROUTES.get(self.path)
            self._send(route(host) if route else {"error": "not found"}, 200 if route else 404)

        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            try:
                if self.path == "/shutdown":
                    self._send({"ok": True})
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
                elif self.path in POST_ROUTES:
                    self._send(POST_ROUTES[self.path](host, body, self.headers))
                else:
                    self._send({"error": "not found"}, 404)
            except Exception as exc:
                self._send({"error": str(exc)}, 400)

    return Handler


def serve(host, port):
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(host))
    server.daemon_threads = True
    host.start()
    try:
        server.serve_forever()
    finally:
        host.close()
