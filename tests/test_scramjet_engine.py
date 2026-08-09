import time
import urllib.request
import json
from sanctuary.services.scramjet_service import start, PORT

def test_scramjet_service_start():
    class DummyLog:
        def write(self, msg): pass
        def flush(self): pass

    proc = start(DummyLog())
    assert proc is not None, "Scramjet process failed to start"

    # Wait briefly for Node.js process initialization
    time.sleep(2)

    try:
        req = urllib.request.urlopen(f"http://127.0.0.1:{PORT}/proxy/health", timeout=5)
        data = json.loads(req.read().decode('utf-8'))
        assert data.get("status") == "ok"
        assert data.get("engine") == "wasm"
        print("Scramjet WASM health check passed successfully!")
    finally:
        if proc:
            proc.terminate()

if __name__ == "__main__":
    test_scramjet_service_start()
