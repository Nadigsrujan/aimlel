"""Transactional local job records shared by API worker processes."""

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path


class JobError(ValueError):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


class JobStore:
    def __init__(self, path):
        self.path = Path(path)

    @contextmanager
    def transaction(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=30)
        try:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, repo TEXT NOT NULL, status TEXT NOT NULL, updated REAL NOT NULL, payload TEXT NOT NULL)"
            )
            connection.commit()
            connection.execute("BEGIN IMMEDIATE")
            # A live worker heartbeats every two seconds, including while cloning.
            # An interrupted worker is recoverable via an explicit retry.
            cutoff = time.time() - 90
            stale = connection.execute(
                "SELECT id,payload FROM jobs WHERE status IN ('running','cancelling') AND updated<?",
                (cutoff,),
            ).fetchall()
            for identifier, payload in stale:
                value = json.loads(payload)
                value.update(
                    status="failed", error="Worker heartbeat expired; retry ingestion"
                )
                self._save(connection, identifier, value)
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _save(self, connection, identifier, value):
        value["job"] = identifier
        connection.execute(
            "INSERT OR REPLACE INTO jobs VALUES (?,?,?,?,?)",
            (
                identifier,
                value["repo"],
                value["status"],
                time.time(),
                json.dumps(value),
            ),
        )

    def create(self, repo, maximum=2):
        with self.transaction() as connection:
            active = connection.execute(
                "SELECT repo FROM jobs WHERE status IN ('running','cancelling')"
            ).fetchall()
            if any(row[0].casefold() == repo.casefold() for row in active):
                raise JobError(409, "Repository ingestion already running")
            if len(active) >= maximum:
                raise JobError(429, "Two ingestion jobs are already running")
            # Retain the newest 100 terminal jobs; active records are never pruned.
            connection.execute(
                "DELETE FROM jobs WHERE id IN (SELECT id FROM jobs WHERE status NOT IN ('running','cancelling') ORDER BY updated DESC LIMIT -1 OFFSET 99)"
            )
            identifier = uuid.uuid4().hex
            value = {
                "repo": repo,
                "status": "running",
                "progress": {"stage": "starting", "elapsed_seconds": 0},
            }
            self._save(connection, identifier, value)
        return identifier, value

    def get(self, identifier):
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT payload FROM jobs WHERE id=?", (identifier,)
            ).fetchone()
            if row is None:
                raise JobError(404, "Unknown job")
            return json.loads(row[0])

    def update(self, identifier, **fields):
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT payload FROM jobs WHERE id=?", (identifier,)
            ).fetchone()
            if row is None:
                raise JobError(404, "Unknown job")
            value = json.loads(row[0])
            if value["status"] not in ("running", "cancelling"):
                return value
            if value["status"] == "cancelling" and fields.get("status") == "processed":
                fields["status"] = "cancelled"
            value.update(fields)
            self._save(connection, identifier, value)
            return value

    def cancel(self, identifier):
        value = self.get(identifier)
        if value["status"] != "running":
            raise JobError(409, "Job is no longer running")
        return self.update(identifier, status="cancelling", error=None)

    def running(self, repo):
        with self.transaction() as connection:
            return (
                connection.execute(
                    "SELECT 1 FROM jobs WHERE status IN ('running','cancelling') AND lower(repo)=lower(?)",
                    (repo,),
                ).fetchone()
                is not None
            )

    def list(self):
        with self.transaction() as connection:
            return [
                json.loads(row[0])
                for row in connection.execute(
                    "SELECT payload FROM jobs ORDER BY updated DESC LIMIT 100"
                )
            ]
