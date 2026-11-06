# SPDX-License-Identifier: MIT
# From LATTICE's tools/knowledge/embed.py, relicensed MIT by its author.
"""Rank entries by how close their meaning is to a question.

One model embeds both sides, so a question's vector can be compared with an entry's. The model is
the configuration's ``[embedding]``, by default ``BAAI/bge-small-en-v1.5`` (MIT licence) run from
its ONNX export by onnxruntime, pinned by revision and each file checked by SHA-256. It is fetched
into the platform's cache folder on first use. Vectors from two models do not share a space, so a
set of vectors records the revision that made it and is refused by any other.

The caller gives the text of each node. The vectors are written to a directory, keyed by node and
by a digest of its text, so a rebuild embeds only what changed. When the model cannot be fetched or
run, ``build`` removes any vectors and raises, so a stale set is never ranked against changed text.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import platformdirs

VECTORS = "vectors.npz"


@dataclass(frozen=True)
class ModelSpec:
    """A pinned embedding model, and the scores measured for it. The thresholds belong to a model,
    so they move with it: WEAK and NEAR were measured for bge-small on LATTICE's questions."""

    repo: str = "BAAI/bge-small-en-v1.5"
    revision: str = "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"
    files: dict[str, str] = field(default_factory=lambda: {
        "onnx/model.onnx": "828e1496d7fabb79cfa4dcd84fa38625c0d3d21da474a00f08db0f559940cf35",
        "tokenizer.json": "d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66",
    })
    # The instruction the model was trained to read before a question, and never before a passage.
    query_prefix: str = "Represent this sentence for searching relevant passages: "
    weak: float = 0.69
    near: float = 0.74
    facet_boost: float = 0.02
    cache: Path | None = None

    @property
    def directory(self) -> Path:
        base = self.cache or platformdirs.user_cache_path("vyvid") / "model"
        return base / re.sub(r"[^A-Za-z0-9._-]+", "--", self.repo) / self.revision


class Unavailable(Exception):
    """The model cannot be fetched or run here, or the vectors are missing or stale, with the reason."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch(spec: ModelSpec) -> Path:
    """The pinned model's directory, downloading any file that is missing.

    A file reaches its own name only after its SHA-256 matched, so one that is there is trusted
    without hashing it again on every question."""
    for name, digest in spec.files.items():
        path = spec.directory / name
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://huggingface.co/{spec.repo}/resolve/{spec.revision}/{name}"
        part = path.with_name(path.name + ".part")
        try:
            with urllib.request.urlopen(url, timeout=120) as response, part.open("wb") as handle:
                shutil.copyfileobj(response, handle)
        except OSError as error:
            raise Unavailable(f"could not fetch {url}: {error}") from error
        if _sha256(part) != digest:
            part.unlink()
            # A proxy's block page arrives as a successful download, so this is its usual symptom.
            raise Unavailable(f"{url} does not match its pinned SHA-256, which a proxy block page also causes")
        part.replace(path)
    return spec.directory


class Model:
    def __init__(self, spec: ModelSpec) -> None:
        try:
            import onnxruntime
            from tokenizers import Tokenizer
        except ImportError as error:
            raise Unavailable(f"{error.name} is not installed") from error
        self.spec = spec
        root = fetch(spec)
        self.tokenizer = Tokenizer.from_file(str(root / "tokenizer.json"))
        self.tokenizer.enable_truncation(512)
        self.tokenizer.enable_padding()
        options = onnxruntime.SessionOptions()
        options.log_severity_level = 3
        model = next(name for name in spec.files if name.endswith(".onnx"))
        self.session = onnxruntime.InferenceSession(str(root / model), options, providers=["CPUExecutionProvider"])

    def embed(self, texts: list[str]) -> np.ndarray:
        """One unit vector per text: the model's first-token state, as bge is trained to give it."""
        out = []
        for start in range(0, len(texts), 32):
            encoded = self.tokenizer.encode_batch(texts[start : start + 32])
            feed = {
                name: np.array([getattr(e, attr) for e in encoded], dtype=np.int64)
                for name, attr in (("input_ids", "ids"), ("attention_mask", "attention_mask"), ("token_type_ids", "type_ids"))
            }
            out.append(self.session.run(None, feed)[0][:, 0])
        vectors = np.vstack(out).astype(np.float32)
        return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)

    def question(self, text: str) -> np.ndarray:
        return self.embed([self.spec.query_prefix + text])[0]


def join_text(parts) -> str:
    """The parts of an entry's text, each once, in order, without Markdown emphasis."""
    cleaned = (p.replace("**", "").strip() for p in parts if p)
    return ". ".join(dict.fromkeys(p for p in cleaned if p))


def _cached(source: Path, spec: ModelSpec) -> dict[str, np.ndarray]:
    if not source.exists():
        return {}
    with np.load(source) as previous:
        if str(previous["revision"]) != spec.revision:
            return {}
        return dict(zip(previous["digests"].tolist(), previous["vectors"]))


def build(entries: dict[str, str], directory: Path, spec: ModelSpec, model=None, warm: Path | None = None, name: str = VECTORS) -> int:
    """Write the vectors of every node's text into ``directory`` as ``name``, embedding only text not seen before.
    ``warm`` is another directory of vectors whose texts are reused too, so stores share one cache.

    Returns how many texts were embedded this time. Raises Unavailable, having removed any vectors,
    so a stale set is never ranked against a changed index."""
    target = directory / name
    digests = {node: hashlib.sha256(text.encode("utf-8")).hexdigest() for node, text in entries.items()}
    cached = {**_cached(warm / name, spec), **_cached(target, spec)} if warm else _cached(target, spec)
    by_digest = {digests[node]: text for node, text in entries.items()}
    # A batch is padded to its longest text, so texts of a length are embedded together. Measured
    # on LATTICE, 2026-10-28: a cold build of 5,168 texts took 317 s in any other order, and 60 s in this one.
    todo = sorted((d for d in by_digest if d not in cached), key=lambda d: (len(by_digest[d]), d))
    if todo:
        try:
            model = model or Model(spec)
        except Unavailable:
            target.unlink(missing_ok=True)
            raise
        for digest, vector in zip(todo, model.embed([by_digest[d] for d in todo])):
            cached[digest] = vector
    directory.mkdir(parents=True, exist_ok=True)
    nodes = sorted(entries)
    np.savez(
        target,
        revision=np.array(spec.revision),
        nodes=np.array(nodes),
        digests=np.array([digests[n] for n in nodes]),
        vectors=np.vstack([cached[digests[n]] for n in nodes]) if nodes else np.zeros((0, 1), dtype=np.float32),
    )
    return len(todo)


def load(directory: Path, spec: ModelSpec, name: str = VECTORS) -> tuple[list[str], np.ndarray]:
    """The nodes and their vectors, or Unavailable if none were written or another model made them."""
    target = directory / name
    if not target.exists():
        raise Unavailable(f"no {name} in {directory}. Run vyd build, which says why")
    with np.load(target) as saved:
        if str(saved["revision"]) != spec.revision:
            raise Unavailable("the vectors were made by another model revision. Rebuild the index")
        return saved["nodes"].tolist(), saved["vectors"]
