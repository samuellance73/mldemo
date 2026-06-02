import argparse
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

_REPO_ROOT = Path(__file__).resolve().parent.parent


def main():
    # Load environment configuration
    load_dotenv(_REPO_ROOT / ".env")

    parser = argparse.ArgumentParser(
        description="Run the Sanctuary container locally with standard ports."
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Host port to bind Caddy proxy to (default: 8080)",
    )
    parser.add_argument(
        "--ssh-port",
        type=int,
        default=2222,
        help="Host port to bind SSH daemon to (default: 2222)",
    )
    parser.add_argument(
        "--image",
        help="Custom image name (defaults to local build tag or username/repo:tag)",
    )
    parser.add_argument(
        "--name",
        default="sanctuary-local",
        help="Container instance name (default: sanctuary-local)",
    )
    parser.add_argument(
        "--stop",
        action="store_true",
        help="Only stop and remove the running container",
    )
    args = parser.parse_args()

    # 1. Detect and stop existing active containers to prevent naming conflicts
    logger.info(f"Checking for existing container named '{args.name}'...")
    check_process = subprocess.run(
        ["docker", "ps", "-a", "-q", "-f", f"name={args.name}"],
        capture_output=True,
        text=True,
    )

    container_id = check_process.stdout.strip()
    if container_id:
        logger.info(
            f"Stopping container '{args.name}' ({container_id[:12]})..."
        )
        subprocess.run(["docker", "stop", args.name], capture_output=True)
        subprocess.run(["docker", "rm", args.name], capture_output=True)
        logger.success("Cleaned up old container.")
        if args.stop:
            sys.exit(0)
    elif args.stop:
        logger.info(f"No active container named '{args.name}' found.")
        sys.exit(0)

    # 2. Resolve image tag to execute
    username = os.getenv("DOCKER_USERNAME") or os.getenv("DOCKER_USER")
    repo = os.getenv("DOCKER_REPO") or "sanctuary"
    tag = os.getenv("DOCKER_TAG") or "latest"

    if args.image:
        image_name = args.image
    elif username:
        image_name = f"{username}/{repo}:{tag}"
    else:
        image_name = "sanctuary:local"

    # Verify if image exists locally or pull it
    logger.info(f"Verifying availability of image '{image_name}'...")
    inspect_process = subprocess.run(
        ["docker", "image", "inspect", image_name], capture_output=True
    )
    if inspect_process.returncode != 0:
        logger.warning(f"Image '{image_name}' not found locally. Attempting to pull...")
        pull_process = subprocess.run(["docker", "pull", image_name])
        if pull_process.returncode != 0:
            logger.error(
                f"Image '{image_name}' could not be resolved. "
                "Ensure it is built or run 'make docker-push'."
            )
            sys.exit(1)

    # 3. Pull configurations to inject from environment files
    pass_cfg = os.getenv("PASS") or "banana153"
    ts_key = os.getenv("TAILSCALE") or ""
    playit_key = os.getenv("PLAYIT") or ""
    master_key = os.getenv("LITELLM_MASTER_KEY") or ""

    # 4. Start the container with appropriate arguments
    # Port mapping: container_port → host_port (Cloud Shell Web Preview supports
    # 8080, 8081, 8082, 8083, 8084 and a handful of others like 3000, 4200, 5000)
    logger.info(f"Spawning container '{args.name}' from '{image_name}'...")
    run_cmd = [
        "docker", "run", "-d",
        "--name", args.name,
        "-p", "7860:7860",       # Caddy public gateway 1:1
        "-p", "2222:2222",       # SSH admin shell 1:1
        "-p", "9000:9000",       # Filebrowser 1:1
        "-p", "7861:7861",       # Gradio cover app 1:1
        "-p", "8080:8080",       # LiteLLM proxy 1:1
        "-p", "3000:3000",       # Open WebUI 1:1
        "-p", "8501:8501",       # VNC display 1:1
        "-e", f"PASS={pass_cfg}",
    ]
    if ts_key:
        run_cmd.extend(["-e", f"TAILSCALE={ts_key}"])
    if playit_key:
        run_cmd.extend(["-e", f"PLAYIT={playit_key}"])
    if master_key:
        run_cmd.extend(["-e", f"LITELLM_MASTER_KEY={master_key}"])

    run_cmd.append(image_name)

    run_process = subprocess.run(run_cmd, capture_output=True, text=True)
    if run_process.returncode != 0:
        logger.error(f"Failed to start container:\n{run_process.stderr}")
        sys.exit(1)

    logger.success(f"Container '{args.name}' successfully launched in background!")

    # 5. Print a connection guide
    logger.info("================================================================")
    logger.info("🖥️  CONNECTION GUIDE (localhost / Cloud Shell Web Preview):")
    logger.info("================================================================")
    logger.info(f"🔗 Caddy  : http://localhost:{args.port} (preview: {args.port})")
    logger.info("📁 Filebrowser    : http://localhost:8081            (preview: 8081)")
    logger.info("🤖 Gradio App     : http://localhost:8082            (preview: 8082)")
    logger.info("🧠 LiteLLM Proxy  : http://localhost:8083            (preview: 8083)")
    logger.info("💬 Open WebUI     : http://localhost:3000            (preview: 3000)")
    logger.info(
        f"🔑 SSH Shell      : ssh user@localhost -p {args.ssh_port} "
        f"(password: '{pass_cfg}')"
    )
    logger.info("================================================================")


if __name__ == "__main__":
    main()
