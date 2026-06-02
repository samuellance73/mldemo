import os
import signal
import sys
import threading
import time
from pathlib import Path

# Import your corrected storage sync service
from sanctuary.services import storage_sync_service

# Configuration Constants
SYNC_INTERVAL_SECONDS = 120  # 30 minutes
LOCAL_DIR = Path("./my_local_data")

# Read configurations from environment variables (Never hardcode secrets!)
REPO_ID = os.getenv("HF_STORAGE_REPO") or "username/dataset-name"
TOKEN = os.getenv("HF_TOKEN") or "hf_your_actual_token"

# An Event behaves like an interruptible sleep
shutdown_event = threading.Event()


def handle_shutdown(signum, frame):
    """Graceful termination handler to execute a final push before exit."""
    print(f"\n[*] Shutdown signal ({signum}) caught. Executing final state push...")
    try:
        storage_sync_service.start(
            storage_log=sys.stdout,
            sync_type="huggingface",
            action="push",
            sync_dir=LOCAL_DIR,
            repo_id=REPO_ID,
            token=TOKEN,
            commit_message="Graceful shutdown state commit"
        )
        print("[*] Final state push successful.")
    except Exception as e:
        print(f"[-] Final push failed during shutdown: {e}")

    shutdown_event.set()  # Break the sleep loop instantly
    sys.exit(0)


# Register system signals for graceful exit (SIGINT = Ctrl+C, SIGTERM = Platform Kill)
signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)

print("[*] Starting continuous auto-sync daemon...")

# ── PHASE 1: Boot-Time Restoration (Only run once!) ──
try:
    print("[*] Restoring remote state on boot...")
    storage_sync_service.start(
        storage_log=sys.stdout,
        sync_type="huggingface",
        action="pull",
        sync_dir=LOCAL_DIR,
        repo_id=REPO_ID,
        token=TOKEN
    )
    print("[*] Initial state restoration completed.")
except Exception as e:
    print(f"[-] Failed to restore remote state: {e}. Falling back to local files.")


# ── PHASE 2: Push-Only Background Loop ──
while not shutdown_event.is_set():
    # Sleep for 30 minutes, but exit INSTANTLY if a shutdown signal sets the event
    interrupted = shutdown_event.wait(SYNC_INTERVAL_SECONDS)
    if interrupted:
        break

    try:
        print(f"\n[*] Initiating scheduled push at {time.strftime('%Y-%m-%d %H:%M:%S')}")

        # Only push your local changes up. Never pull inside the loop
        # unless you have implemented complex file merging first.
        storage_sync_service.start(
            storage_log=sys.stdout,
            sync_type="huggingface",
            action="push",
            sync_dir=LOCAL_DIR,
            repo_id=REPO_ID,
            token=TOKEN,
            commit_message="Automated periodic sync"
        )
        print("[*] Scheduled push completed successfully.")
    except Exception as e:
        print(f"[-] Scheduled push failed: {e}. Retrying next interval.")

print("[*] Continuous auto-sync daemon stopped cleanly.")