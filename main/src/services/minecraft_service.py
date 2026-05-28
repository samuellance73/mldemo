import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from loguru import logger

MC_GAME_VERSION = "26.1.2"
PAPER_MC_VERSION = "26.1.2"
MODRINTH_API = "https://api.modrinth.com/v2"
# Ephemeral container storage (lost on restart; avoids /data persistent volume).
MC_DIR = Path("/tmp/mc")

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
        metrics_dir = Path("/home/user/.torch_metrics")
        metrics_dir.mkdir(parents=True, exist_ok=True)
        log_file = metrics_dir / "mc_daemon.log"
        with log_file.open("a") as f:
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
    with urllib.request.urlopen(req) as response, Path(dest_path).open("wb") as out_file:
        shutil.copyfileobj(response, out_file)


def download_binary(url, dest_path, timeout=300):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "ML-minecraft-service/1.0", "Accept": "*/*"},
    )
    with (
        urllib.request.urlopen(req, timeout=timeout) as response,
        Path(dest_path).open("wb") as out_file,
    ):
        shutil.copyfileobj(response, out_file)


def file_sha1(path):
    digest = hashlib.sha1()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_valid_datapack_zip(path, expected_size=None, expected_sha1=None):
    path_obj = Path(path)
    if not path_obj.is_file():
        return False
    if expected_size is not None and path_obj.stat().st_size != expected_size:
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
        {
            "game_versions": json.dumps([game_version]),
            "loaders": json.dumps(["datapack"]),
        }
    )
    url = f"{MODRINTH_API}/project/{project_slug}/version?{query}"
    req = urllib.request.Request(
        url, headers={"User-Agent": "ML-minecraft-service/1.0"}
    )
    with urllib.request.urlopen(req, timeout=60) as response:
        versions = json.load(response)
    if not versions:
        raise RuntimeError(f"No Modrinth datapack for {project_slug} on {game_version}")
    version = versions[0]
    primary = next(
        (f for f in version["files"] if f.get("primary")), version["files"][0]
    )
    hashes = primary.get("hashes", {})
    return {
        "version_number": version["version_number"],
        "url": primary["url"],
        "filename": primary["filename"],
        "sha1": hashes.get("sha1"),
        "size": primary.get("size"),
    }


def install_datapack(dest, info):
    dest_obj = Path(dest)
    if is_valid_datapack_zip(dest, info.get("size"), info.get("sha1")):
        return False

    tmp = Path(str(dest) + ".part")
    if tmp.exists():
        tmp.unlink()
    try:
        download_binary(info["url"], tmp)
        if not is_valid_datapack_zip(tmp, info.get("size"), info.get("sha1")):
            raise RuntimeError("downloaded file is not a valid datapack zip")
        tmp.replace(dest_obj)
        return True
    except Exception:
        if tmp.exists():
            tmp.unlink()
        if dest_obj.exists():
            dest_obj.unlink()
        raise


def reset_generated_world(mc_dir):
    """Remove saved dimensions so worldgen datapacks apply on the next server start."""
    removed = []
    mc_dir_obj = Path(mc_dir)
    for name in ("world", "world_nether", "world_the_end"):
        path = mc_dir_obj / name
        if path.is_dir():
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
    mc_dir_obj = Path(mc_dir)
    datapacks_dir = mc_dir_obj / "world" / "datapacks"
    datapacks_dir.mkdir(parents=True, exist_ok=True)

    for project_slug, label in WORLDGEN_DATAPACKS:
        dest = datapacks_dir / f"{label}.zip"
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
    return Path(mc_dir) / "versions" / PAPER_MC_VERSION / f"paper-{PAPER_MC_VERSION}.jar"


def ensure_paper_runtime(java_bin, mc_dir, server_jar):
    """Run paperclip once so versions/ contains the patched jar (launch via server_jar)."""
    patched = paper_patched_jar(mc_dir)
    if patched.is_file():
        return

    patched.parent.mkdir(parents=True, exist_ok=True)
    log_print("[*] Bootstrapping Paper (download mojang jar + apply patches)...")
    result = subprocess.run(
        [str(java_bin), "-jar", str(server_jar), "--version"],
        cwd=str(mc_dir),
        capture_output=True,
        text=True,
        timeout=600,
    )
    if not patched.is_file():
        log_print(f"[-] Paper bootstrap failed (exit {result.returncode})")
        if result.stdout:
            log_print(result.stdout[-1500:])
        if result.stderr:
            log_print(result.stderr[-1500:])
        raise RuntimeError(f"expected patched jar missing: {patched}")

    log_print(f"[+] Paper runtime ready at {patched}")


def setup_geyser(mc_dir):
    mc_dir_obj = Path(mc_dir)
    plugins_dir = mc_dir_obj / "plugins"
    plugins_dir.mkdir(parents=True, exist_ok=True)

    downloads = {
        "Geyser-Spigot.jar": "https://download.geysermc.org/v2/projects/geyser/versions/latest/builds/latest/downloads/spigot",
        "floodgate-spigot.jar": "https://download.geysermc.org/v2/projects/floodgate/versions/latest/builds/latest/downloads/spigot",
    }

    for filename, url in downloads.items():
        path = plugins_dir / filename

        if path.exists():
            try:
                with zipfile.ZipFile(path) as zf:
                    pass
            except Exception:
                log_print(
                    f"[!] Corrupt jar detected: {filename} (Invalid Zip Header). Purging and redownloading..."
                )
                try:
                    path.unlink()
                except:
                    pass

        if not path.exists():
            log_print(f"[*] Downloading {filename}...")
            try:
                download_file(url, path)
                log_print(f"[+] {filename} downloaded successfully.")
            except Exception as e:
                log_print(f"[-] Failed to download {filename}: {e}")


def setup_and_run():
    log_print("--- INITIALIZING STEALTH MINECRAFT DAEMON ---")
    mc_dir = MC_DIR
    jre_dir = mc_dir / "jre"
    metrics_dir = Path("/home/user/.torch_metrics")

    mc_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir.mkdir(parents=True, exist_ok=True)

    java_bin = jre_dir / "bin" / "java"
    if not java_bin.exists():
        log_print("[*] Portable JRE not found. Downloading Eclipse Temurin JRE 25...")
        jre_url = "https://api.adoptium.net/v3/binary/latest/25/ga/linux/x64/jre/hotspot/normal/eclipse?project=jdk"
        tar_path = mc_dir / "jre.tar.gz"

        try:
            download_file(jre_url, tar_path)
            log_print("[*] Extracting JRE...")
            temp_extract = mc_dir / "jre_temp"
            temp_extract.mkdir(parents=True, exist_ok=True)

            with tarfile.open(tar_path, "r:gz") as tar:
                tar.extractall(path=temp_extract)

            for p_file in temp_extract.rglob("java"):
                if p_file.is_file() and p_file.parent.name == "bin":
                    java_home = p_file.parent.parent
                    if jre_dir.exists():
                        shutil.rmtree(jre_dir)
                    shutil.move(str(java_home), str(jre_dir))
                    break

            shutil.rmtree(temp_extract, ignore_errors=True)
            if tar_path.exists():
                tar_path.unlink()
            log_print("[*] Portable JRE setup completed successfully.")
        except Exception as e:
            log_print(f"[-] Failed to setup JRE: {e}")
            return

    server_jar = mc_dir / "server.jar"
    if not server_jar.exists():
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
        java_bin.chmod(0o755)
    except Exception as e:
        log_print(f"[-] Failed to chmod java binary: {e}")

    try:
        ensure_paper_runtime(java_bin, mc_dir, server_jar)
    except Exception as e:
        log_print(f"[-] Failed to bootstrap Paper runtime: {e}")
        return

    log_print("[*] Launching Minecraft server loop...")
    log_file = metrics_dir / "mc_daemon.log"

    while True:
        ensure_datapacks(mc_dir)

        if not paper_patched_jar(mc_dir).is_file():
            try:
                ensure_paper_runtime(java_bin, mc_dir, server_jar)
            except Exception as e:
                log_print(f"[-] Paper runtime missing and bootstrap failed: {e}")
                time.sleep(10)
                continue

        eula_path = mc_dir / "eula.txt"
        eula_path.write_text("eula=true\n")

        ops_path = mc_dir / "ops.json"
        with ops_path.open("w") as f:
            json.dump(OPS_JSON, f, indent=2)
            f.write("\n")

        props_path = mc_dir / "server.properties"
        if not props_path.exists():
            props_path.write_text("server-port=25566\nonline-mode=false\nmotd=PCEP\n")
        else:
            try:
                props_data = props_path.read_text()
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
                    props_path.write_text(props_data)
            except Exception as e:
                log_print(f"[-] Failed to update server.properties: {e}")

        log_print("[*] Starting Minecraft server process...")
        with log_file.open("a") as log:
            process = subprocess.Popen(
                [str(java_bin), "-Xms4G", "-Xmx4G", "-jar", str(server_jar), "nogui"],
                cwd=str(mc_dir),
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
