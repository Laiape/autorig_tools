"""Send a script to an explicitly selected local Maya trial command port."""
import argparse
import json
from pathlib import Path
import socket
import time


def dispatch(script, receipt, port=7102, arguments=None):
    script, receipt = Path(script).resolve(), Path(receipt).resolve()
    if not script.is_file() or receipt.exists():
        raise ValueError("Use an existing script and a new receipt path.")
    code = ("import json,traceback,runpy\nfrom pathlib import Path\n"
            "if not Path(%r).exists():\n"
            " try:\n  namespace=runpy.run_path(%r,init_globals={'TRIAL_ARGUMENTS':%r})\n"
            "  result={'success':True,'result':namespace.get('result')}\n"
            " except BaseException:\n  result={'success':False,'traceback':traceback.format_exc()}\n"
            " Path(%r).write_text(json.dumps(result,indent=2,default=str),encoding='utf-8')\n"
            % (str(receipt), str(script), arguments or {}, str(receipt)))
    receipt.parent.mkdir(parents=True, exist_ok=True)
    with socket.create_connection(("127.0.0.1", port), timeout=5) as connection:
        connection.settimeout(.25)
        connection.sendall(("exec(" + repr(code) + ")\n").encode("utf-8"))
        # echoOutput can send unrelated pending log lines before this command runs.
        # Keep the socket alive until the command's own receipt is committed.
        deadline = time.monotonic() + 600
        while not receipt.exists():
            if time.monotonic() >= deadline:
                raise TimeoutError('The trial command did not commit its receipt within 600 seconds.')
            try:
                if not connection.recv(65536):
                    raise ConnectionError('The trial session closed before writing its receipt.')
            except socket.timeout:
                continue
    return str(receipt)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("script")
    parser.add_argument("receipt")
    parser.add_argument("--port", type=int, default=7102)
    parser.add_argument("--arguments", default="{}")
    options = parser.parse_args()
    print(dispatch(options.script, options.receipt, options.port,
                   json.loads(options.arguments)))
