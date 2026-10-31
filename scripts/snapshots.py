"""Bounded Git blob streaming for immutable Python snapshots."""
from contextlib import contextmanager
import subprocess
from ingest import eligible, extract, git


@contextmanager
def blob_reader(repo):
    process = subprocess.Popen(['git', '-C', str(repo), 'cat-file', '--batch'],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    def read(sha):
        process.stdin.write(sha + b'\n')
        process.stdin.flush()
        header = process.stdout.readline().split()
        if len(header) != 3 or header[1] != b'blob':
            raise ValueError('Invalid Git blob response')
        size = int(header[2])
        if size > 2_000_000:
            remaining = size + 1
            while remaining:
                chunk = process.stdout.read(min(65536, remaining))
                if not chunk:
                    raise ValueError('Truncated Git blob')
                remaining -= len(chunk)
            return None
        content = process.stdout.read(size)
        if len(content) != size or process.stdout.read(1) != b'\n':
            raise ValueError('Truncated Git blob')
        return content
    try:
        yield read
    finally:
        process.stdin.close()
        process.stdout.close()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def build_snapshot(repo, revision):
    nodes, edges, failures, skipped = [], [], [], []
    with blob_reader(repo) as read:
        for entry in git(repo, 'ls-tree', '-r', '-z', revision).split(b'\0'):
            if not entry:
                continue
            metadata, rawpath = entry.split(b'\t', 1)
            mode, kind, blob = metadata.split()
            path = rawpath.decode('utf-8', 'surrogateescape')
            if kind != b'blob' or mode == b'120000' or not eligible(path):
                continue
            content = read(blob)
            if content is None:
                skipped.append(path)
                continue
            n, e, error = extract(path, content)
            nodes.extend(n)
            edges.extend(e)
            if error:
                failures.append({'path': path, 'error': error})
    return {'revision': revision, 'nodes': nodes, 'edges': edges,
            'parse_failures': failures, 'skipped_files': skipped}
