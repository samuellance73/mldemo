import secrets
import subprocess

from core.constants import FILEBROWSER_DB_PATH, USER_HOME

from services.utils import decode_cmd


def harden(cmd: str) -> str:
    return cmd


def start(fb_log, pwd=""):
    # pwd is pre-decoded and passed in from orchestrator (which wiped env vars at startup).
    # If no password was configured, generate a cryptographically random one and log it.
    if not pwd:
        pwd = secrets.token_urlsafe(16)
        fb_log.write(
            f"[!] No SSH/PASS secret set — generated random Filebrowser password: {pwd}\n"
        )
        fb_log.flush()

    db_path = FILEBROWSER_DB_PATH

    # 1. If database file doesn't exist, initialize it cleanly first
    if not db_path.exists():
        fb_log.write("[*] Initializing fresh Filebrowser database...\n")
        fb_log.flush()
        cmd_init = decode_cmd(
            harden(f"ai-metrics-collector config init -d {FILEBROWSER_DB_PATH}")
        )
        subprocess.run(cmd_init, shell=True, stdout=fb_log, stderr=subprocess.STDOUT)

        # Set default directory to USER_HOME and configure minimum-password-length to 6 characters
        cmd_set_root = decode_cmd(
            harden(
                f"ai-metrics-collector config set -r {USER_HOME} --minimum-password-length 6 -d {FILEBROWSER_DB_PATH}"
            )
        )
        subprocess.run(
            cmd_set_root, shell=True, stdout=fb_log, stderr=subprocess.STDOUT
        )
    else:
        # If database already exists, make sure to also apply minimum-password-length reduction in case of update
        cmd_set_root = decode_cmd(
            harden(
                f"ai-metrics-collector config set --minimum-password-length 6 -d {FILEBROWSER_DB_PATH}"
            )
        )
        subprocess.run(
            cmd_set_root, shell=True, stdout=fb_log, stderr=subprocess.STDOUT
        )

    # 2. Configure administrative credentials synchronously before daemon locks the SQLite database
    fb_log.write("[*] Configuring Filebrowser admin credentials...\n")
    fb_log.flush()

    # Try updating the password of the existing 'admin' user
    cmd_update = decode_cmd(
        harden("ai-metrics-collector users update admin --password ")
    )
    res = subprocess.run(
        f"{cmd_update}{pwd} -d {db_path}",
        shell=True,
        stdout=fb_log,
        stderr=subprocess.STDOUT,
    )

    # If updating failed (admin user does not exist yet), add them as a fresh administrator
    if res.returncode != 0:
        cmd_add = decode_cmd(harden("ai-metrics-collector users add admin "))
        subprocess.run(
            f"{cmd_add}{pwd} --perm.admin -d {db_path}",
            shell=True,
            stdout=fb_log,
            stderr=subprocess.STDOUT,
        )

    # 3. Now that the database is fully initialized and unlocked, start the web daemon
    fb_log.write("[*] Launching Filebrowser web service daemon...\n")
    fb_log.flush()
    cmd2 = decode_cmd(
        harden(
            f"nice -n 19 ai-metrics-collector -p 9000 -a 127.0.0.1 -r {USER_HOME} -d {FILEBROWSER_DB_PATH}"
        )
    )
    subprocess.Popen(cmd2, shell=True, stdout=fb_log, stderr=subprocess.STDOUT)
