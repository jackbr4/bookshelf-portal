"""
CalibreClient — wraps calibredb add, invoked via podman.

The host Calibre library is mounted at /calibre-library inside the container.
The book file's parent directory is mounted read-only at /book-src so
calibredb can read it without touching other parts of the filesystem.
"""

import logging
import re
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class CalibreClient:
    def __init__(self, library_path: str, image: str):
        self.library_path = library_path
        self.image = image

    def add_book(self, file_path: str) -> Optional[int]:
        """
        Add a book file to the Calibre library.

        Returns the new Calibre book id, or None if the add failed.
        Duplicates are always added (--duplicates flag).
        """
        host_file = Path(file_path).resolve()
        if not host_file.exists():
            logger.error("[calibre] file not found: %s", host_file)
            return None

        host_dir = host_file.parent
        container_file = f"/book-src/{host_file.name}"

        cmd = [
            "podman", "run", "--rm",
            "-v", f"{self.library_path}:/calibre-library:U",
            "-v", f"{host_dir}:/book-src:ro",
            self.image,
            "calibredb", "add",
            "--library-path=/calibre-library",
            "--duplicates",
            container_file,
        ]

        logger.info("[calibre] running: %s", " ".join(cmd))
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=120
            )
        except subprocess.TimeoutExpired:
            logger.error("[calibre] calibredb add timed out for %s", host_file.name)
            return None

        if result.returncode != 0:
            logger.error(
                "[calibre] calibredb add failed (rc=%d): %s",
                result.returncode, result.stderr.strip(),
            )
            return None

        logger.info("[calibre] stdout: %s", result.stdout.strip())

        match = re.search(r"Added book ids:\s*(\d+)", result.stdout)
        if match:
            calibre_id = int(match.group(1))
            logger.info("[calibre] added %r → calibre_id=%d", host_file.name, calibre_id)
            return calibre_id

        logger.warning(
            "[calibre] could not parse calibre_id from output: %r", result.stdout[:200]
        )
        return None
