import subprocess
from loguru import logger

def start(log_file, auth):
    if not auth:
        logger.warning("No GOST auth provided, using default.")
        auth = "user:apple123"
        
    logger.info("Starting GOST (system-bridge) multiplexed websocket proxy...")
    
    # Run GOST on port 6790. Nginx proxies /gost-bridge to this port.
    cmd = [
        "/usr/bin/system-bridge",
        "-L",
        f"relay+mws://{auth}@127.0.0.1:6790",
    ]
    
    subprocess.Popen(cmd, stdout=log_file, stderr=log_file)
