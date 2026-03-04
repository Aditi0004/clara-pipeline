from http.server import BaseHTTPRequestHandler, HTTPServer
import json, subprocess, urllib.parse

class Handler(BaseHTTPRequestHandler):

    def do_POST(self):
        length = int(self.headers['Content-Length'])
        body = json.loads(self.rfile.read(length))
        path = self.path
        if path == '/pipeline-a':
            cmd = ['python','scripts/pipeline.py','demo',
                   body['transcript_path'],'--company',body.get('company','')]
        elif path == '/pipeline-b':
            cmd = ['python','scripts/pipeline.py','onboard',
                   body['account_id'], body['onboarding_path']]
        else:
            self.send_response(404); self.end_headers(); return
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.send_response(200)
        self.send_header('Content-Type','application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'output': result.stdout}).encode())
    def log_message(self, *a): pass

HTTPServer(('', 8080), Handler).serve_forever()