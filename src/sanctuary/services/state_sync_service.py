import os
import signal
import sys
import threading
import time
from pathlib import Path

# Import your corrected storage sync service
from sanctuary.services import storage_sync_service
from sanctuary.core.constants import METRICS_DIR

# Configuration Constants
SYNC_INTERVAL_SECONDS = 180  # Sync interval in seconds
# Sync the real state directory where all services store their persistent data
# (tailscale state, filebrowser.db, cloudflare URLs, ligolo fingerprints, etc.)
LOCAL_DIR = Path(METRICS_DIR)

# Initialize empty placeholders to be populated dynamically on startup
SYNC_KWARGS = {}
SYNC_TYPE = "huggingface"
shutdown_event = threading.Event()


def handle_shutdown(signum, frame):
    """Graceful termination handler to execute a final push before exit."""
    print(f"\n[*] Shutdown signal ({signum}) caught. Executing final state push...")
    try:
        storage_sync_service.start(
            storage_log=sys.stdout,
            sync_type=SYNC_TYPE,
            action="push",
            sync_dir=LOCAL_DIR,
            commit_message="Graceful shutdown state commit",
            **SYNC_KWARGS
        )
        print("[*] Final state push successful.")
    except Exception as e:
        print(f"[-] Final push failed during shutdown: {e}")

    shutdown_event.set()  # Break the sleep loop instantly
    sys.exit(0)


# Register system signals for graceful exit (SIGINT = Ctrl+C, SIGTERM = Platform Kill)
signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)


def _loop(storage_log, sync_type, sync_kwargs):
    """Main background loop."""
    while not shutdown_event.is_set():
        # Sleep, but exit instantly if a shutdown event is set
        interrupted = shutdown_event.wait(SYNC_INTERVAL_SECONDS)
        if interrupted:
            break

        try:
            print(f"\n[*] Initiating scheduled push at {time.strftime('%Y-%m-%d %H:%M:%S')}")
            storage_sync_service.start(
                storage_log=storage_log,
                sync_type=sync_type,
                action="push",
                sync_dir=LOCAL_DIR,
                commit_message="Automated periodic sync",
                **sync_kwargs
            )
        except Exception as e:
            print(f"[-] Scheduled push failed: {e}. Retrying next interval.")


def start(storage_log, sync_type="huggingface", **kwargs):
    """Called by orchestrator.py to bootstrap the sync loop daemon."""
    global SYNC_TYPE, SYNC_KWARGS
    
    # Save options for background / shutdown processes
    SYNC_TYPE = sync_type
    SYNC_KWARGS = kwargs

    # Prepare local staging path defensively
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)

    print("[*] Starting continuous auto-sync daemon...")

    # PHASE 1: Boot-Time Restoration (Only run once!)
    try:
        print("[*] Restoring remote state on boot...")
        storage_sync_service.start(
            storage_log=storage_log,
            sync_type=sync_type,
            action="pull",
            sync_dir=LOCAL_DIR,
            **kwargs
        )
        print("[*] Initial state restoration completed.")
    except Exception as e:
        print(f"[-] Failed to restore remote state: {e}. Falling back to local files.")

    # PHASE 2: Start background loop thread
    t = threading.Thread(
        target=_loop,
        args=(storage_log, sync_type, SYNC_KWARGS),
        daemon=True
    )
    t.start()