"""Persistent content-addressed AST digests for resumable history scans."""

from pathlib import Path
import sqlite3
import sys


class SignatureCache:
    def __init__(self, repo, version):
        directory = Path(repo).parent.parent / "interim/ast-signatures"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / (
            Path(repo).name
            + "-"
            + version
            + "-py"
            + str(sys.version_info.major)
            + str(sys.version_info.minor)
            + ".sqlite"
        )
        self.connection = sqlite3.connect(path, timeout=30)
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS signatures (blob BLOB PRIMARY KEY, digest BLOB)"
        )
        self.connection.commit()
        self.pending = 0

    def get(self, blob):
        row = self.connection.execute(
            "SELECT digest FROM signatures WHERE blob=?", (blob,)
        ).fetchone()
        if row is None:
            raise KeyError(blob)
        return row[0]

    def put(self, blob, digest):
        self.connection.execute(
            "INSERT OR REPLACE INTO signatures VALUES (?,?)", (blob, digest)
        )
        self.pending += 1
        if self.pending >= 128:
            self.connection.commit()
            self.pending = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        try:
            self.connection.commit()
        finally:
            self.connection.close()
