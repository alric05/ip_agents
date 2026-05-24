"""Tests for patent normalization and feature matching utilities."""

from unittest.mock import patch

import pytest

from src.novelty_checker.evaluation.scorers._matching import (
    compute_optimal_feature_alignment,
    embedding_similarity,
    hybrid_feature_score,
    jaccard_similarity,
    levenshtein_ratio,
    longest_common_subsequence_ratio,
    ngram_similarity,
    normalize_patent_number,
    match_patent_family,
    tokenize_feature,
)


# ---------------------------------------------------------------------------
# Patent normalization
# ---------------------------------------------------------------------------

class TestNormalizePatentNumber:
    def test_strips_kind_code(self):
        assert normalize_patent_number("US9924896B2") == "US9924896"

    def test_strips_spaces_and_commas(self):
        assert normalize_patent_number("US 9,924,896 B2") == "US9924896"

    def test_european_patent(self):
        assert normalize_patent_number("EP3456789A1") == "EP3456789"

    def test_wipo_with_slash(self):
        assert normalize_patent_number("WO2020/123456") == "WO2020123456"

    def test_already_normalized(self):
        assert normalize_patent_number("US9924896") == "US9924896"

    def test_lowercase_input(self):
        assert normalize_patent_number("us9924896b2") == "US9924896"

    def test_empty_string(self):
        assert normalize_patent_number("") == ""


class TestMatchPatentFamily:
    def test_exact_match(self):
        assert match_patent_family("US9924896B2", "US9924896B2")

    def test_different_kind_codes(self):
        assert match_patent_family("US9924896B2", "US9924896A1")

    def test_different_formatting(self):
        assert match_patent_family("US 9,924,896 B2", "US9924896B2")

    def test_no_match(self):
        assert not match_patent_family("US9924896B2", "US10234567B1")


# ---------------------------------------------------------------------------
# Text similarity: tokenization
# ---------------------------------------------------------------------------

class TestTokenizeFeature:
    def test_basic_tokenization(self):
        tokens = tokenize_feature("Piezoelectric energy harvesting module")
        assert "piezoelectric" in tokens
        assert "energy" in tokens
        assert "module" in tokens

    def test_removes_stopwords(self):
        tokens = tokenize_feature("the energy of the module")
        assert "the" not in tokens
        assert "of" not in tokens

    def test_removes_short_words(self):
        tokens = tokenize_feature("a b c module")
        assert "a" not in tokens
        assert "module" in tokens


# ---------------------------------------------------------------------------
# Jaccard similarity
# ---------------------------------------------------------------------------

class TestJaccardSimilarity:
    def test_identical_sets(self):
        assert jaccard_similarity({"a", "b", "c"}, {"a", "b", "c"}) == 1.0

    def test_disjoint_sets(self):
        assert jaccard_similarity({"a", "b"}, {"c", "d"}) == 0.0

    def test_partial_overlap(self):
        assert jaccard_similarity({"a", "b", "c"}, {"b", "c", "d"}) == pytest.approx(0.5)

    def test_empty_sets(self):
        assert jaccard_similarity(set(), set()) == 0.0

    def test_one_empty(self):
        assert jaccard_similarity({"a"}, set()) == 0.0


# ---------------------------------------------------------------------------
# N-gram similarity
# ---------------------------------------------------------------------------

class TestNgramSimilarity:
    def test_identical_strings(self):
        assert ngram_similarity("hello", "hello", n=2) == 1.0

    def test_completely_different(self):
        assert ngram_similarity("abc", "xyz", n=2) == 0.0

    def test_similar_strings(self):
        score = ngram_similarity("energy harvesting", "energy harvester", n=2)
        assert 0.5 < score < 1.0

    def test_empty_strings(self):
        assert ngram_similarity("", "hello", n=2) == 0.0
        assert ngram_similarity("", "", n=2) == 0.0

    def test_trigrams(self):
        score = ngram_similarity("piezoelectric", "piezoelectric", n=3)
        assert score == 1.0


# ---------------------------------------------------------------------------
# LCS ratio
# ---------------------------------------------------------------------------

class TestLCSRatio:
    def test_identical_strings(self):
        assert longest_common_subsequence_ratio("hello", "hello") == 1.0

    def test_no_common(self):
        assert longest_common_subsequence_ratio("abc", "xyz") == 0.0

    def test_subsequence(self):
        ratio = longest_common_subsequence_ratio("abcdef", "ace")
        assert ratio == pytest.approx(3.0 / 6.0)

    def test_empty(self):
        assert longest_common_subsequence_ratio("", "abc") == 0.0


# ---------------------------------------------------------------------------
# Levenshtein ratio
# ---------------------------------------------------------------------------

class TestLevenshteinRatio:
    def test_identical(self):
        assert levenshtein_ratio("hello", "hello") == 1.0

    def test_one_char_diff(self):
        ratio = levenshtein_ratio("hello", "hallo")
        assert ratio == pytest.approx(4.0 / 5.0)

    def test_completely_different(self):
        ratio = levenshtein_ratio("abc", "xyz")
        assert ratio == 0.0

    def test_empty_strings(self):
        assert levenshtein_ratio("", "") == 1.0
        assert levenshtein_ratio("abc", "") == 0.0


# ---------------------------------------------------------------------------
# Embedding similarity
# ---------------------------------------------------------------------------

class TestEmbeddingSimilarity:
    def test_identical_text(self):
        score = embedding_similarity("energy harvesting module", "energy harvesting module")
        assert score is not None
        assert score > 0.95

    def test_semantic_match(self):
        """Different wording, same concept — should score higher than lexical."""
        score = embedding_similarity(
            "piezoelectric power generator",
            "vibration to electricity converter",
        )
        assert score is not None
        assert score > 0.3  # semantic similarity should be meaningful

    def test_unrelated_texts(self):
        score = embedding_similarity(
            "energy harvesting sensor node",
            "database connection pool manager",
        )
        assert score is not None
        assert score < 0.4

    def test_empty_text(self):
        assert embedding_similarity("", "hello") == 0.0
        assert embedding_similarity("hello", "") == 0.0


# ---------------------------------------------------------------------------
# Hybrid feature score
# ---------------------------------------------------------------------------

class TestHybridFeatureScore:
    def test_identical_features(self):
        f = {"feature_name": "Piezoelectric energy harvesting"}
        score = hybrid_feature_score(f, f)
        assert score > 0.9

    def test_similar_features(self):
        a = {"feature_name": "Piezoelectric energy harvesting module"}
        b = {"name": "Piezoelectric energy harvester"}
        score = hybrid_feature_score(a, b)
        assert score > 0.5

    def test_different_features(self):
        a = {"feature_name": "Wireless sensor node"}
        b = {"name": "Database connection pool"}
        score = hybrid_feature_score(a, b)
        assert score < 0.3

    def test_empty_feature(self):
        score = hybrid_feature_score({}, {"name": "Something"})
        assert score == 0.0

    def test_custom_weights(self):
        a = {"feature_name": "energy harvesting"}
        b = {"name": "energy harvesting"}
        score = hybrid_feature_score(a, b, weights={
            "jaccard": 1.0, "bigram_dice": 0.0, "lcs_ratio": 0.0, "levenshtein": 0.0,
        })
        assert score == 1.0

    def test_embedding_weight_included(self):
        """Hybrid scorer should use all 5 strategies including embedding."""
        a = {"feature_name": "Piezoelectric energy harvesting module"}
        b = {"name": "Piezoelectric energy harvester"}
        # With embedding weight = 1.0, others = 0 → tests pure embedding path
        score = hybrid_feature_score(a, b, weights={
            "jaccard": 0.0, "bigram_dice": 0.0, "lcs_ratio": 0.0,
            "levenshtein": 0.0, "embedding": 1.0,
        })
        assert score > 0.7  # semantically very similar

    def test_semantic_pair_scores_higher_with_embedding(self):
        """A semantic pair should score higher with embedding than without."""
        a = {"feature_name": "vibration-based power generation"}
        b = {"name": "piezoelectric energy harvesting"}
        # Pure lexical (no embedding)
        lexical_score = hybrid_feature_score(a, b, weights={
            "jaccard": 0.3, "bigram_dice": 0.3, "lcs_ratio": 0.2, "levenshtein": 0.2,
        })
        # With embedding
        full_score = hybrid_feature_score(a, b)  # uses default weights with embedding
        # Embedding should boost the score
        assert full_score >= lexical_score

    def test_graceful_fallback_without_embedding(self):
        """When embedding is unavailable, hybrid should still work with 4 strategies."""
        import src.novelty_checker.evaluation.scorers._matching as mod
        # Temporarily pretend embeddings are unavailable
        orig_available = mod._embedding_available
        orig_model = mod._embedding_model
        mod._embedding_available = False
        mod._embedding_model = None
        try:
            a = {"feature_name": "energy harvesting"}
            b = {"name": "energy harvesting"}
            score = hybrid_feature_score(a, b)
            assert score > 0.9  # identical text, should still score high
        finally:
            mod._embedding_available = orig_available
            mod._embedding_model = orig_model


# ---------------------------------------------------------------------------
# Optimal feature alignment
# ---------------------------------------------------------------------------

class TestOptimalFeatureAlignment:
    def test_perfect_alignment(self):
        agent = [
            {"feature_name": "Feature A"},
            {"feature_name": "Feature B"},
        ]
        gt = [
            {"name": "Feature A"},
            {"name": "Feature B"},
        ]
        matches = compute_optimal_feature_alignment(agent, gt)
        assert len(matches) == 2

    def test_partial_alignment(self):
        agent = [
            {"feature_name": "Feature A"},
            {"feature_name": "Unrelated feature"},
        ]
        gt = [
            {"name": "Feature A"},
            {"name": "Feature B completely different"},
        ]
        matches = compute_optimal_feature_alignment(agent, gt, threshold=0.5)
        assert len(matches) >= 1
        # Feature A should match
        matched_gt = {gt_idx for _, gt_idx, _ in matches}
        assert 0 in matched_gt

    def test_empty_lists(self):
        assert compute_optimal_feature_alignment([], []) == []
        assert compute_optimal_feature_alignment([{"feature_name": "A"}], []) == []

    def test_threshold_filtering(self):
        agent = [{"feature_name": "X"}]
        gt = [{"name": "Y completely unrelated"}]
        matches = compute_optimal_feature_alignment(agent, gt, threshold=0.9)
        assert len(matches) == 0

    def test_order_independent(self):
        """Reversed order should produce identical match count and scores."""
        features = [
            {"feature_name": "Piezoelectric energy harvesting"},
            {"feature_name": "Wireless sensor duty cycling"},
            {"feature_name": "Supercapacitor energy storage"},
        ]
        gt = [
            {"name": "Supercapacitor energy storage"},
            {"name": "Piezoelectric energy harvesting"},
            {"name": "Wireless sensor duty cycling"},
        ]
        matches_orig = compute_optimal_feature_alignment(features, gt)
        matches_rev = compute_optimal_feature_alignment(list(reversed(features)), gt)

        assert len(matches_orig) == 3
        assert len(matches_rev) == 3

        # Scores should be identical (just different index mappings)
        scores_orig = sorted(s for _, _, s in matches_orig)
        scores_rev = sorted(s for _, _, s in matches_rev)
        assert scores_orig == pytest.approx(scores_rev)
