import os
import sys
import yaml
import argparse
import json
from datetime import datetime, timezone
from huggingface_hub import HfApi
from loguru import logger
from dotenv import load_dotenv

def obfuscate_secret(val, key=0x5A):
    """XOR encrypts secret bytes and returns a clean hex string for Hugging Face Hub."""
    if not val:
        return ""
    return bytes([b ^ key for b in val.encode('utf-8')]).hex()

def resolve_mapped_secret(target_key, node_name):
    """Resolves mapped secrets standardizing to node-specific or global keys."""
    prefix_map = {
        "A": "TAILSCALE",
        "P": "PLAYIT",
        "C": "CHISEL",
        "PASS": "SSH"
    }
    prefix = prefix_map.get(target_key)
    if not prefix:
        return None, None
        
    # Suffix from node name: e.g. "server-01" -> "01"
    suffix = "".join(c for c in reversed(node_name) if c.isdigit())[::-1]
    
    # 1. Try node-specific: e.g. PLAYIT_01
    if suffix:
        node_key = f"{prefix}_{suffix}"
        val = os.getenv(node_key)
        if val is not None:
            return val, node_key
            
    # 2. Try global/fallback prefix: e.g. PLAYIT
    val = os.getenv(prefix)
    if val is not None:
        return val, prefix
        
    # 3. Try legacy target_key: e.g. PASS, A
    val = os.getenv(target_key)
    if val is not None:
        return val, target_key
        
    return None, None

def update_state(state_path, node_name, repo_id, repo_type, status, commit_url=None, error=None):
    """Updates state.json with the outcome of a deployment step."""
    direct_url = None
    if repo_type == "space":
        subdomain = repo_id.lower().replace('/', '-').replace('_', '-')
        direct_url = f"https://{subdomain}.hf.space"
    
    state = {}
    if os.path.exists(state_path):
        try:
            with open(state_path, "r") as f:
                state = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read existing state.json: {e}")
            
    if node_name not in state:
        state[node_name] = {}
        
    now_str = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    node_state = state[node_name]
    node_state.update({
        "hf_repo": repo_id,
        "repo_type": repo_type,
        "url": direct_url,
        "last_deployed": now_str,
        "status": status
    })
    
    if commit_url:
        node_state["commit_url"] = commit_url
        node_state.pop("error", None)
    elif error:
        node_state["error"] = error
        node_state.pop("commit_url", None)
        
    try:
        os.makedirs(os.path.dirname(os.path.abspath(state_path)), exist_ok=True)
        with open(state_path, "w") as f:
            json.dump(state, f, indent=2)
        logger.debug(f"Saved state for '{node_name}' to '{state_path}'")
    except Exception as e:
        logger.error(f"Failed to write to state.json: {e}")

def main():
    load_dotenv(".env")
    parser = argparse.ArgumentParser(description="Deploy built code to Hugging Face Hub nodes.")
    parser.add_argument("--nodes", default="manifests/nodes.yaml", help="Path to nodes.yaml manifest (default: manifests/nodes.yaml)")
    parser.add_argument("--dist", default="dist", help="Path to the distribution directory to upload (default: dist)")
    parser.add_argument("--token", help="Hugging Face API token (default: uses HF_TOKEN env var or cached login)")
    parser.add_argument("--commit-message", default="Automated deployment update from ML build", help="Commit message for upload")
    parser.add_argument("--playit-secret", help="Playit.gg secret token to push as space secret 'P'")
    parser.add_argument("--tailscale-key", help="Tailscale auth key to push as space secret 'A'")
    parser.add_argument("--chisel-auth", help="Chisel authentication credentials (username:password) to push as space secret 'C'")
    parser.add_argument("--ssh-password", help="SSH user password to push as space secret 'PASS'")
    args = parser.parse_args()

    # Apply command line secret overrides
    if args.playit_secret:
        os.environ["PLAYIT"] = args.playit_secret
    if args.tailscale_key:
        os.environ["TAILSCALE"] = args.tailscale_key
    if args.chisel_auth:
        os.environ["CHISEL"] = args.chisel_auth
    if args.ssh_password:
        os.environ["SSH"] = args.ssh_password

    # Ensure working directory is repository root
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(repo_root)

    if not os.path.exists(args.nodes):
        logger.error(f"Nodes manifest '{args.nodes}' not found.")
        sys.exit(1)

    if not os.path.exists(args.dist):
        logger.error(f"Distribution directory '{args.dist}' not found. Please run 'uv run python scripts/build.py' or 'make build' first.")
        sys.exit(1)

    logger.info(f"Loading nodes configuration from '{args.nodes}'...")
    try:
        with open(args.nodes, "r") as f:
            config = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to parse '{args.nodes}': {e}")
        sys.exit(1)

    nodes = config.get("nodes", {})
    if not nodes:
        logger.warning("No nodes configured in manifest.")
        sys.exit(0)

    logger.info(f"Starting deployment of '{args.dist}' to {len(nodes)} node(s)...")
    state_path = os.path.join(os.path.dirname(os.path.abspath(args.nodes)), "state.json")

    for node_name, node_info in nodes.items():
        repo_id = node_info.get("hf-repo")
        if not repo_id:
            logger.warning(f"Skipping node '{node_name}': 'hf-repo' not specified in configuration.")
            continue

        repo_type = node_info.get("repo-type", "space")
        prefix = "spaces/" if repo_type == "space" else ("datasets/" if repo_type == "dataset" else "")
        target_url = f"https://huggingface.co/{prefix}{repo_id}"

        # Resolve authentication token:
        token_env_key = node_info.get("token-env")
        env_token = os.getenv(token_env_key) if token_env_key else None
        node_token = node_info.get("token") or env_token or args.token or os.getenv("HF_TOKEN")
        node_api = HfApi(token=node_token)

        logger.info(f"Deploying node '{node_name}' -> {repo_type} '{repo_id}'...")
        if not node_token:
            logger.warning(f"No Hugging Face token provided for '{node_name}'. If the repository is private, this will fail with a 401 error.")
        else:
            try:
                identity = node_api.whoami()
                username = identity.get("name", "Unknown")
                logger.info(f"Authenticated as HF User: '{username}'")
                
                if username != "Unknown" and "/" in repo_id:
                    ns, r_name = repo_id.split("/", 1)
                    if ns.lower() == username.lower() and ns != username:
                        logger.info(f"Correcting namespace casing from '{ns}' to '{username}'...")
                        repo_id = f"{username}/{r_name}"
            except Exception as e:
                logger.warning(f"Diagnostic check: Could not verify token identity ({e})")

        # Optionally auto-create the repository if configured
        if node_info.get("create-repo", False):
            logger.info(f"Ensuring repository '{repo_id}' exists on Hugging Face Hub...")
            try:
                node_api.create_repo(
                    repo_id=repo_id,
                    repo_type=repo_type,
                    private=node_info.get("private", True),
                    space_sdk=node_info.get("space-sdk", "docker" if repo_type == "space" else None),
                    exist_ok=True
                )
            except Exception as e:
                logger.debug(f"Note on repo creation: {e}")

        # Push Space Secrets if configured
        if repo_type == "space" and node_info.get("push-secrets", False):
            logger.info(f"Pushing XOR-obfuscated space secret(s) to '{repo_id}'...")
            pushed_keys = {}
            for target_key in ["A", "P", "C", "PASS"]:
                raw_val, source_key = resolve_mapped_secret(target_key, node_name)
                if raw_val is not None:
                    obf_val = obfuscate_secret(raw_val)
                    try:
                        node_api.add_space_secret(repo_id=repo_id, key=target_key, value=obf_val)
                        pushed_keys[source_key] = target_key
                    except Exception as e:
                        logger.error(f"Failed to push secret '{source_key}' as '{target_key}': {e}")
            if pushed_keys:
                summary = [f"{k}->{v}" for k, v in pushed_keys.items()]
                logger.info(f"Successfully pushed space secrets: {', '.join(summary)}")

        direct_url = None
        if repo_type == "space":
            subdomain = repo_id.lower().replace('/', '-').replace('_', '-')
            direct_url = f"https://{subdomain}.hf.space"

        try:
            commit_info = node_api.upload_folder(
                folder_path=args.dist,
                repo_id=repo_id,
                repo_type=repo_type,
                commit_message=args.commit_message,
            )
            logger.success(f"Successfully deployed '{node_name}'! Target Repo: {target_url}")
            if direct_url:
                logger.info(f"Direct App URL: {direct_url}")
            commit_url = getattr(commit_info, "commit_url", None)
            if commit_url:
                logger.info(f"Commit URL: {commit_url}")
                
            update_state(
                state_path=state_path,
                node_name=node_name,
                repo_id=repo_id,
                repo_type=repo_type,
                status="success",
                commit_url=commit_url
            )
        except Exception as e:
            logger.error(f"Failed to deploy node '{node_name}': {e}")
            update_state(
                state_path=state_path,
                node_name=node_name,
                repo_id=repo_id,
                repo_type=repo_type,
                status="failed",
                error=str(e)
            )

    logger.success("Deployment run completed.")

if __name__ == "__main__":
    main()
