"""Minimal HLS proxy + static server for testing Audiobookshelf HLS output.

Usage:
    python server.py                (listens on http://localhost:8088)
    set PORT=9000 && python server.py

Then open http://localhost:8088 in a browser. The page POSTs to this server
at /upstream/api/... and /upstream/hls/..., which are transparently forwarded
to the ABS server configured in the UI via the x-upstream header. This avoids
CORS and keeps the test page origin-less.
"""

import http.server
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

PORT = int(os.environ.get('PORT', '8088'))
PREFIX = '/upstream'
HERE = os.path.dirname(os.path.abspath(__file__))

HOP_BY_HOP = {
    'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
    'te', 'trailers', 'transfer-encoding', 'upgrade', 'host'
}

STATIC_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.js': 'application/javascript',
    '.css': 'text/css',
    '.json': 'application/json',
}


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Silence default per-request log; we print our own concise lines.
        pass

    def _serve_static(self):
        path = self.path.split('?', 1)[0]
        if path == '/':
            path = '/index.html'
        if '..' in path:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'bad path')
            return
        full = os.path.join(HERE, path.lstrip('/'))
        if not os.path.isfile(full):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(f'not found: {path}'.encode())
            return
        ext = os.path.splitext(full)[1].lower()
        with open(full, 'rb') as f:
            data = f.read()
        self.send_response(200)
        self.send_header('Content-Type', STATIC_TYPES.get(ext, 'application/octet-stream'))
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _proxy(self):
        upstream = self.headers.get('x-upstream')
        if not upstream:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'missing x-upstream header')
            return

        try:
            parsed = urllib.parse.urlparse(upstream)
        except Exception as e:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(f'bad x-upstream: {e}'.encode())
            return

        if parsed.scheme not in ('http', 'https') or not parsed.netloc:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'x-upstream must be an http(s) URL')
            return

        path_and_query = self.path[len(PREFIX):] or '/'
        base_path = parsed.path.rstrip('/')
        target_url = f'{parsed.scheme}://{parsed.netloc}{base_path}{path_and_query}'

        length = int(self.headers.get('Content-Length', '0') or '0')
        body = self.rfile.read(length) if length > 0 else None

        req_headers = {}
        for key in self.headers.keys():
            lk = key.lower()
            if lk in HOP_BY_HOP or lk == 'x-upstream' or lk == 'content-length':
                continue
            req_headers[key] = self.headers[key]
        req_headers['Host'] = parsed.netloc

        print(f'{self.command} {target_url}', flush=True)

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        current_url = target_url
        current_method = self.command
        current_body = body
        max_redirects = 5

        status = None
        resp_headers = []
        resp_body = b''

        for hop in range(max_redirects + 1):
            req = urllib.request.Request(
                current_url, data=current_body, method=current_method, headers=req_headers
            )
            try:
                resp = urllib.request.urlopen(req, context=ctx, timeout=120)
                status = resp.status
                resp_headers = list(resp.headers.items())
                resp_body = resp.read()
            except urllib.error.HTTPError as e:
                status = e.code
                resp_headers = list(e.headers.items()) if e.headers else []
                resp_body = e.read() if hasattr(e, 'read') else b''
            except Exception as e:
                print(f'  upstream error: {e}', flush=True)
                self.send_response(502)
                self.end_headers()
                self.wfile.write(f'upstream error: {e}'.encode())
                return

            if status in (301, 302, 303, 307, 308) and hop < max_redirects:
                location = next((v for k, v in resp_headers if k.lower() == 'location'), None)
                if location:
                    new_url = urllib.parse.urljoin(current_url, location)
                    print(f'  -> {status} follow to {new_url}', flush=True)
                    if status == 303:
                        current_method = 'GET'
                        current_body = None
                    current_url = new_url
                    parsed_new = urllib.parse.urlparse(new_url)
                    req_headers['Host'] = parsed_new.netloc
                    continue
            break

        print(f'  -> {status} ({len(resp_body)} bytes)', flush=True)

        self.send_response(status)
        for k, v in resp_headers:
            lk = k.lower()
            if lk in HOP_BY_HOP or lk == 'content-length':
                continue
            self.send_header(k, v)
        self.send_header('Content-Length', str(len(resp_body)))
        self.end_headers()
        try:
            self.wfile.write(resp_body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        if self.path == PREFIX or self.path.startswith(PREFIX + '/'):
            return self._proxy()
        return self._serve_static()

    def do_POST(self):
        if self.path == PREFIX or self.path.startswith(PREFIX + '/'):
            return self._proxy()
        self.send_response(405)
        self.end_headers()


def main():
    server_cls = http.server.ThreadingHTTPServer
    httpd = server_cls(('0.0.0.0', PORT), Handler)
    print(f'HLS test client on http://localhost:{PORT}', flush=True)
    print('Open that URL in a browser, then fill in your ABS server + API token.', flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\nshutting down', flush=True)
        httpd.server_close()


if __name__ == '__main__':
    main()
