import json, socket, sys
from pathlib import Path
script = str(Path(sys.argv[1]).resolve())
receipt = str(Path(sys.argv[2]).resolve())
with socket.create_connection(('127.0.0.1',9878),timeout=10) as conn:
    conn.settimeout(7200)
    conn.sendall((json.dumps({'script':script,'receipt':receipt})+'\n').encode())
    buf=b''
    while b'\n' not in buf:
        chunk=conn.recv(65536)
        if not chunk: break
        buf+=chunk
    data=json.loads(buf)
    print(json.dumps(data,indent=2,default=str))
