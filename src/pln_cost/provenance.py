"""Verify historical source snapshots without retaining obsolete live files."""
import hashlib
import json
import zipfile


def verify_project_sources(project, batch, hashes):
    """Historical batches bind archived bytes; new batches bind live source.

    This does not claim that current code produced historical measurements.
    Raw results, fixtures and native proof traces are verified separately.
    """
    archive = batch / "source-snapshot.zip"
    if not archive.exists():
        for name, expected in hashes.items():
            if hashlib.sha256((project / name).read_bytes()).hexdigest() != expected:
                raise ValueError(f"Changed frozen file: {name}")
        return "live source"
    metadata = json.loads((batch / "source-snapshot.json").read_text())
    if hashlib.sha256(archive.read_bytes()).hexdigest() != metadata["sha256"]:
        raise ValueError("Changed historical source archive")
    with zipfile.ZipFile(archive) as saved:
        for name, expected in hashes.items():
            if hashlib.sha256(saved.read(name)).hexdigest() != expected:
                raise ValueError(f"Changed historical source: {name}")
    return "archived original source"
