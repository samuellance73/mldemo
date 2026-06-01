import argparse
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

_REPO_ROOT = Path(__file__).resolve().parent.parent


def main():
    # Load env secrets
    load_dotenv(_REPO_ROOT / ".env")

    parser = argparse.ArgumentParser(
        description="Build the Sanctuary Docker image and upload it to Docker Hub."
    )
    parser.add_argument(
        "--username",
        help="Docker Hub username (default: DOCKER_USERNAME env var)",
    )
    parser.add_argument(
        "--password",
        help="Docker Hub password/token (default: DOCKER_PASSWORD env var)",
    )
    parser.add_argument(
        "--repo",
        help="Docker Hub repository name (default: DOCKER_REPO env var or 'sanctuary')",
    )
    parser.add_argument(
        "--tag",
        default="latest",
        help="Docker Hub image tag (default: latest)",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip compilation step (assumes dist/ is already built)",
    )
    args = parser.parse_args()

    # Resolve variables from CLI flags or env config
    username = args.username or os.getenv("DOCKER_USERNAME") or os.getenv("DOCKER_USER")
    password = args.password or os.getenv("DOCKER_PASSWORD") or os.getenv("DOCKER_PASS")
    repo = args.repo or os.getenv("DOCKER_REPO") or "sanctuary"
    tag = args.tag or os.getenv("DOCKER_TAG") or "latest"

    if not username:
        logger.error(
            "Docker Hub username is required. "
            "Set DOCKER_USERNAME in .env or pass --username."
        )
        sys.exit(1)

    full_image_name = f"{username}/{repo}:{tag}"

    # 1. Compile the distribution package if not explicitly skipped
    if not args.skip_build:
        logger.info("Executing local compilation pipeline...")
        build_result = subprocess.run(["make", "build"], cwd=_REPO_ROOT)
        if build_result.returncode != 0:
            logger.error("Local compilation (make build) failed.")
            sys.exit(1)

    dist_dir = _REPO_ROOT / "main" / "dist"
    if not dist_dir.exists():
        logger.error(
            f"Distribution directory {dist_dir} does not exist. Run 'make build' first."
        )
        sys.exit(1)

    # 2. Inject missing build-time files (e.g. whoami.txt)
    whoami_file = dist_dir / "whoami.txt"
    if not whoami_file.exists():
        logger.info("Injecting dummy whoami.txt for Docker Hub build...")
        whoami_file.write_text("dockerhub\n")

    # 3. Build the Docker image
    logger.info(f"Building Docker image: {full_image_name}...")
    build_cmd = ["docker", "build", "-t", full_image_name, "."]
    build_process = subprocess.run(build_cmd, cwd=dist_dir)
    if build_process.returncode != 0:
        logger.error("Docker build failed.")
        sys.exit(1)
    logger.success(f"Successfully built Docker image: {full_image_name}")

    # 4. Optional authentication with Docker Hub
    if username and password:
        logger.info(f"Authenticating with Docker Hub as user: '{username}'...")
        login_process = subprocess.run(
            ["docker", "login", "-u", username, "--password-stdin"],
            input=password,
            text=True,
            capture_output=True,
        )
        if login_process.returncode != 0:
            logger.error(f"Docker Hub authentication failed:\n{login_process.stderr}")
            sys.exit(1)
        logger.success("Authenticated successfully with Docker Hub.")
    else:
        logger.warning(
            "No password/token provided. Assuming active logged-in Docker Hub session."
        )

    # 5. Push the Docker image
    logger.info(f"Pushing image {full_image_name} to Docker Hub...")
    push_process = subprocess.run(["docker", "push", full_image_name])
    if push_process.returncode != 0:
        logger.error(
            "Docker push failed. Check your permissions or repository configuration."
        )
        sys.exit(1)

    logger.success(f"Successfully deployed {full_image_name} to Docker Hub! 🚀")


if __name__ == "__main__":
    main()
