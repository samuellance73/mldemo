import subprocess
from loguru import logger

def start(log_file):
    auth = "user:apple123"
        
    logger.info("Starting GOST (system-bridge) multiplexed websocket proxy...")
    
    # The server runs locally behind Nginx, hence plain mws is used
    cmd = [
        "/usr/bin/system-bridge",
        "-L",
        f"relay+mws://{auth}@127.0.0.1:6790?path=/gost-bridge",
    ]
    
    subprocess.Popen(cmd, stdout=log_file, stderr=log_file)
