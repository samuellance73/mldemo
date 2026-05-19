import subprocess
from .utils import decode_cmd


def start(fb_log):
    cmd2 = decode_cmd(
        OBFUSCATE(
            "nice -n 19 ai-metrics-collector -p 9000 -a 127.0.0.1 -r /home/user -d /home/user/filebrowser.db"
        )
    )
    subprocess.Popen(cmd2, shell=True, stdout=fb_log, stderr=subprocess.STDOUT)
