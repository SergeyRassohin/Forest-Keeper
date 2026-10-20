"""Failure-path tests for artifact verification; no network or real weights."""

import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import models


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "weights"
        self.data = b"a small artificial model artifact"
        self.file = {
            "path": "weights",
            "size": len(self.data),
            "sha256": hashlib.sha256(self.data).hexdigest(),
        }

    def test_corrupted_same_size_file_is_rejected(self):
        self.path.write_bytes(b"x" * len(self.data))
        self.assertFalse(models.verify(self.path, self.file))

    def test_atomic_replacement_after_verification(self):
        self.path.write_bytes(b"old")
        with patch.object(models, "request", return_value=io.BytesIO(self.data)):
            models.download(self.path, self.file, "https://huggingface.co/example")
        self.assertTrue(models.verify(self.path, self.file))
        self.assertFalse(self.path.with_suffix(".part").exists())

    def test_failed_checksum_keeps_previous_file(self):
        self.path.write_bytes(b"old")
        with (
            patch.object(models, "request", return_value=io.BytesIO(b"x" * len(self.data))),
            self.assertRaisesRegex(ValueError, "checksum mismatch"),
        ):
            models.download(self.path, self.file, "https://huggingface.co/example")
        self.assertEqual(self.path.read_bytes(), b"old")
        self.assertFalse(self.path.with_suffix(".part").exists())

    def test_oversized_download_is_rejected(self):
        with (
            patch.object(models, "request", return_value=io.BytesIO(self.data + b"extra")),
            self.assertRaisesRegex(ValueError, "exceeds"),
        ):
            models.download(self.path, self.file, "https://huggingface.co/example")
        self.assertFalse(self.path.exists())

    def test_concurrent_partial_is_not_deleted(self):
        partial = self.path.with_suffix(".part")
        partial.write_bytes(b"another downloader")
        with self.assertRaisesRegex(ValueError, "Partial file exists"):
            models.download(self.path, self.file, "https://huggingface.co/example")
        self.assertEqual(partial.read_bytes(), b"another downloader")

    def test_unpinned_catalog_is_rejected(self):
        manifest, _lock = models.catalog()
        manifest["llm"]["revision"] = "main"
        with (
            patch.object(models.yaml, "safe_load", return_value=manifest),
            self.assertRaisesRegex(ValueError, "mismatch"),
        ):
            models.catalog()


if __name__ == "__main__":
    unittest.main()
