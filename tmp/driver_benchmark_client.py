import argparse
import socket
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('script')
p.add_argument('--port', type=int, default=7002)
args = p.parse_args()
script = str(Path(args.script).resolve())
with socket.create_connection(('127.0.0.1', args.port), 5) as conn:
    conn.settimeout(600)
    conn.sendall(('import runpy; runpy.run_path(%r)\n' % script).encode())
    print(conn.recv(65536).decode(errors='replace'))
