"""Matching utilities for patent numbers and feature comparison.

Provides patent number normalization, multiple text similarity strategies
(Jaccard, n-gram Dice, LCS, Levenshtein, embedding cosine), and optimal
feature alignment.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from typing import Any

import numpy as np

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Patent number normalization
# ---------------------------------------------------------------------------

# Common kind codes to strip (e.g., A1, A2, B1, B2, C)
_KIND_CODE_RE = re.compile(r"\s*[A-C]\d?\s*$")
# Non-alphanumeric characters to strip
_NON_ALNUM_RE = re.compile(r"[^A-Z0-9]")


def normalize_patent_number(pub_number: str) -> str:
    """Normalize a patent publication number for comparison.

    Strips kind codes, whitespace, commas, and hyphens.
    Examples:
        "US 9,924,896 B2"  -> "US9924896"
        "US9924896B2"       -> "US9924896"
        "EP3456789A1"       -> "EP3456789"
        "WO2020/123456"     -> "WO2020123456"
    """
    s = pub_number.strip().upper()
    # Remove kind code suffix
    s = _KIND_CODE_RE.sub("", s)
    # Remove all non-alphanumeric characters
    s = _NON_ALNUM_RE.sub("", s)
    return s


def match_patent_family(agent_ref: str, gt_ref: str) -> bool:
    """Check if two patent references match at the family level.

    Phase 1: normalized publication number exact match.
    Phase 2 (future): INPADOC family lookup.
    """
    return normalize_patent_number(agent_ref) == normalize_patent_number(gt_ref)


def extract_patent_number(ref: dict[str, Any]) -> str:
    """Extract the publication number from a reference dict.

    Handles varying key names used across the codebase.
    """
    for key in ("publication_number", "pub_number", "ref_id", "patent_number", "id"):
        val = ref.get(key, "")
        if val and isinstance(val, str):
            return val
    return ""


# ---------------------------------------------------------------------------
# Text similarity: tokenization
# ---------------------------------------------------------------------------

_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "of", "to", "in", "for", "with",
    "on", "at", "by", "is", "it", "as", "be", "that", "this", "from",
    "are", "was", "were", "been", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "could", "should", "may",
    "can", "not", "no", "but", "if", "than", "then", "so", "such",
    "which", "who", "whom", "what", "where", "when", "how",
})


def tokenize_feature(text: str) -> set[str]:
    """Tokenize text into a set of meaningful lowercase words."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 1}


# ---------------------------------------------------------------------------
# Text similarity: Jaccard
# ---------------------------------------------------------------------------

def jaccard_similarity(set_a: set[str], set_b: set[str]) -> float:
    """Compute Jaccard similarity between two token sets.

    Returns 0.0 if both sets are empty.
    """
    if not set_a and not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


# ---------------------------------------------------------------------------
# Text similarity: character n-gram Dice coefficient
# ---------------------------------------------------------------------------

def _char_ngrams(text: str, n: int) -> Counter:
    """Generate character n-grams from text."""
    text = text.lower().strip()
    return Counter(text[i : i + n] for i in range(len(text) - n + 1))


def ngram_similarity(text_a: str, text_b: str, n: int = 2) -> float:
    """Compute Dice coefficient on character n-grams.

    Dice = 2 * |intersection| / (|A| + |B|)
    Default n=2 (bigrams). Use n=3 for trigrams.
    """
    if not text_a or not text_b:
        return 0.0
    ngrams_a = _char_ngrams(text_a, n)
    ngrams_b = _char_ngrams(text_b, n)
    if not ngrams_a or not ngrams_b:
        return 0.0

    # Intersection count: min of each n-gram count
    intersection = sum((ngrams_a & ngrams_b).values())
    total = sum(ngrams_a.values()) + sum(ngrams_b.values())
    return (2.0 * intersection) / total if total > 0 else 0.0


# ---------------------------------------------------------------------------
# Text similarity: Longest Common Subsequence
# ---------------------------------------------------------------------------

def longest_common_subsequence_ratio(text_a: str, text_b: str) -> float:
    """Compute LCS ratio: LCS length / max(len(a), len(b)).

    Captures sequence-level similarity — good for detecting reordered
    but overlapping feature descriptions.
    """
    a = text_a.lower().strip()
    b = text_b.lower().strip()
    if not a or not b:
        return 0.0

    m, n = len(a), len(b)
    # Space-optimized DP: only keep two rows
    prev = [0] * (n + 1)
    curr = [0] * (n + 1)
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                curr[j] = prev[j - 1] + 1
            else:
                curr[j] = max(prev[j], curr[j - 1])
        prev, curr = curr, [0] * (n + 1)

    lcs_len = prev[n]
    return lcs_len / max(m, n)


# ---------------------------------------------------------------------------
# Text similarity: Levenshtein ratio
# ---------------------------------------------------------------------------

def levenshtein_ratio(text_a: str, text_b: str) -> float:
    """Compute normalized Levenshtein similarity: 1 - (edit_dist / max_len).

    Good for detecting near-matches with minor typos or phrasing differences.
    """
    a = text_a.lower().strip()
    b = text_b.lower().strip()
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0

    m, n = len(a), len(b)
    # Space-optimized DP
    prev = list(range(n + 1))
    for i in range(1, m + 1):
        curr = [i] + [0] * n
        for j in range(1, n + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            curr[j] = min(
                prev[j] + 1,      # deletion
                curr[j - 1] + 1,   # insertion
                prev[j - 1] + cost,  # substitution
            )
        prev = curr

    edit_dist = prev[n]
    return 1.0 - (edit_dist / max(m, n))


# ---------------------------------------------------------------------------
# Text similarity: sentence embedding cosine similarity
# ---------------------------------------------------------------------------

_embedding_model = None
_embedding_available: bool | None = None


def _get_embedding_model():
    """Lazy-load sentence-transformers model. Cached after first call.

    Uses all-MiniLM-L6-v2 (22M params, fast, good quality).
    Returns None if sentence-transformers is not installed.
    """
    global _embedding_model, _embedding_available
    if _embedding_available is False:
        return None
    if _embedding_model is not None:
        return _embedding_model
    try:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        _embedding_available = True
        return _embedding_model
    except ImportError:
        _logger.warning(
            "sentence-transformers not installed; embedding similarity disabled. "
            "Install with: pip install sentence-transformers"
        )
        _embedding_available = False
        return None


def embedding_similarity(text_a: str, text_b: str) -> float | None:
    """Compute cosine similarity between sentence embeddings.

    Returns:
        Similarity score in [0.0, 1.0], or None if sentence-transformers
        is not available.
    """
    if not text_a or not text_b:
        return 0.0

    model = _get_embedding_model()
    if model is None:
        return None

    embeddings = model.encode([text_a.lower().strip(), text_b.lower().strip()])
    a, b = embeddings[0], embeddings[1]

    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    if norm_a == 0 or norm_b == 0:
        return 0.0

    cosine = dot_product / (norm_a * norm_b)
    return max(0.0, float(cosine))


# ---------------------------------------------------------------------------
# Hybrid feature score
# ---------------------------------------------------------------------------

_DEFAULT_WEIGHTS = {
    "jaccard": 0.15,
    "bigram_dice": 0.15,
    "lcs_ratio": 0.1,
    "levenshtein": 0.1,
    "embedding": 0.5,
}

# Fallback weights when embedding is not available
_FALLBACK_WEIGHTS = {
    "jaccard": 0.3,
    "bigram_dice": 0.3,
    "lcs_ratio": 0.2,
    "levenshtein": 0.2,
}


def hybrid_feature_score(
    agent_feature: dict[str, str],
    gt_feature: dict[str, str],
    weights: dict[str, float] | None = None,
) -> float:
    """Compute a weighted combination of multiple similarity metrics.

    Compares feature name + description text using up to five strategies:
    - Jaccard similarity on word tokens
    - Bigram Dice coefficient on characters
    - LCS ratio on characters
    - Levenshtein ratio on characters
    - Cosine similarity on sentence embeddings (if sentence-transformers installed)

    If sentence-transformers is not installed, gracefully falls back to the
    four lexical strategies with rebalanced weights.

    Args:
        agent_feature: Dict with at least "feature_name" (and optionally
            "description", "keywords").
        gt_feature: Dict with at least "name" or "feature_name" (and
            optionally "description").
        weights: Optional override for strategy weights. Keys:
            "jaccard", "bigram_dice", "lcs_ratio", "levenshtein", "embedding".

    Returns:
        Similarity score between 0.0 and 1.0.
    """
    w = weights or _DEFAULT_WEIGHTS

    # Build comparison strings: combine name + description
    agent_text = _build_comparison_text(agent_feature)
    gt_text = _build_comparison_text(gt_feature)

    if not agent_text or not gt_text:
        return 0.0

    agent_tokens = tokenize_feature(agent_text)
    gt_tokens = tokenize_feature(gt_text)

    scores: dict[str, float] = {
        "jaccard": jaccard_similarity(agent_tokens, gt_tokens),
        "bigram_dice": ngram_similarity(agent_text, gt_text, n=2),
        "lcs_ratio": longest_common_subsequence_ratio(agent_text, gt_text),
        "levenshtein": levenshtein_ratio(agent_text, gt_text),
    }

    # Try embedding similarity
    emb_score = embedding_similarity(agent_text, gt_text)
    if emb_score is not None:
        scores["embedding"] = emb_score
    elif weights is None:
        # Embedding unavailable and no custom weights — use fallback weights
        w = _FALLBACK_WEIGHTS

    total_weight = sum(w.get(k, 0) for k in scores)
    if total_weight == 0:
        return 0.0

    return sum(scores[k] * w.get(k, 0) for k in scores) / total_weight


def _build_comparison_text(feature: dict[str, str]) -> str:
    """Build a single comparison string from a feature dict."""
    parts = []
    # Try multiple key names for the feature name
    for key in ("feature_name", "name", "title"):
        # val = feature.get(key, "").strip()
        val = feature.get(key) or ""
        val = val.strip()
        if val:
            parts.append(val)
            break
    # Add description if available
    for key in ("description", "keywords", "details"):
        val = feature.get(key) or ""
        if isinstance(val, list):
            # Flatten nested lists (keyword synonym groups)
            flat = []
            for item in val:
                if isinstance(item, list):
                    flat.extend(item)
                elif isinstance(item, str):
                    flat.append(item)
            val = " ".join(flat)
        val = val.strip()
        if val:
            parts.append(val)
            break
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Optimal feature alignment
# ---------------------------------------------------------------------------

def compute_optimal_feature_alignment(
    agent_features: list[dict[str, str]],
    gt_features: list[dict[str, str]],
    threshold: float = 0.3,
    weights: dict[str, float] | None = None,
) -> list[tuple[int, int, float]]:
    """Find the best 1:1 alignment between agent and GT features.

    Uses a greedy algorithm: compute all pairwise scores, then greedily
    assign the highest-scoring pairs first, subject to 1:1 constraint
    and minimum threshold.

    Args:
        agent_features: List of agent feature dicts.
        gt_features: List of ground truth feature dicts.
        threshold: Minimum hybrid score to consider a valid match.
        weights: Optional override for hybrid_feature_score weights.

    Returns:
        List of (agent_idx, gt_idx, score) tuples for matched pairs.
    """
    if not agent_features or not gt_features:
        return []

    # Compute all pairwise scores
    pairs: list[tuple[int, int, float]] = []
    for i, af in enumerate(agent_features):
        for j, gf in enumerate(gt_features):
            score = hybrid_feature_score(af, gf, weights)
            if score >= threshold:
                pairs.append((i, j, score))

    # Greedy matching: sort by score descending, assign greedily
    pairs.sort(key=lambda x: x[2], reverse=True)
    used_agent: set[int] = set()
    used_gt: set[int] = set()
    matches: list[tuple[int, int, float]] = []

    for agent_idx, gt_idx, score in pairs:
        if agent_idx not in used_agent and gt_idx not in used_gt:
            matches.append((agent_idx, gt_idx, score))
            used_agent.add(agent_idx)
            used_gt.add(gt_idx)

    return matches
