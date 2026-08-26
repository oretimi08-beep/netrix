import os
import json
from http.server import BaseHTTPRequestHandler

_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)


def _ls(path):
    try:
        return sorted(os.listdir(path))
    except Exception as e:
        return 'ERROR: ' + str(e)


INFO = {
    'here': _HERE,
    'parent': _PARENT,
    'ls_here': _ls(_HERE),
    'ls_parent': _ls(_PARENT),
    'app_dir_in_here': os.path.isdir(os.path.join(_HERE, 'app')),
    'app_dir_in_parent': os.path.isdir(os.path.join(_PARENT, 'app')),
    'cwd': os.getcwd(),
}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(INFO, indent=2).encode())
