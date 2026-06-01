import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
from dotenv import load_dotenv
from huggingface_hub import HfApi
from loguru import logger

_REPO_ROOT = Path(__file__).resolve().parent.parent  # Sanctuary/

from sanctuary.client.crypto import XOR_KEY
from sanctuary.core.service_registry import ALLOWED_SERVICES


def resolve_node_services(node_info):
    """Return enabled service names for a node (empty = minimal core)."""
    services = node_info.get("services")
    if services is None:
        return []
    if not isinstance(services, list):
        raise ValueError("'services' must be a list of service names")
    return [str(s).strip().lower() for s in services if str(s).strip()]


def write_enabled_services(dist_dir, node_name, enabled):
    path = Path(dist_dir) / "config" / "enabled_services.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump({"services": enabled, "node": node_name}, f)


def harden_secret(val, key=XOR_KEY):
    """XOR encrypts secret bytes and returns a clean hex string for Hugging Face Hub."""
    if not val:
        return ""
    return bytes([b ^ key for b in val.encode("utf-8")]).hex()


def resolve_mapped_secret(target_key, node_name):
    """Resolves mapped secrets standardizing to node-specific or global keys."""
    prefix_map = {"A": "TAILSCALE", "P": "PLAYIT", "PASS": "PASS"}
    prefix = prefix_map.get(target_key)
    if not prefix:
        return None, None

    # Suffix from node name: e.g. "server-01" -> "01"
    suffix = "".join(c for c in reversed(node_name) if c.isdigit())[::-1]

    # 1. Try node-specific: e.g. PLAYIT_01, PASS_01
    if suffix:
        node_key = f"{prefix}_{suffix}"
        val = os.getenv(node_key)
        if val is not None:
            return val, node_key

    # 2. Try global/fallback prefix: e.g. PLAYIT, PASS
    val = os.getenv(prefix)
    if val is not None:
        return val, prefix

    # 3. Try legacy target_key: e.g. PASS, A
    val = os.getenv(target_key)
    if val is not None:
        return val, target_key

    return None, None


def update_state(
    state_path,
    node_name,
    repo_id,
    repo_type,
    status,
    commit_url=None,
    error=None,
    services=None,
    valid_nodes=None,
):
    """Updates state.json with the outcome of a deployment step."""
    direct_url = None
    if repo_type == "space":
        subdomain = repo_id.lower().replace("/", "-").replace("_", "-")
        direct_url = f"https://{subdomain}.hf.space"

    state = {}
    state_path_obj = Path(state_path)
    if state_path_obj.exists():
        try:
            with state_path_obj.open("r") as f:
                state = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read existing state.json: {e}")

    # Prune stale nodes no longer present in the configuration
    if valid_nodes is not None:
        valid_set = set(valid_nodes)
        state = {k: v for k, v in state.items() if k in valid_set}

    if node_name not in state:
        state[node_name] = {}

    now_str = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    node_state = state[node_name]
    update_payload = {
        "hf_repo": repo_id,
        "repo_type": repo_type,
        "url": direct_url,
        "last_deployed": now_str,
        "status": status,
    }
    if services is not None:
        update_payload["services"] = services
    node_state.update(update_payload)

    if commit_url:
        node_state["commit_url"] = commit_url
        node_state.pop("error", None)
    elif error:
        node_state["error"] = error
        node_state.pop("commit_url", None)

    try:
        state_path_obj.resolve().parent.mkdir(parents=True, exist_ok=True)
        with state_path_obj.open("w") as f:
            json.dump(state, f, indent=2)
        logger.debug(f"Saved state for '{node_name}' to '{state_path}'")
    except Exception as e:
        logger.error(f"Failed to write to state.json: {e}")


def main():
    load_dotenv(_REPO_ROOT / ".env")
    parser = argparse.ArgumentParser(
        description="Deploy built code to Hugging Face Hub nodes."
    )
    parser.add_argument(
        "--nodes",
        default="../manifests/nodes.yaml",
        help="Path to nodes.yaml manifest (default: ../manifests/nodes.yaml)",
    )
    parser.add_argument(
        "--dist",
        default="dist",
        help="Path to the distribution directory to upload (default: dist)",
    )
    parser.add_argument(
        "--token",
        help="Hugging Face API token (default: uses HF_TOKEN env var or cached login)",
    )
    parser.add_argument(
        "--commit-message",
        default="Automated deployment update from ML build",
        help="Commit message for upload",
    )
    parser.add_argument(
        "--playit-secret", help="Playit.gg secret token to push as space secret 'P'"
    )
    parser.add_argument(
        "--tailscale-key", help="Tailscale auth key to push as space secret 'A'"
    )
    parser.add_argument(
        "--ssh-password", help="SSH user password to push as space secret 'PASS'"
    )
    parser.add_argument(
        "--node",
        help="Specific node(s) to deploy to (comma-separated, or 'all' for all nodes)",
    )
    args = parser.parse_args()

    # Apply command line secret overrides
    if args.playit_secret:
        os.environ["PLAYIT"] = args.playit_secret
    if args.tailscale_key:
        os.environ["TAILSCALE"] = args.tailscale_key
    if args.ssh_password:
        os.environ["PASS"] = args.ssh_password

    # Ensure working directory is main/ (where dist/ and config/ live)
    repo_root = Path(__file__).resolve().parent.parent / "main"
    os.chdir(repo_root)

    nodes_path = Path(args.nodes)
    if not nodes_path.exists():
        logger.error(f"Nodes manifest '{args.nodes}' not found.")
        sys.exit(1)

    dist_path = Path(args.dist)
    if not dist_path.exists():
        logger.error(
            f"Distribution directory '{args.dist}' not found. Please run 'uv run python scripts/build.py' or 'make build' first."
        )
        sys.exit(1)

    logger.info(f"Loading nodes configuration from '{args.nodes}'...")
    try:
        with nodes_path.open("r") as f:
            config = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to parse '{args.nodes}': {e}")
        sys.exit(1)

    nodes = config.get("nodes", {})
    if not nodes:
        logger.warning("No nodes configured in manifest.")
        sys.exit(0)

    all_configured_nodes = list(nodes.keys())

    # Filter nodes based on --node argument
    if args.node and args.node.lower() != "all":
        requested_nodes = [n.strip() for n in args.node.split(",")]
        filtered_nodes = {}
        for node_name in requested_nodes:
            if node_name not in nodes:
                logger.error(
                    f"Node '{node_name}' not found in manifest. Available nodes: {', '.join(nodes.keys())}"
                )
                sys.exit(1)
            filtered_nodes[node_name] = nodes[node_name]
        nodes = filtered_nodes

    logger.info(f"Starting deployment of '{args.dist}' to {len(nodes)} node(s)...")
    state_path = nodes_path.resolve().parent / "state.json"

    for node_name, node_info in nodes.items():
        repo_id = node_info.get("hf-repo")
        if not repo_id:
            logger.warning(
                f"Skipping node '{node_name}': 'hf-repo' not specified in configuration."
            )
            continue

        repo_type = node_info.get("repo-type", "space")
        prefix = (
            "spaces/"
            if repo_type == "space"
            else ("datasets/" if repo_type == "dataset" else "")
        )
        target_url = f"https://huggingface.co/{prefix}{repo_id}"

        # Resolve authentication token:
        token_env_key = node_info.get("token-env")
        env_token = os.getenv(token_env_key) if token_env_key else None
        node_token = (
            node_info.get("token") or env_token or args.token or os.getenv("HF_TOKEN")
        )
        node_api = HfApi(token=node_token)

        logger.info(f"Deploying node '{node_name}' -> {repo_type} '{repo_id}'...")
        if not node_token:
            logger.warning(
                f"No Hugging Face token provided for '{node_name}'. If the repository is private, this will fail with a 401 error."
            )
        else:
            try:
                identity = node_api.whoami()
                username = identity.get("name", "Unknown")
                logger.info(f"Authenticated as HF User: '{username}'")

                if username != "Unknown" and "/" in repo_id:
                    ns, r_name = repo_id.split("/", 1)
                    if ns.lower() == username.lower() and ns != username:
                        logger.info(
                            f"Correcting namespace casing from '{ns}' to '{username}'..."
                        )
                        repo_id = f"{username}/{r_name}"
            except Exception as e:
                logger.warning(
                    f"Diagnostic check: Could not verify token identity ({e})"
                )

        # Optionally auto-create the repository if configured
        if node_info.get("create-repo", False):
            logger.info(
                f"Ensuring repository '{repo_id}' exists on Hugging Face Hub..."
            )
            try:
                node_api.create_repo(
                    repo_id=repo_id,
                    repo_type=repo_type,
                    private=node_info.get("private", False),
                    space_sdk=node_info.get(
                        "space-sdk", "docker" if repo_type == "space" else None
                    ),
                    exist_ok=True,
                )
            except Exception as e:
                logger.debug(f"Note on repo creation: {e}")

        try:
            enabled_services = resolve_node_services(node_info)
        except ValueError as e:
            logger.error(f"Invalid services for '{node_name}': {e}")
            continue

        unknown = set(enabled_services) - ALLOWED_SERVICES
        if unknown:
            logger.error(
                f"Unknown services for '{node_name}': {', '.join(sorted(unknown))}. "
                f"Allowed: {', '.join(sorted(ALLOWED_SERVICES))}"
            )
            continue

        enabled_set = set(enabled_services)
        logger.info(
            f"Node '{node_name}' services: "
            + (", ".join(sorted(enabled_set)) if enabled_set else "(minimal core)")
        )

        # Push Space Secrets if configured
        if repo_type == "space" and node_info.get("push-secrets", False):
            logger.info(f"Synchronizing space secret(s) to '{repo_id}'...")
            pushed_keys = {}
            deleted_keys = []
            secret_targets = ["PASS"]
            if "tailscale" in enabled_set:
                secret_targets.insert(0, "A")
            if "playit" in enabled_set:
                secret_targets.insert(-1, "P")
            for target_key in secret_targets:
                raw_val, source_key = resolve_mapped_secret(target_key, node_name)
                if raw_val:
                    obf_val = harden_secret(raw_val)
                    try:
                        node_api.add_space_secret(
                            repo_id=repo_id, key=target_key, value=obf_val
                        )
                        pushed_keys[source_key] = target_key
                    except Exception as e:
                        logger.error(
                            f"Failed to push secret '{source_key}' as '{target_key}': {e}"
                        )
                else:
                    # Secret is not defined/empty; delete it from HF Space to ensure it doesn't linger
                    try:
                        node_api.delete_space_secret(repo_id=repo_id, key=target_key)
                        deleted_keys.append(target_key)
                    except Exception as e:
                        # Silently ignore if secret didn't exist on the space
                        logger.debug(
                            f"Secret '{target_key}' did not exist or could not be deleted: {e}"
                        )
            if pushed_keys:
                summary = [f"{k}->{v}" for k, v in pushed_keys.items()]
                logger.info(f"Successfully pushed space secrets: {', '.join(summary)}")
            if deleted_keys:
                logger.info(
                    f"Successfully deleted/cleared stale space secrets: {', '.join(deleted_keys)}"
                )

            # Clear secrets for services not enabled on this node
            for target_key in ["A", "P"]:
                if target_key not in secret_targets:
                    try:
                        node_api.delete_space_secret(repo_id=repo_id, key=target_key)
                        deleted_keys.append(target_key)
                    except Exception as e:
                        logger.debug(
                            f"Secret '{target_key}' did not exist or could not be deleted: {e}"
                        )

            # LLM_KEYS: push when llm_proxy is enabled, delete otherwise
            if "llm_proxy" in enabled_set:
                llm_keys_raw = ""
                yaml_path = _REPO_ROOT / "llm_keys.yaml"
                if yaml_path.exists():
                    try:
                        with yaml_path.open("r") as f:
                            data = yaml.safe_load(f) or {}
                        providers = data.get("providers", {})
                        entries = []
                        for provider, keys in providers.items():
                            provider_clean = provider.lower().strip()
                            if isinstance(keys, list):
                                for k in keys:
                                    if isinstance(k, str) and k:
                                        entries.append(
                                            f"{provider_clean}:*:{k.strip()}"
                                        )
                                    elif isinstance(k, dict):
                                        model = k.get("model")
                                        specific_keys = k.get("keys", [])
                                        if model and isinstance(specific_keys, list):
                                            for sk in specific_keys:
                                                if sk and isinstance(sk, str):
                                                    entries.append(
                                                        f"{provider_clean}:{model.strip()}:{sk.strip()}"
                                                    )
                                        elif model and isinstance(k.get("keys"), str):
                                            sk = k.get("keys")
                                            if sk:
                                                entries.append(
                                                    f"{provider_clean}:{model.strip()}:{sk.strip()}"
                                                )
                            elif isinstance(keys, str):
                                entries.append(f"{provider_clean}:*:{keys.strip()}")
                        llm_keys_raw = ",".join(entries)
                    except Exception as e:
                        logger.error(
                            f"Error compiling llm_keys.yaml for deployment: {e}"
                        )

                if llm_keys_raw:
                    try:
                        node_api.add_space_secret(
                            repo_id=repo_id,
                            key="LLM_KEYS",
                            value=harden_secret(llm_keys_raw),
                        )
                        logger.info(
                            f"Successfully pushed space secret: LLM_KEYS ({len(llm_keys_raw.split(','))} key(s))"
                        )
                    except Exception as e:
                        logger.error(f"Failed to push LLM_KEYS secret: {e}")
                else:
                    logger.warning(
                        f"Node '{node_name}' has llm_proxy enabled but no keys found in llm_keys.yaml"
                    )

                # LITELLM_MASTER_KEY: push when llm_proxy enabled, delete otherwise
                master_key_val = os.getenv("LITELLM_MASTER_KEY", "").strip()
                if master_key_val:
                    try:
                        node_api.add_space_secret(
                            repo_id=repo_id,
                            key="LITELLM_MASTER_KEY",
                            value=master_key_val,  # plain — llm_proxy reads it directly, not XOR-decoded
                        )
                        logger.info(
                            "Successfully pushed space secret: LITELLM_MASTER_KEY"
                        )
                    except Exception as e:
                        logger.error(f"Failed to push LITELLM_MASTER_KEY secret: {e}")
                else:
                    logger.debug(
                        f"LITELLM_MASTER_KEY not set — /litellm-ui/ dashboard will be disabled on '{node_name}'"
                    )
            else:
                try:
                    node_api.delete_space_secret(repo_id=repo_id, key="LLM_KEYS")
                except Exception:
                    pass
                try:
                    node_api.delete_space_secret(
                        repo_id=repo_id, key="LITELLM_MASTER_KEY"
                    )
                except Exception:
                    pass

        direct_url = None
        if repo_type == "space":
            subdomain = repo_id.lower().replace("/", "-").replace("_", "-")
            direct_url = f"https://{subdomain}.hf.space"

        custom_dir = node_info.get("custom-dir")
        if custom_dir:
            upload_path = (repo_root.parent / custom_dir).resolve()
        else:
            upload_path = dist_path.resolve()

        # Per-node runtime config injected immediately before upload
        whoami_path = upload_path / "whoami.txt"
        try:
            whoami_path.write_text(node_name + "\n")
        except Exception as e:
            logger.warning(f"Failed to write whoami.txt: {e}")

        try:
            write_enabled_services(upload_path, node_name, enabled_services)
        except Exception as e:
            logger.warning(f"Failed to write enabled_services.json: {e}")

        try:
            commit_info = node_api.upload_folder(
                folder_path=str(upload_path),
                repo_id=repo_id,
                repo_type=repo_type,
                commit_message=args.commit_message,
                delete_patterns="*",
            )
            logger.success(
                f"Successfully deployed '{node_name}'! Target Repo: {target_url}"
            )
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
                commit_url=commit_url,
                services=enabled_services,
                valid_nodes=all_configured_nodes,
            )
        except Exception as e:
            logger.error(f"Failed to deploy node '{node_name}': {e}")
            update_state(
                state_path=state_path,
                node_name=node_name,
                repo_id=repo_id,
                repo_type=repo_type,
                status="failed",
                error=str(e),
                services=enabled_services,
                valid_nodes=all_configured_nodes,
            )

    logger.success("Deployment run completed.")


if __name__ == "__main__":
    main()
