import os
import subprocess
import logging
from .cmbagent_utils import cmbagent_debug

logger = logging.getLogger(__name__)

# Base URL for the repository containing the data
REPO_URL = "https://github.com/CMBAgents/cmbagent_data.git"


def setup_cmbagent_data():
    # Check if the environment variable is set
    env_path = os.getenv("CMBAGENT_DATA")

    # Case 1: Environment variable is set, ends with "cmbagent_data", and directory has files
    if env_path and env_path.endswith("cmbagent_data") and os.path.isdir(env_path) and os.listdir(env_path):
        if cmbagent_debug:
            logger.debug("using_existing_data_directory", path=env_path)
        return env_path

    # For all other cases (env not set, or invalid/missing directory) use home directory
    home_dir = os.path.expanduser("~")
    target_path = os.path.join(home_dir, "cmbagent_data")

    # Clone the repository if the target directory does not exist or is empty
    if not os.path.exists(target_path) or not os.listdir(target_path):
        if cmbagent_debug:
            logger.debug("cloning_repository", target_path=target_path)
        os.makedirs(target_path, exist_ok=True)
        # Cloning directly into target_path (the command ensures that the repo's content
        # ends up inside target_path)
        subprocess.run(["git", "clone", REPO_URL, target_path], check=True)

    # Set the environment variable
    os.environ["CMBAGENT_DATA"] = target_path
    if cmbagent_debug:
        logger.debug("cmbagent_data_env_set", path=target_path)

    return target_path
