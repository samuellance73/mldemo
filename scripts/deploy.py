import os
import sys
import yaml
import argparse
from huggingface_hub import HfApi

def load_env(path=".env"):
    """Lightweight .env parser so no external dependencies are needed."""
    if os.path.exists(path):
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ[key.strip()] = val.strip().strip("'\"")

def main():
    load_env(".env")
    parser = argparse.ArgumentParser(description="Deploy built code to Hugging Face Hub nodes.")
    parser.add_argument("--nodes", default="manifests/nodes.yaml", help="Path to nodes.yaml manifest (default: manifests/nodes.yaml)")
    parser.add_argument("--dist", default="dist", help="Path to the distribution directory to upload (default: dist)")
    parser.add_argument("--token", help="Hugging Face API token (default: uses HF_TOKEN env var or cached login)")
    parser.add_argument("--commit-message", default="Automated deployment update from ML build", help="Commit message for upload")
    args = parser.parse_args()

    # Ensure working directory is repository root
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(repo_root)

    if not os.path.exists(args.nodes):
        print(f"[-] Error: Nodes manifest '{args.nodes}' not found.")
        sys.exit(1)

    if not os.path.exists(args.dist):
        print(f"[-] Error: Distribution directory '{args.dist}' not found. Please run 'uv run python scripts/build.py' or 'make build' first.")
        sys.exit(1)

    print(f"[*] Loading nodes configuration from '{args.nodes}'...")
    try:
        with open(args.nodes, "r") as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"[-] Failed to parse '{args.nodes}': {e}")
        sys.exit(1)

    nodes = config.get("nodes", {})
    if not nodes:
        print("[-] No nodes configured in manifest.")
        sys.exit(0)

    print(f"[*] Initializing Hugging Face API...")

    print(f"[*] Starting deployment of '{args.dist}' to {len(nodes)} node(s)...")

    for node_name, node_info in nodes.items():
        repo_id = node_info.get("hf-repo")
        if not repo_id:
            print(f"[-] Skipping node '{node_name}': 'hf-repo' not specified in configuration.")
            continue

        repo_type = node_info.get("repo-type", "space")
        prefix = "spaces/" if repo_type == "space" else ("datasets/" if repo_type == "dataset" else "")
        target_url = f"https://huggingface.co/{prefix}{repo_id}"

        # Resolve authentication token:
        # 1. Direct 'token' in yaml (if used)
        # 2. 'token-env' key looking up environment variable from .env
        # 3. CLI --token argument
        # 4. Standard $HF_TOKEN fallback
        token_env_key = node_info.get("token-env")
        env_token = os.getenv(token_env_key) if token_env_key else None
        node_token = node_info.get("token") or env_token or args.token or os.getenv("HF_TOKEN")
        node_api = HfApi(token=node_token)

        print(f"\n[*] Deploying node '{node_name}' -> {repo_type} '{repo_id}'...")
        if not node_token:
            print(f"[-] Warning: No Hugging Face token provided for '{node_name}'. If the repository is private, this will fail with a 401 error.")
        else:
            try:
                identity = node_api.whoami()
                username = identity.get("name", "Unknown")
                print(f"[*] Authenticated as HF User: '{username}'")
                auth_data = identity.get("auth", {}).get("accessToken", {})
                perms = auth_data.get("permissions", [])
                if perms:
                    print(f"[*] Token permissions: {perms}")
                
                # Correct case-sensitivity mismatch: Hugging Face backend strictly checks exact case for create_repo
                if username != "Unknown" and "/" in repo_id:
                    ns, r_name = repo_id.split("/", 1)
                    if ns.lower() == username.lower() and ns != username:
                        print(f"[*] Correcting namespace casing from '{ns}' to '{username}'...")
                        repo_id = f"{username}/{r_name}"

            except Exception as e:
                print(f"[-] Diagnostic check: Could not verify token identity ({e})")

        # Optionally auto-create the repository if configured
        if node_info.get("create-repo", False):
            print(f"[*] Ensuring repository '{repo_id}' exists on Hugging Face Hub...")
            try:
                node_api.create_repo(
                    repo_id=repo_id,
                    repo_type=repo_type,
                    private=node_info.get("private", True),
                    space_sdk=node_info.get("space-sdk", "docker" if repo_type == "space" else None),
                    exist_ok=True
                )
            except Exception as e:
                print(f"[-] Note on repo creation: {e}")

        try:
            commit_info = node_api.upload_folder(
                folder_path=args.dist,
                repo_id=repo_id,
                repo_type=repo_type,
                commit_message=args.commit_message,
            )
            print(f"[+] Successfully deployed '{node_name}'!")
            print(f"[+] Target Repo: {target_url}")
            if hasattr(commit_info, "commit_url") and commit_info.commit_url:
                print(f"[+] Commit URL: {commit_info.commit_url}")
        except Exception as e:
            print(f"[-] Failed to deploy node '{node_name}': {e}", file=sys.stderr)

    print("\n[+] Deployment run completed.")

if __name__ == "__main__":
    main()
