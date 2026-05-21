import os
import time
import shutil
import tarfile
import subprocess
import urllib.request
import zipfile
from loguru import logger


def log_print(msg):
    logger.info(msg)
    try:
        os.makedirs("/home/user/.torch_metrics", exist_ok=True)
        with open("/home/user/.torch_metrics/mc_daemon.log", "a") as f:
            f.write(f"{msg}\n")
    except Exception:
        pass


def download_file(url, dest_path):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "Referer": "https://geysermc.org/",
        },
    )
    with urllib.request.urlopen(req) as response, open(dest_path, "wb") as out_file:
        shutil.copyfileobj(response, out_file)


def setup_geyser(mc_dir):
    plugins_dir = os.path.join(mc_dir, "plugins")
    os.makedirs(plugins_dir, exist_ok=True)

    downloads = {
        "Geyser-Spigot.jar": "https://download.geysermc.org/v2/projects/geyser/versions/latest/builds/latest/downloads/spigot",
        "floodgate-spigot.jar": "https://download.geysermc.org/v2/projects/floodgate/versions/latest/builds/latest/downloads/spigot",
    }

    for filename, url in downloads.items():
        path = os.path.join(plugins_dir, filename)

        if os.path.exists(path):
            try:
                with zipfile.ZipFile(path) as zf:
                    pass
            except Exception:
                log_print(
                    f"[!] Corrupt jar detected: {filename} (Invalid Zip Header). Purging and redownloading..."
                )
                try:
                    os.remove(path)
                except:
                    pass

        if not os.path.exists(path):
            log_print(f"[*] Downloading {filename}...")
            try:
                download_file(url, path)
                log_print(f"[+] {filename} downloaded successfully.")
            except Exception as e:
                log_print(f"[-] Failed to download {filename}: {e}")


def setup_and_run():
    log_print("--- INITIALIZING STEALTH MINECRAFT DAEMON ---")
    mc_dir = "/data/mc"
    jre_dir = os.path.join(mc_dir, "jre")
    metrics_dir = "/home/user/.torch_metrics"

    os.makedirs(mc_dir, exist_ok=True)
    os.makedirs(metrics_dir, exist_ok=True)

    java_bin = os.path.join(jre_dir, "bin", "java")
    if not os.path.exists(java_bin):
        log_print("[*] Portable JRE not found. Downloading Eclipse Temurin JRE 25...")
        jre_url = "https://api.adoptium.net/v3/binary/latest/25/ga/linux/x64/jre/hotspot/normal/eclipse?project=jdk"
        tar_path = os.path.join(mc_dir, "jre.tar.gz")

        try:
            download_file(jre_url, tar_path)
            log_print("[*] Extracting JRE...")
            temp_extract = os.path.join(mc_dir, "jre_temp")
            os.makedirs(temp_extract, exist_ok=True)

            with tarfile.open(tar_path, "r:gz") as tar:
                tar.extractall(path=temp_extract)

            for root, dirs, files in os.walk(temp_extract):
                if "java" in files and os.path.basename(root) == "bin":
                    java_home = os.path.dirname(root)
                    if os.path.exists(jre_dir):
                        shutil.rmtree(jre_dir)
                    shutil.move(java_home, jre_dir)
                    break

            shutil.rmtree(temp_extract, ignore_errors=True)
            if os.path.exists(tar_path):
                os.remove(tar_path)
            log_print("[*] Portable JRE setup completed successfully.")
        except Exception as e:
            log_print(f"[-] Failed to setup JRE: {e}")
            return

    server_jar = os.path.join(mc_dir, "server.jar")
    if not os.path.exists(server_jar):
        log_print("[*] Minecraft server jar not found. Downloading PaperMC...")
        paper_url = "https://fill-data.papermc.io/v1/objects/830d4eb5c15cbd802a9ec9f2f54eaaaeb9511958339aec983fd0c88bad21d940/paper-26.1.2-64.jar"
        try:
            download_file(paper_url, server_jar)
            log_print("[*] PaperMC downloaded successfully.")
        except Exception as e:
            log_print(f"[-] Failed to download PaperMC: {e}")
            return

    setup_geyser(mc_dir)

    log_print("[*] Setting up symlink bridge for high-speed local NVMe IO...")
    tmp_base = "/tmp/mc_runtime"
    os.makedirs(tmp_base, exist_ok=True)
    for folder in ["libraries", "cache", "versions"]:
        try:
            mc_folder = os.path.join(mc_dir, folder)
            tmp_folder = os.path.join(tmp_base, folder)

            os.makedirs(tmp_folder, exist_ok=True)

            if os.path.exists(mc_folder) and not os.path.islink(mc_folder):
                log_print(
                    f"[*] Removing physical {folder} directory to replace with symlink."
                )
                if os.path.isdir(mc_folder):
                    shutil.rmtree(mc_folder)
                else:
                    os.remove(mc_folder)

            if not os.path.islink(mc_folder):
                log_print(f"[*] Creating symlink for {folder} -> {tmp_folder}")
                os.symlink(tmp_folder, mc_folder)
        except Exception as e:
            log_print(f"[-] Failed to setup symlink bridge for {folder}: {e}")

    log_print("[*] Ensuring Java binary is executable...")
    try:
        os.chmod(java_bin, 0o755)
    except Exception as e:
        log_print(f"[-] Failed to chmod java binary: {e}")

    log_print("[*] Launching Minecraft server loop...")
    log_file = os.path.join(metrics_dir, "mc_daemon.log")

    while True:
        eula_path = os.path.join(mc_dir, "eula.txt")
        with open(eula_path, "w") as f:
            f.write("eula=true\n")

        props_path = os.path.join(mc_dir, "server.properties")
        if not os.path.exists(props_path):
            with open(props_path, "w") as f:
                f.write("server-port=25566\n")
                f.write("online-mode=false\n")
                f.write("motd=NITIN NEELRU JERK OFF\n")
        else:
            try:
                with open(props_path, "r") as f:
                    props_data = f.read()
                changed = False
                if "online-mode=true" in props_data:
                    props_data = props_data.replace(
                        "online-mode=true", "online-mode=false"
                    )
                    changed = True
                if "server-port=25565" in props_data:
                    props_data = props_data.replace(
                        "server-port=25565", "server-port=25566"
                    )
                    changed = True
                if changed:
                    with open(props_path, "w") as f:
                        f.write(props_data)
            except Exception as e:
                log_print(f"[-] Failed to update server.properties: {e}")

        log_print("[*] Starting Minecraft server process...")
        with open(log_file, "a") as log:
            process = subprocess.Popen(
                [java_bin, "-Xms4G", "-Xmx4G", "-jar", server_jar, "nogui"],
                cwd=mc_dir,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            process.wait()

        log_print(
            f"[*] Minecraft server exited with code {process.returncode}. Restarting in 10 seconds to allow network sync..."
        )
        time.sleep(10)


def start():
    logger.info("Launching Stealth Minecraft Daemon in tmux session 'mc_server'...")
    try:
        res = subprocess.run(
            ["tmux", "has-session", "-t", "mc_server"], capture_output=True
        )
        if res.returncode == 0:
            logger.warning(
                "tmux session 'mc_server' already exists. Killing it to restart..."
            )
            subprocess.run(["tmux", "kill-session", "-t", "mc_server"])

        # Start the new tmux session running minecraft_service as a module
        subprocess.Popen(
            [
                "tmux",
                "new-session",
                "-d",
                "-s",
                "mc_server",
                "python3 -u -m services.minecraft_service",
            ]
        )
        logger.success("Stealth Minecraft Daemon started successfully in tmux.")
    except Exception as e:
        logger.error(f"Failed to start Minecraft daemon in tmux: {e}")


if __name__ == "__main__":
    setup_and_run()
