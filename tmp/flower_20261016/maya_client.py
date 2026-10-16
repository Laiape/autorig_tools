import json
import socket
import sys
from pathlib import Path
code = Path(sys.argv[1]).read_text(encoding='utf-8')
with socket.create_connection(('127.0.0.1', 9878), timeout=5) as conn:
    conn.settimeout(600)
    conn.sendall((json.dumps({'type': 'execute_python', 'params': {'code': code}})+'\n').encode())
    data = b''
    while b'\n' not in data:
        chunk = conn.recv(65536)
        if not chunk:
            break
        data += chunk
    print(data.decode())
