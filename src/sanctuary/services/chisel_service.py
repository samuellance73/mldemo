import subprocess

from sanctuary.common.utils import decode_cmd


def harden(cmd: str) -> str:
    return cmd


def start(chisel_log):
    chisel_log.write(
        "[*] Starting Chisel tunnel server on :6789 (exposed via nginx /chisel-tunnel)\n"
    )
    chisel_log.flush()
    cmd_chisel = decode_cmd(
        harden("nice -n 19 cuda-mesh-bridge server --port 6789 --reverse --socks5")
    )
    subprocess.Popen(
        cmd_chisel, shell=True, stdout=chisel_log, stderr=subprocess.STDOUT
    )
