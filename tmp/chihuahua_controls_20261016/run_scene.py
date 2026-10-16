"""Run one task script through the active local Maya listener."""
import json
from pathlib import Path
import socket
import sys

path = str(Path(sys.argv[1]).resolve())
code = "import runpy\nns=runpy.run_path(%r)\nresult=ns.get('result')" % path
with socket.create_connection(('127.0.0.1',9877),timeout=10) as connection:
    connection.settimeout(180)
    connection.sendall((json.dumps({'type':'execute_python','params':{'code':code}})+'\n').encode())
    response = b''
    while b'\n' not in response:
        block = connection.recv(65536)
        if not block:
            break
        response += block
print(response.decode())
