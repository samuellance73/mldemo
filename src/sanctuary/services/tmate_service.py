import subprocess

from loguru import logger

PREFIX = "[TMATE]"


def start(log):
    """
    Start tmate terminal sharing service.
    Provides instant terminal sharing via tmate.io.
    """
    logger.info(f"{PREFIX} Starting tmate service...")
    
    log.write(f"{PREFIX} Starting tmate terminal sharing...\n")
    log.flush()
    
    # Start tmate in daemon mode with logging
    cmd = ["tmate", "-F"]
    subprocess.Popen(
        cmd,
        stdout=log,
        stderr=subprocess.STDOUT
    )
    
    logger.success(f"{PREFIX} Tmate service started")
