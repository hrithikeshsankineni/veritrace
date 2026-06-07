"""Tests for veritrace.assurance.attacks."""

from __future__ import annotations

from veritrace.assurance.attacks import generate_attacks, AttackCase

_EXPECTED_CLASSES = {"injection", "pii_extraction", "out_of_scope", "unanswerable", "contradiction"}


def test_generate_attacks_returns_list():
    attacks = generate_attacks("demo")
    assert isinstance(attacks, list)
    assert len(attacks) > 0


def test_all_attack_classes_present():
    attacks = generate_attacks("demo")
    classes = {a["attack_class"] for a in attacks}
    assert classes == _EXPECTED_CLASSES


def test_each_class_has_multiple_cases():
    attacks = generate_attacks("demo")
    from collections import Counter
    counts = Counter(a["attack_class"] for a in attacks)
    for cls in _EXPECTED_CLASSES:
        assert counts[cls] >= 2, f"Class {cls!r} has fewer than 2 cases"


def test_attack_ids_unique():
    attacks = generate_attacks("demo")
    ids = [a["attack_id"] for a in attacks]
    assert len(ids) == len(set(ids))


def test_all_attacks_expect_pass():
    """All static attacks expect the system to defend correctly."""
    attacks = generate_attacks("demo")
    assert all(a["expected_pass"] is True for a in attacks)


def test_attacks_have_required_fields():
    attacks = generate_attacks("demo")
    for a in attacks:
        assert a["attack_id"]
        assert a["attack_class"]
        assert a["prompt"]
        assert isinstance(a["expected_pass"], bool)
        assert "notes" in a


def test_generate_is_deterministic():
    a1 = generate_attacks("demo")
    a2 = generate_attacks("demo")
    assert [x["attack_id"] for x in a1] == [x["attack_id"] for x in a2]


def test_generate_returns_independent_copies():
    """Mutating one result must not affect subsequent calls."""
    attacks1 = generate_attacks("demo")
    attacks1[0]["prompt"] = "MUTATED"
    attacks2 = generate_attacks("demo")
    assert attacks2[0]["prompt"] != "MUTATED"


def test_injection_attacks_present():
    attacks = generate_attacks("demo")
    inj = [a for a in attacks if a["attack_class"] == "injection"]
    assert any("ignore" in a["prompt"].lower() or "jailbreak" in a["prompt"].lower() for a in inj)


def test_contradiction_covers_atorvastatin():
    attacks = generate_attacks("demo")
    con = [a for a in attacks if a["attack_class"] == "contradiction"]
    assert any("atorvastatin" in a["prompt"].lower() for a in con)
