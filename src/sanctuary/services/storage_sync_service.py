import os
import subprocess
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from loguru import logger

# Try importing huggingface_hub, if not available, provide a mock
try:
    from huggingface_hub import HfApi, snapshot_download
except ImportError:
    logger.warning("huggingface_hub not installed. HFDatasetProvider will be non-functional.")
    class HfApi:
        def __init__(self, token=None):
            pass
        def upload_folder(self, folder_path, repo_id, repo_type, commit_message, delete_patterns):
            logger.error("HfApi.upload_folder called but huggingface_hub is not installed.")

    def snapshot_download(repo_id, repo_type, local_dir, token, ignore_patterns):
        logger.error("snapshot_download called but huggingface_hub is not installed.")


class BaseStorageProvider(ABC):
    """Abstract contract that any storage provider must fulfill."""

    @abstractmethod
    def pull(self, local_dir: Path) -> None:
        """Downloads remote storage assets to local_dir."""
        pass

    @abstractmethod
    def push(self, local_dir: Path, commit_message: str) -> None:
        """Uploads local_dir assets to remote storage."""
        pass


class HFDatasetProvider(BaseStorageProvider):
    """Hugging Face private dataset storage provider."""

    def __init__(self, repo_id: str, token: str, node_name: str = None):
        self.repo_id = repo_id
        self.token = token
        self.node_name = node_name
        self.api = HfApi(token=token)

    def pull(self, local_dir: Path) -> None:
        actual_local_dir = local_dir
        allow_patterns = None
        if self.node_name:
            actual_local_dir = local_dir / self.node_name
            actual_local_dir.mkdir(parents=True, exist_ok=True)
            allow_patterns = [f"{self.node_name}/*"]

        logger.info(f"Pulling from Hugging Face dataset '{self.repo_id}' (node: '{self.node_name}') to '{actual_local_dir}'")
        snapshot_download(
            repo_id=self.repo_id,
            repo_type="dataset",
            local_dir=str(local_dir),
            token=self.token,
            ignore_patterns=[".git*", "README.md"],
            allow_patterns=allow_patterns
        )
        logger.info(f"Successfully pulled Hugging Face dataset '{self.repo_id}'.")

    def push(self, local_dir: Path, commit_message: str) -> None:
        actual_local_dir = local_dir
        path_in_repo = None
        if self.node_name:
            actual_local_dir = local_dir / self.node_name
            actual_local_dir.mkdir(parents=True, exist_ok=True)
            path_in_repo = self.node_name

        logger.info(f"Pushing to Hugging Face dataset '{self.repo_id}' (node: '{self.node_name}') from '{actual_local_dir}'")
        self.api.upload_folder(
            folder_path=str(actual_local_dir),
            repo_id=self.repo_id,
            repo_type="dataset",
            commit_message=commit_message,
            delete_patterns="*",
            path_in_repo=path_in_repo
        )
        logger.info(f"Successfully pushed to Hugging Face dataset '{self.repo_id}'.")


class S3StorageProvider(BaseStorageProvider):
    """Headless S3/R2 storage provider utilizing pre-installed rclone."""

    def __init__(self, bucket_name: str, endpoint: str, access_key: str, secret_key: str, node_name: str = None):
        self.bucket_name = bucket_name
        self.endpoint = endpoint
        self.access_key = access_key
        self.secret_key = secret_key
        self.node_name = node_name

    def _get_rclone_env(self):
        env = os.environ.copy()
        env["RCLONE_CONFIG_S3SYNC_TYPE"] = "s3"
        env["RCLONE_CONFIG_S3SYNC_PROVIDER"] = "Other"
        env["RCLONE_CONFIG_S3SYNC_ACCESS_KEY_ID"] = self.access_key
        env["RCLONE_CONFIG_S3SYNC_SECRET_ACCESS_KEY"] = self.secret_key
        env["RCLONE_CONFIG_S3SYNC_ENDPOINT"] = self.endpoint
        return env

    def pull(self, local_dir: Path) -> None:
        remote_path = f"s3sync:{self.bucket_name}"
        actual_local_dir = local_dir
        if self.node_name:
            remote_path = f"{remote_path}/{self.node_name}"
            actual_local_dir = local_dir / self.node_name
            actual_local_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Pulling from S3 bucket '{self.bucket_name}' (node: '{self.node_name}') to '{actual_local_dir}'")
        subprocess.run(
            ["rclone", "sync", remote_path, str(actual_local_dir)],
            env=self._get_rclone_env(),
            check=True,
            capture_output=True
        )
        logger.info(f"Successfully pulled from S3 bucket '{self.bucket_name}'.")

    def push(self, local_dir: Path, commit_message: str) -> None:
        remote_path = f"s3sync:{self.bucket_name}"
        actual_local_dir = local_dir
        if self.node_name:
            remote_path = f"{remote_path}/{self.node_name}"
            actual_local_dir = local_dir / self.node_name
            actual_local_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Pushing to S3 bucket '{self.bucket_name}' (node: '{self.node_name}') from '{actual_local_dir}'")
        subprocess.run(
            ["rclone", "sync", str(actual_local_dir), remote_path],
            env=self._get_rclone_env(),
            check=True,
            capture_output=True
        )
        logger.info(f"Successfully pushed to S3 bucket '{self.bucket_name}'.")


def start(storage_log, sync_type: str = "huggingface", **kwargs):
    """Starts the Storage Sync Service synchronously to perform pull/push operations."""
    storage_log.write(f"[*] Starting Storage Sync Service for {sync_type}...\n")
    storage_log.flush()

    node_name = kwargs.get("node_name")

    provider = None
    if sync_type == "huggingface":
        repo_id = kwargs.get("repo_id")
        token = kwargs.get("token")
        if not repo_id or not token:
            logger.error("Hugging Face repo_id and token are required for huggingface sync.")
            storage_log.write("[-] Error: hf-repo ID and token are required.\n")
            storage_log.flush()
            return
        provider = HFDatasetProvider(repo_id=repo_id, token=token, node_name=node_name)
    elif sync_type == "s3":
        bucket_name = kwargs.get("bucket_name")
        endpoint = kwargs.get("endpoint")
        access_key = kwargs.get("access_key")
        secret_key = kwargs.get("secret_key")
        if not all([bucket_name, endpoint, access_key, secret_key]):
            logger.error("S3 bucket_name, endpoint, access_key, and secret_key are required for S3 sync.")
            storage_log.write("[-] Error: S3 endpoint credentials are required.\n")
            storage_log.flush()
            return
        provider = S3StorageProvider(
            bucket_name=bucket_name,
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            node_name=node_name
        )
    else:
        logger.error(f"Unknown sync type: {sync_type}")
        storage_log.write(f"[-] Error: Unknown sync type '{sync_type}'\n")
        storage_log.flush()
        return

    if provider:
        logger.info(f"Storage Sync Service ({sync_type}) initialized successfully.")
        
        # Extract operational commands from kwargs
        action = kwargs.get("action")  # "pull" or "push"
        sync_dir = kwargs.get("sync_dir") or kwargs.get("local_path")

        if not sync_dir:
            logger.error("A sync_dir or local_path is required to perform storage sync operations.")
            storage_log.write("[-] Error: Sync target directory not provided.\n")
            storage_log.flush()
            return

        sync_dir = Path(sync_dir)

        if action == "pull":
            storage_log.write(f"[*] Executing pull operation on target: {sync_dir}\n")
            storage_log.flush()
            provider.pull(sync_dir)
        elif action == "push":
            commit_msg = kwargs.get("commit_message", "Automated checkpoint sync via Sanctuary")
            storage_log.write(f"[*] Executing push operation on target: {sync_dir}\n")
            storage_log.flush()
            provider.push(sync_dir, commit_msg)
        elif not action:
            logger.warning("No action specified (standby mode). No transfers performed.")
            storage_log.write("[*] Standby mode: No active action received.\n")
            storage_log.flush()
        else:
            logger.error(f"Invalid storage action: {action}")
            storage_log.write(f"[-] Error: Invalid action '{action}'\n")
            storage_log.flush()