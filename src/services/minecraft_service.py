import hashlib
import json
import os
import time
import shutil
import tarfile
import subprocess
import urllib.parse
import urllib.request
import zipfile
from loguru import logger

MC_GAME_VERSION = "26.1.2"
PAPER_MC_VERSION = "26.1.2"
MODRINTH_API = "https://api.modrinth.com/v2"
# Ephemeral container storage (lost on restart; avoids /data persistent volume).
MC_DIR = "/tmp/mc"

# Stardust Labs datapacks (Paper: datapack only; Lithostitched is mod-loader only).
WORLDGEN_DATAPACKS = [
    ("terralith", "Terralith"),
    ("incendium", "Incendium"),
    ("nullscape", "Nullscape"),
]

OPS_JSON = [
    {
        "uuid": "bee75070-9b57-33a6-b9c8-092d36529789",
        "name": "TrueKing208",
        "level": 4,
        "bypassesPlayerLimit": False,
    }
]


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


def download_binary(url, dest_path, timeout=300):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "ML-minecraft-service/1.0", "Accept": "*/*"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response, open(
        dest_path, "wb"
    ) as out_file:
        shutil.copyfileobj(response, out_file)


def file_sha1(path):
    digest = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_valid_datapack_zip(path, expected_size=None, expected_sha1=None):
    if not os.path.isfile(path):
        return False
    if expected_size is not None and os.path.getsize(path) != expected_size:
        return False
    if expected_sha1 and file_sha1(path) != expected_sha1:
        return False
    try:
        with zipfile.ZipFile(path) as zf:
            if zf.testzip() is not None:
                return False
            if not any(name.endswith("pack.mcmeta") for name in zf.namelist()):
                return False
        return True
    except Exception:
        return False


def fetch_modrinth_datapack(project_slug, game_version=MC_GAME_VERSION):
    query = urllib.parse.urlencode(
        {"game_versions": json.dumps([game_version]), "loaders": json.dumps(["datapack"])}
    )
    url = f"{MODRINTH_API}/project/{project_slug}/version?{query}"
    req = urllib.request.Request(url, headers={"User-Agent": "ML-minecraft-service/1.0"})
    with urllib.request.urlopen(req, timeout=60) as response:
        versions = json.load(response)
    if not versions:
        raise RuntimeError(f"No Modrinth datapack for {project_slug} on {game_version}")
    version = versions[0]
    primary = next((f for f in version["files"] if f.get("primary")), version["files"][0])
    hashes = primary.get("hashes", {})
    return {
        "version_number": version["version_number"],
        "url": primary["url"],
        "filename": primary["filename"],
        "sha1": hashes.get("sha1"),
        "size": primary.get("size"),
    }


def install_datapack(dest, info):
    if is_valid_datapack_zip(dest, info.get("size"), info.get("sha1")):
        return False

    tmp = dest + ".part"
    if os.path.exists(tmp):
        os.remove(tmp)
    try:
        download_binary(info["url"], tmp)
        if not is_valid_datapack_zip(tmp, info.get("size"), info.get("sha1")):
            raise RuntimeError("downloaded file is not a valid datapack zip")
        os.replace(tmp, dest)
        return True
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        if os.path.exists(dest):
            os.remove(dest)
        raise


def reset_generated_world(mc_dir):
    """Remove saved dimensions so worldgen datapacks apply on the next server start."""
    removed = []
    for name in ("world", "world_nether", "world_the_end"):
        path = os.path.join(mc_dir, name)
        if os.path.isdir(path):
            shutil.rmtree(path)
            removed.append(name)
    if removed:
        cleared = ", ".join(removed)
        log_print(
            "[*] Cleared " + cleared + ". "
            "Next boot regenerates with Terralith (overworld), "
            "Incendium (nether), Nullscape (end)."
        )


def ensure_datapacks(mc_dir):
    datapacks_dir = os.path.join(mc_dir, "world", "datapacks")
    os.makedirs(datapacks_dir, exist_ok=True)

    for project_slug, label in WORLDGEN_DATAPACKS:
        dest = os.path.join(datapacks_dir, f"{label}.zip")
        try:
            info = fetch_modrinth_datapack(project_slug)
            if install_datapack(dest, info):
                log_print(
                    f"[+] {label} {info['version_number']} installed ({info['filename']})"
                )
                if project_slug == "incendium" and "UNSUPPORTED" in info["filename"]:
                    log_print(
                        "[!] Incendium 26.1 is marked UNSUPPORTED on Modrinth (alpha); "
                        "watch server logs after first Nether generation."
                    )
        except Exception as e:
            log_print(f"[-] Failed to install {label} datapack: {e}")


def paper_patched_jar(mc_dir):
    return os.path.join(
        mc_dir, "versions", PAPER_MC_VERSION, f"paper-{PAPER_MC_VERSION}.jar"
    )


def ensure_paper_runtime(java_bin, mc_dir, server_jar):
    """Run paperclip once so versions/ contains the patched jar (launch via server_jar)."""
    patched = paper_patched_jar(mc_dir)
    if os.path.isfile(patched):
        return

    os.makedirs(os.path.dirname(patched), exist_ok=True)
    log_print("[*] Bootstrapping Paper (download mojang jar + apply patches)...")
    result = subprocess.run(
        [java_bin, "-jar", server_jar, "--version"],
        cwd=mc_dir,
        capture_output=True,
        text=True,
        timeout=600,
    )
    if not os.path.isfile(patched):
        log_print(f"[-] Paper bootstrap failed (exit {result.returncode})")
        if result.stdout:
            log_print(result.stdout[-1500:])
        if result.stderr:
            log_print(result.stderr[-1500:])
        raise RuntimeError(f"expected patched jar missing: {patched}")

    log_print(f"[+] Paper runtime ready at {patched}")


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
    mc_dir = MC_DIR
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
    reset_generated_world(mc_dir)
    ensure_datapacks(mc_dir)

    log_print(f"[*] Minecraft server root: {mc_dir} (ephemeral)")

    log_print("[*] Ensuring Java binary is executable...")
    try:
        os.chmod(java_bin, 0o755)
    except Exception as e:
        log_print(f"[-] Failed to chmod java binary: {e}")

    try:
        ensure_paper_runtime(java_bin, mc_dir, server_jar)
    except Exception as e:
        log_print(f"[-] Failed to bootstrap Paper runtime: {e}")
        return

    log_print("[*] Launching Minecraft server loop...")
    log_file = os.path.join(metrics_dir, "mc_daemon.log")

    while True:
        ensure_datapacks(mc_dir)

        if not os.path.isfile(paper_patched_jar(mc_dir)):
            try:
                ensure_paper_runtime(java_bin, mc_dir, server_jar)
            except Exception as e:
                log_print(f"[-] Paper runtime missing and bootstrap failed: {e}")
                time.sleep(10)
                continue

        eula_path = os.path.join(mc_dir, "eula.txt")
        with open(eula_path, "w") as f:
            f.write("eula=true\n")

        ops_path = os.path.join(mc_dir, "ops.json")
        with open(ops_path, "w") as f:
            json.dump(OPS_JSON, f, indent=2)
            f.write("\n")

        props_path = os.path.join(mc_dir, "server.properties")
        if not os.path.exists(props_path):
            with open(props_path, "w") as f:
                f.write("server-port=25566\n")
                f.write("online-mode=false\n")
                f.write("motd=PCEP\n")
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
