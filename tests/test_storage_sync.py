import os
import shutil
import sys
import unittest
from pathlib import Path

import yaml
from dotenv import load_dotenv
from loguru import logger

# Align python path to resolve src/ imports cleanly

from sanctuary.core.service_logs import ServiceLogPipe
from sanctuary.services import storage_sync_service


class TestStorageSyncService(unittest.TestCase):

    def setUp(self):
        # Initialize the variable immediately so tearDown doesn't crash
        self.project_root = Path(__file__).resolve().parent.parent
        self.test_dir = self.project_root / "test_storage_data"
        
        # Now proceed with logic
        load_dotenv(self.project_root / ".env")
        
        try:
            self.test_dir.mkdir(exist_ok=True)
            
            nodes_yaml_path = self.project_root / "manifests" / "nodes.yaml"
            with nodes_yaml_path.open("r") as f:
                nodes_config = yaml.safe_load(f)
            
            first_node_name = list(nodes_config["nodes"].keys())[0]
            node_info = nodes_config["nodes"][first_node_name]
            
            self.hf_repo_id = (node_info.get("storage") or {}).get("repo-id") or node_info.get("hf-repo")
            self.hf_token_env = node_info.get("token-env", "HF_TOKEN")
            self.hf_token = os.getenv(self.hf_token_env) or os.getenv("HF_TOKEN")

            if not self.hf_token:
                self.skipTest(f"Missing HF token in {self.hf_token_env}")
                
            self.storage_log = ServiceLogPipe("TEST_STORAGE_SYNC")
            logger.info(f"Test setup complete for: {self.hf_repo_id}")
            
        except Exception as e:
            logger.error(f"Setup failed: {e}")
            raise e # This will show you the REAL error instead of the AttributeError

    def tearDown(self):
        # Clean up temporary test files on completion
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_huggingface_sync_roundtrip(self):
        """Verifies a full round-trip push, local deletion, pull, and comparison."""
        
        # Paths for distinct push and pull phases to prevent false-positives
        push_dir = self.test_dir / "push_data"
        pull_dir = self.test_dir / "pull_data"
        
        push_dir.mkdir()
        pull_dir.mkdir()

        # Step 1: Write initial test payload locally
        test_file_name = "test_file.txt"
        payload_content = f"Sanctuary integration verification token: {os.urandom(8).hex()}"
        
        local_file = push_dir / test_file_name
        local_file.write_text(payload_content)

        logger.info("Pushing test payload to Hugging Face...")
        # Step 2: Push local_file to remote storage
        storage_sync_service.start(
            self.storage_log,
            action="push", # Explicitly declare operation direction
            sync_type="huggingface",
            repo_id=self.hf_repo_id,
            token=self.hf_token,
            sync_dir=push_dir
        )

        # Step 3: Pull to a completely separate, clean directory
        logger.info("Pulling payload from Hugging Face to a clean directory...")
        storage_sync_service.start(
            self.storage_log,
            action="pull", # Explicitly declare operation direction
            sync_type="huggingface",
            repo_id=self.hf_repo_id,
            token=self.hf_token,
            sync_dir=pull_dir
        )

        # Step 4: Verify the file pulled matches the file pushed
        pulled_file = pull_dir / test_file_name
        
        # Verify existence
        self.assertTrue(
            pulled_file.is_file(), 
            f"The pulled file {test_file_name} does not exist in the target directory."
        )
        
        # Verify content matches original payload
        self.assertEqual(
            pulled_file.read_text(), 
            payload_content,
            "The pulled file content does not match the original pushed payload."
        )
        logger.success("Hugging Face synchronization integration test passed.")


if __name__ == '__main__':
    unittest.main()