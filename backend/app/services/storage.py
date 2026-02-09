"""
File storage abstraction.

Why an abstraction here? Because the PRD requires S3 in production, but
we want to develop and test locally without AWS credentials. By hiding
the storage details behind a simple interface, switching from local → S3
is a config change, not a code rewrite.

Usage:
    storage = get_storage_service()
    path = await storage.save_file(file, "videos/instructor-123/video.mp4")
    url = await storage.get_file_url("videos/instructor-123/video.mp4")
    await storage.delete_file("videos/instructor-123/video.mp4")
"""

import os
import shutil
from pathlib import Path
from typing import BinaryIO, Union

from fastapi import UploadFile

from app.config import settings


class LocalStorageService:
    """Saves files to a local directory. Used in development.

    Files are stored under backend/uploads/ with the same key structure
    that S3 would use, so the transition is seamless.
    """

    def __init__(self, base_path: str = "uploads"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def save_file(self, file: UploadFile, key: str, filename: str) -> int:
        """Save an uploaded file to local disk.

        Args:
            file: FastAPI UploadFile (supports async read)
            key: The storage key (e.g., "videos/uuid/filename.mp4")
            filename: Original filename (for logging)

        Returns:
            The number of bytes written
        """
        file_path = self.base_path / key
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write in chunks to handle large files without loading into memory
        chunk_size = 1024 * 1024  # 1MB chunks
        total_bytes = 0

        with open(file_path, "wb") as dest:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                dest.write(chunk)
                total_bytes += len(chunk)

        return total_bytes

    async def get_file_url(self, key: str) -> str:
        """Get a URL/path to access the file.

        In local mode, this returns the filesystem path.
        In S3 mode, this would return a presigned URL.
        """
        return str(self.base_path / key)

    async def delete_file(self, key: str) -> bool:
        """Delete a file from storage."""
        file_path = self.base_path / key
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    async def file_exists(self, key: str) -> bool:
        """Check if a file exists in storage."""
        return (self.base_path / key).exists()


# TODO: Add S3StorageService when AWS is configured
# class S3StorageService:
#     """Saves files to AWS S3. Used in production."""
#     ...


def get_storage_service() -> LocalStorageService:
    """Factory function — returns the right storage backend based on config.

    When we add S3 support, this becomes:
        if settings.APP_ENV == "production":
            return S3StorageService(bucket=settings.AWS_S3_BUCKET)
        return LocalStorageService()
    """
    return LocalStorageService()
