"""Append-only JSONL with hash-chain tamper detection (not a digital signature)."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path

GENESIS = "0" * 64


def canonical(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def file_hash(path: Path) -> str:
    return digest(path.read_bytes()) if path.is_file() else digest(b"")


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    result = []
    predecessor = GENESIS
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            raise ValueError(f"unexpected blank line in {path.name}:{n}")
        obj = json.loads(line)
        if not isinstance(obj, dict) or obj.get("previous_sha256") != predecessor:
            raise ValueError(f"invalid ledger chain in {path.name}:{n}")
        stored = obj.get("event_sha256")
        payload = {k: v for k, v in obj.items() if k != "event_sha256"}
        if not isinstance(stored, str) or stored != digest(canonical(payload)):
            raise ValueError(f"invalid ledger checksum in {path.name}:{n}")
        predecessor = stored
        result.append(obj)
    return result


def append(path: Path, value: dict) -> dict:
    history = load(path)
    item = dict(value)
    if "event_sha256" in item or "previous_sha256" in item:
        raise ValueError("caller cannot supply ledger integrity fields")
    item["previous_sha256"] = history[-1]["event_sha256"] if history else GENESIS
    item["event_sha256"] = digest(canonical(item))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(canonical(item).decode("utf-8") + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return item
