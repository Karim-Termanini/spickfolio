import os
import socket
import threading
import time

from spick_folio import config
from spick_folio.capabilities import check_parquet_available, check_r_available, ensure_kaggle_venv
from spick_folio.handler import Handler
from spick_folio.rate_limit import ThreadPoolHTTPServer
from spick_folio.rdatasets_loader import load_rdatasets


def run():
    check_r_available()
    check_parquet_available()

    def background_init():
        load_rdatasets()
        ensure_kaggle_venv()

    threading.Thread(target=background_init, daemon=True).start()

    def watchdog():
        while True:
            time.sleep(5)
            if time.time() - config.last_heartbeat > config.HEARTBEAT_TIMEOUT:
                print("Heartbeat expired — shutting down.")
                os._exit(0)

    threading.Thread(target=watchdog, daemon=True).start()

    port = 18700
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.bind(('127.0.0.1', port))
        s.close()
    except OSError:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('127.0.0.1', 0))
        port = s.getsockname()[1]
        s.close()

    os.makedirs(config.CACHE_DIR, exist_ok=True)
    with open(os.path.join(config.CACHE_DIR, 'port'), 'w') as f:
        f.write(str(port))
    with open(os.path.join(config.CACHE_DIR, 'server.pid'), 'w') as f:
        f.write(str(os.getpid()))

    server = ThreadPoolHTTPServer(('127.0.0.1', port), Handler, max_workers=10)
    print(f"Python server listening on 127.0.0.1:{port}")
    server.serve_forever()
