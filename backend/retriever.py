"""TF-IDF retriever over the SHL Individual Test Solutions catalog."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

_DATA_PATH = Path(__file__).parent / "data" / "shl_catalog.json"

# Keys that indicate a pre-packaged Job Solution (out of scope)
_JOB_SOLUTION_SIGNALS = {"job-focused", "package", "bundle"}


def _is_job_solution(item: Dict[str, Any]) -> bool:
    name = item.get("name", "").lower()
    desc = item.get("description", "").lower()
    if "job-focused" in name or "job-focused" in desc:
        return True
    if "solution" in name and any(s in desc for s in ("includes", "package", "bundle")):
        return True
    return False


def _get_test_type(item: Dict[str, Any]) -> str:
    """Map catalog keys to SHL test type codes."""
    keys = " ".join(k.lower() for k in (item.get("keys") or []))
    if "personality" in keys or "behavior" in keys:
        return "P"
    if "ability" in keys or "aptitude" in keys:
        return "A"
    if "simulation" in keys:
        return "S"
    if "situational judgment" in keys or "biodata" in keys:
        return "J"
    if "knowledge" in keys or "skills" in keys:
        return "K"
    return "K"


def _doc_text(item: Dict[str, Any]) -> str:
    """Build a rich searchable document for TF-IDF indexing."""
    # Repeat name 3x to boost exact-name matches
    name = item.get("name", "")
    parts = [
        name, name, name,
        item.get("description", ""),
        " ".join(item.get("keys") or []),
        " ".join(item.get("job_levels") or []),
        " ".join(item.get("languages") or []),
        f"duration {item.get('duration', '')}",
        f"remote {item.get('remote', '')}",
        f"adaptive {item.get('adaptive', '')}",
    ]
    return " ".join(str(p) for p in parts if p)


class CatalogRetriever:
    def __init__(self, path: Path = _DATA_PATH):
        with open(path, "r", encoding="utf-8") as fh:
            raw: List[Dict[str, Any]] = json.load(fh)

        # Filter out Job Solutions — keep Individual Test Solutions only
        self.catalog: List[Dict[str, Any]] = [
            it for it in raw if not _is_job_solution(it)
        ]

        self.docs = [_doc_text(it) for it in self.catalog]
        self.by_name: Dict[str, Dict[str, Any]] = {
            it["name"].lower(): it for it in self.catalog
        }

        self.vectorizer = TfidfVectorizer(
            lowercase=True,
            stop_words="english",
            ngram_range=(1, 3),      # trigrams catch "Java 8 New", "Verify G+"
            max_features=30000,
            sublinear_tf=True,
            min_df=1,
        )
        self.matrix = self.vectorizer.fit_transform(self.docs)

    def search(self, query: str, k: int = 25) -> List[Dict[str, Any]]:
        if not query or not query.strip():
            return []
        q_vec = self.vectorizer.transform([query])
        sims = cosine_similarity(q_vec, self.matrix).ravel()
        # Lower threshold — 0.01 — to avoid dropping valid results
        top_idx = np.argsort(-sims)[:k]
        results = []
        for i in top_idx:
            if sims[i] < 0.01:
                break
            item = self.catalog[i]
            results.append(self._to_dict(item, float(sims[i])))
        return results

    def get_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        if not name:
            return None
        key = name.lower().strip()
        # Exact match
        item = self.by_name.get(key)
        if item:
            return self._to_dict(item)
        # Substring match (handles minor LLM name variations)
        for n_low, it in self.by_name.items():
            if key in n_low or n_low in key:
                return self._to_dict(it)
        return None

    def _to_dict(self, item: Dict[str, Any], score: float = 1.0) -> Dict[str, Any]:
        return {
            "name":        item.get("name"),
            "url":         item.get("link"),          # catalog field is "link"
            "test_type":   _get_test_type(item),
            "description": (item.get("description") or "")[:400],
            "duration":    item.get("duration") or "n/a",
            "job_levels":  item.get("job_levels") or [],
            "languages":   item.get("languages") or [],
            "remote":      item.get("remote") or "",
            "adaptive":    item.get("adaptive") or "",
            "keys":        item.get("keys") or [],
            "score":       score,
        }
