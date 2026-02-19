"""lt_common - S3 client (mock for local dev)."""
import io
from pathlib import Path


class S3Client:
    """Mock S3 client - uses local directory."""

    def __init__(self, base_path: str = "./s3_mock"):
        self.base = Path(base_path)
        self.base.mkdir(parents=True, exist_ok=True)

    def upload(self, key: str, body: bytes | str, bucket: str = "ace") -> str:
        p = self.base / bucket / key
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body.encode() if isinstance(body, str) else body)
        return f"s3://{bucket}/{key}"

    def download(self, key: str, bucket: str = "ace") -> bytes:
        p = self.base / bucket / key
        return p.read_bytes() if p.exists() else b""
