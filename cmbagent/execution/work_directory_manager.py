"""
Work Directory Manager - Isolated work directories for parallel tasks

This module manages isolated work directories for parallel task execution,
preventing file system conflicts between concurrent tasks.
"""

import os
import shutil
import logging
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class WorkDirectoryManager:
    """Manages isolated work directories for parallel task execution"""

    def __init__(self, base_work_dir: str, run_id: str):
        """
        Initialize work directory manager

        Args:
            base_work_dir: Base work directory path
            run_id: Unique run identifier
        """
        self.base_dir = Path(base_work_dir)
        self.run_id = run_id
        self.node_dirs: Dict[str, Path] = {}

        # Create run directory
        self.run_dir = self.base_dir / "runs" / run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)

        # Create main directories
        self.sequential_dir = self.run_dir / "sequential"
        self.parallel_dir = self.run_dir / "parallel"
        self.sequential_dir.mkdir(exist_ok=True)
        self.parallel_dir.mkdir(exist_ok=True)

        logger.info(f"Work directory manager initialized for run {run_id}")

    def create_node_directory(self, node_id: str) -> str:
        """
        Create isolated directory structure for parallel task

        Structure:
        work_dir/
        └── runs/
            └── run_abc123/
                ├── sequential/          # Sequential execution artifacts
                └── parallel/            # Parallel execution artifacts
                    ├── node_1/
                    │   ├── data/
                    │   ├── codebase/
                    │   ├── logs/
                    │   ├── outputs/
                    │   └── temp/
                    ├── node_2/
                    └── node_3/

        Args:
            node_id: Node identifier

        Returns:
            Path to node's work directory
        """
        node_dir = self.parallel_dir / node_id

        # Create subdirectories
        subdirs = ["data", "codebase", "logs", "outputs", "temp", "chats", "cost"]
        for subdir in subdirs:
            (node_dir / subdir).mkdir(parents=True, exist_ok=True)

        self.node_dirs[node_id] = node_dir

        logger.debug(f"Created work directory for node {node_id}: {node_dir}")

        return str(node_dir)

    def get_node_directory(self, node_id: str) -> Optional[str]:
        """
        Get node's work directory path

        Args:
            node_id: Node identifier

        Returns:
            Path to node's work directory or None if not created
        """
        if node_id in self.node_dirs:
            return str(self.node_dirs[node_id])
        return None

    def get_node_subdir(self, node_id: str, subdir: str) -> str:
        """
        Get specific subdirectory for a node

        Args:
            node_id: Node identifier
            subdir: Subdirectory name (data, codebase, logs, outputs, temp)

        Returns:
            Path to subdirectory
        """
        if node_id not in self.node_dirs:
            raise ValueError(f"Node {node_id} directory not created")

        subdir_path = self.node_dirs[node_id] / subdir
        if not subdir_path.exists():
            subdir_path.mkdir(parents=True, exist_ok=True)

        return str(subdir_path)

    def merge_parallel_results(
        self,
        node_ids: List[str],
        preserve_structure: bool = True
    ) -> None:
        """
        Merge outputs from parallel tasks into main work directory

        Args:
            node_ids: List of node IDs to merge
            preserve_structure: Keep node subdirectories in merged output
        """
        logger.info(f"Merging outputs from {len(node_ids)} parallel tasks")

        main_data_dir = self.sequential_dir / "data"
        main_data_dir.mkdir(exist_ok=True)

        for node_id in node_ids:
            if node_id not in self.node_dirs:
                logger.warning(f"Node {node_id} directory not found, skipping")
                continue

            node_dir = self.node_dirs[node_id]

            # Copy outputs
            outputs_dir = node_dir / "outputs"
            if outputs_dir.exists():
                if preserve_structure:
                    # Keep in node-specific subdirectory
                    target_dir = main_data_dir / node_id
                    target_dir.mkdir(exist_ok=True)
                    self._copy_directory_contents(outputs_dir, target_dir)
                else:
                    # Flatten with node ID prefix
                    for file_path in outputs_dir.iterdir():
                        if file_path.is_file():
                            target_path = main_data_dir / f"{node_id}_{file_path.name}"
                            shutil.copy2(file_path, target_path)

            # Copy data outputs
            data_dir = node_dir / "data"
            if data_dir.exists():
                target_dir = main_data_dir / node_id
                target_dir.mkdir(exist_ok=True)
                self._copy_directory_contents(data_dir, target_dir)

        logger.info(
            f"Merged outputs from {len(node_ids)} parallel tasks to {main_data_dir}"
        )

    def cleanup_node_directory(
        self,
        node_id: str,
        keep_outputs: bool = True,
        keep_logs: bool = True
    ) -> None:
        """
        Clean up temporary files for a node

        Args:
            node_id: Node identifier
            keep_outputs: Keep outputs directory
            keep_logs: Keep logs directory
        """
        if node_id not in self.node_dirs:
            logger.warning(f"Node {node_id} directory not found, nothing to clean")
            return

        node_dir = self.node_dirs[node_id]

        # Remove temp files
        temp_dir = node_dir / "temp"
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
            logger.debug(f"Removed temp directory for node {node_id}")

        # Optionally remove other directories
        if not keep_outputs:
            outputs_dir = node_dir / "outputs"
            if outputs_dir.exists():
                shutil.rmtree(outputs_dir)

        if not keep_logs:
            logs_dir = node_dir / "logs"
            if logs_dir.exists():
                shutil.rmtree(logs_dir)

    def cleanup_all(self, keep_outputs: bool = True) -> None:
        """
        Clean up all node directories

        Args:
            keep_outputs: Keep outputs when cleaning
        """
        logger.info(f"Cleaning up {len(self.node_dirs)} node directories")

        for node_id in list(self.node_dirs.keys()):
            self.cleanup_node_directory(node_id, keep_outputs=keep_outputs)

    def delete_node_directory(self, node_id: str) -> None:
        """
        Completely delete node's work directory

        Args:
            node_id: Node identifier
        """
        if node_id not in self.node_dirs:
            return

        node_dir = self.node_dirs[node_id]
        if node_dir.exists():
            shutil.rmtree(node_dir)
            logger.debug(f"Deleted work directory for node {node_id}")

        del self.node_dirs[node_id]

    def get_directory_stats(self, node_id: str) -> Dict[str, int]:
        """
        Get directory size statistics for a node

        Args:
            node_id: Node identifier

        Returns:
            Dictionary with size statistics in bytes
        """
        if node_id not in self.node_dirs:
            raise ValueError(f"Node {node_id} directory not created")

        node_dir = self.node_dirs[node_id]

        stats = {
            "total_bytes": 0,
            "subdirs": {}
        }

        for subdir in ["data", "codebase", "logs", "outputs", "temp"]:
            subdir_path = node_dir / subdir
            if subdir_path.exists():
                size = self._get_directory_size(subdir_path)
                stats["subdirs"][subdir] = size
                stats["total_bytes"] += size

        return stats

    def _copy_directory_contents(self, src: Path, dst: Path) -> None:
        """
        Copy contents of source directory to destination

        Args:
            src: Source directory
            dst: Destination directory
        """
        dst.mkdir(parents=True, exist_ok=True)

        for item in src.iterdir():
            if item.is_file():
                shutil.copy2(item, dst / item.name)
            elif item.is_dir():
                shutil.copytree(item, dst / item.name, dirs_exist_ok=True)

    def _get_directory_size(self, directory: Path) -> int:
        """
        Get total size of directory in bytes

        Args:
            directory: Directory path

        Returns:
            Total size in bytes
        """
        total = 0
        for entry in directory.rglob('*'):
            if entry.is_file():
                try:
                    total += entry.stat().st_size
                except (OSError, FileNotFoundError):
                    pass
        return total

    def __repr__(self) -> str:
        """String representation"""
        return (
            f"WorkDirectoryManager(run_id={self.run_id}, "
            f"nodes={len(self.node_dirs)})"
        )
