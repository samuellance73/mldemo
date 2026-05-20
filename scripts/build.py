import re
import base64
import os
import sys
import shutil
import argparse
import yaml
import json
from datetime import datetime, timezone
from loguru import logger


def encode_cmd(decoded_str):
    return base64.b64encode(decoded_str.encode()).decode()[::-1]


def build_orchestrator(logging_mode=1):
    with open("src/core/orchestrator.py", "r") as f:
        content = f.read()

    def replacer(match):
        raw_cmd = match.group(1)
        encoded = encode_cmd(raw_cmd)
        return f'"{encoded}"'

    # Replace OBFUSCATE("...") with "encoded_reversed_b64"
    content = re.sub(r'OBFUSCATE\(\s*"([^"]+)"\s*\)', replacer, content)

    content = content.replace(
        "COVERT_LOGGING_MODE = 1", f"COVERT_LOGGING_MODE = {logging_mode}"
    )

    # Strip comments
    content = "\n".join(
        line for line in content.split("\n") if not line.lstrip().startswith("#")
    )

    os.makedirs("dist/core", exist_ok=True)
    with open("dist/core/orchestrator.py", "w") as f:
        f.write(content)
    mode_str = (
        "File Only"
        if logging_mode == 1
        else ("Console + File" if logging_mode == 2 else "DISABLED")
    )
    logger.success(
        f"Built orchestrator.py from src/core/orchestrator.py (Logging: {mode_str})"
    )


def build_dockerfile(logging_mode=1):
    with open("Dockerfile", "r") as f:
        content = f.read()

    def url_replacer(match):
        raw_url = match.group(1)
        encoded = base64.b64encode(raw_url.encode()).decode()
        return f"$(echo '{encoded}' | base64 -d)"

    # Replace URL_OBFUSCATE("...") with $(echo '...' | base64 -d)
    content = re.sub(r'URL_OBFUSCATE\("([^"]+)"\)', url_replacer, content)

    if logging_mode == 0:
        content = content.replace(
            " 2>&1 | tee /home/user/.torch_metrics/startup.log", ""
        )

    # For the dist build, files are at the root of dist/, not in src/
    content = content.replace("COPY --chown=user:user src/", "COPY --chown=user:user ")
    
    # Inject copying of the whoami files right before USER user
    injection = "COPY --chown=user:user whoami.txt /home/user/whoami.txt\n\nUSER user"
    content = content.replace("USER user", injection)

    # Strip comments
    content = "\n".join(
        line for line in content.split("\n") if not line.lstrip().startswith("#")
    )

    os.makedirs("dist", exist_ok=True)
    with open("dist/Dockerfile", "w") as f:
        f.write(content)
    logger.success("Built Dockerfile from root Dockerfile")


def update_build_state(nodes_path, state_path):
    if not os.path.exists(nodes_path):
        logger.warning(
            f"Nodes manifest '{nodes_path}' not found. Skipping build state update."
        )
        return

    try:
        with open(nodes_path, "r") as f:
            config = yaml.safe_load(f)
        nodes = config.get("nodes", {})

        state = {}
        if os.path.exists(state_path):
            try:
                with open(state_path, "r") as f:
                    state = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to read existing state.json: {e}")

        now_str = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        for node_name, node_info in nodes.items():
            repo_id = node_info.get("hf-repo")
            if not repo_id:
                continue
            repo_type = node_info.get("repo-type", "space")

            # Calculate URL if it's a space
            direct_url = None
            if repo_type == "space":
                subdomain = repo_id.lower().replace("/", "-").replace("_", "-")
                direct_url = f"https://{subdomain}.hf.space"

            if node_name not in state:
                state[node_name] = {}

            state[node_name].update(
                {
                    "hf_repo": repo_id,
                    "repo_type": repo_type,
                    "url": direct_url,
                    "last_built": now_str,
                }
            )

        os.makedirs(os.path.dirname(os.path.abspath(state_path)), exist_ok=True)
        with open(state_path, "w") as f:
            json.dump(state, f, indent=2)
        logger.success(f"Updated build state in '{state_path}'")
    except Exception as e:
        logger.error(f"Failed to update '{state_path}' on build: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build pipeline for ML project")
    parser.add_argument(
        "--logs",
        type=int,
        choices=[0, 1, 2],
        default=1,
        help="0=None, 1=File (default), 2=Console+File",
    )
    parser.add_argument(
        "--nodes",
        default="manifests/nodes.yaml",
        help="Path to nodes.yaml manifest (default: manifests/nodes.yaml)",
    )
    args = parser.parse_args()

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(repo_root)
    if not os.path.exists("src/core/orchestrator.py") or not os.path.exists(
        "Dockerfile"
    ):
        logger.error(
            "Source files missing! Please ensure src/core/orchestrator.py and Dockerfile exist."
        )
        sys.exit(1)

    build_orchestrator(logging_mode=args.logs)
    build_dockerfile(logging_mode=args.logs)

    # Copy other necessary files and strip their comments if python
    if os.path.exists("src/app.py"):
        with open("src/app.py", "r") as f:
            app_content = f.read()
        app_content = "\n".join(
            line
            for line in app_content.split("\n")
            if not line.lstrip().startswith("#")
        )
        with open("dist/app.py", "w") as f:
            f.write(app_content)

    if os.path.exists("src/services"):
        os.makedirs("dist/services", exist_ok=True)
        for entry in os.listdir("src/services"):
            src_entry = os.path.join("src/services", entry)
            dist_entry = os.path.join("dist/services", entry)
            if os.path.isfile(src_entry) and entry.endswith(".py"):
                with open(src_entry, "r") as f:
                    content = f.read()

                def replacer(match):
                    raw_cmd = match.group(1)
                    encoded = encode_cmd(raw_cmd)
                    return f'"{encoded}"'

                content = re.sub(r'OBFUSCATE\(\s*"([^"]+)"\s*\)', replacer, content)
                content = "\n".join(
                    line
                    for line in content.split("\n")
                    if not line.lstrip().startswith("#")
                )
                with open(dist_entry, "w") as f:
                    f.write(content)
        logger.success("Processed and copied services to dist/services")

    if os.path.exists("src/README.md"):
        shutil.copy("src/README.md", "dist/README.md")

    if os.path.exists("config"):
        shutil.copytree("config", "dist/config", dirs_exist_ok=True)
        conf_path = "dist/config/supervisord.conf"
        if os.path.exists(conf_path):
            with open(conf_path, "r") as f:
                conf_data = f.read()
            if args.logs == 2:
                conf_data = conf_data.replace(
                    "stderr_logfile=/home/user/.torch_metrics/startup.log",
                    "stderr_logfile=/dev/stderr\nstderr_logfile_maxbytes=0",
                )
                conf_data = conf_data.replace(
                    "stdout_logfile=/home/user/.torch_metrics/startup.log",
                    "stdout_logfile=/dev/stdout\nstdout_logfile_maxbytes=0",
                )
            elif args.logs == 0:
                conf_data = conf_data.replace(
                    "stderr_logfile=/home/user/.torch_metrics/startup.log",
                    "stderr_logfile=/dev/null",
                )
                conf_data = conf_data.replace(
                    "stdout_logfile=/home/user/.torch_metrics/startup.log",
                    "stdout_logfile=/dev/null",
                )
            with open(conf_path, "w") as f:
                f.write(conf_data)
            logger.success(f"Configured supervisord.conf for logging mode: {args.logs}")

    state_path = os.path.join(
        os.path.dirname(os.path.abspath(args.nodes)), "state.json"
    )
    update_build_state(args.nodes, state_path)

    logger.success(
        "Build complete. The files in dist/ are ready to be pushed to Hugging Face."
    )
