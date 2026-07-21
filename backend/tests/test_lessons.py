"""Unit tests for the long-term lessons store's similarity math — a custom
addition beyond the assignment spec (see README). No DB or OpenAI key
required; `find_similar_lessons` itself needs a live session so it's
exercised via the live smoke test instead, not here."""

from __future__ import annotations

from app.db.repository import cosine_similarity


def test_identical_vectors_have_similarity_one() -> None:
    v = [1.0, 2.0, 3.0]
    assert abs(cosine_similarity(v, v) - 1.0) < 1e-9


def test_orthogonal_vectors_have_similarity_zero() -> None:
    assert abs(cosine_similarity([1.0, 0.0], [0.0, 1.0])) < 1e-9


def test_opposite_vectors_have_similarity_negative_one() -> None:
    assert abs(cosine_similarity([1.0, 2.0], [-1.0, -2.0]) - (-1.0)) < 1e-9


def test_zero_vector_yields_zero_similarity_without_dividing_by_zero() -> None:
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_more_similar_vector_ranks_higher() -> None:
    query = [1.0, 1.0, 0.0]
    close = [1.0, 0.9, 0.1]
    far = [0.0, 0.0, 1.0]
    assert cosine_similarity(query, close) > cosine_similarity(query, far)
