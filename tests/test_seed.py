"""Tests for data/seed.py — determinism and coverage design requirements."""

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

# We need to import seed from the data package
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.seed import seed, SYNTHETIC_DIR


@pytest.fixture(autouse=True)
def run_seed(tmp_path, monkeypatch):
    """Redirect SYNTHETIC_DIR to a temp location and run seed() twice."""
    import data.seed as seed_module
    monkeypatch.setattr(seed_module, "SYNTHETIC_DIR", tmp_path / "synthetic")
    # Run twice to check idempotency
    seed_module.seed()
    seed_module.seed()
    return tmp_path / "synthetic"


@pytest.fixture()
def syn_dir(tmp_path):
    import data.seed as seed_module
    return seed_module.SYNTHETIC_DIR


def _checksum(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def test_expected_files_exist(syn_dir):
    expected = [
        "formulary_2024.md",
        "formulary_2026.md",
        "policy_prior_auth_v1.md",
        "policy_prior_auth_v2.md",
        "member_services_faq.md",
        "coverage_policy_2026.md",
        "member_profiles.json",
        "records.sqlite",
    ]
    for fname in expected:
        assert (syn_dir / fname).exists(), f"Missing: {fname}"


def test_versioned_conflict_present(syn_dir):
    """Atorvastatin has different tiers in 2024 vs 2026 (the seeded conflict)."""
    f2024 = (syn_dir / "formulary_2024.md").read_text()
    f2026 = (syn_dir / "formulary_2026.md").read_text()
    # 2024: Tier 2 ($30); 2026: Tier 1 ($10)
    assert "Tier 2" in f2024
    assert "Tier 1" in f2026
    # Both reference atorvastatin
    assert "Atorvastatin" in f2024
    assert "Atorvastatin" in f2026


def test_superseded_doc_present(syn_dir):
    v1 = (syn_dir / "policy_prior_auth_v1.md").read_text()
    assert "Superseded" in v1 or "superseded" in v1


def test_coverage_gap_present(syn_dir):
    """No document should cover dental implants — gap triggers abstention."""
    all_text = " ".join(
        p.read_text() for p in syn_dir.glob("*.md")
    )
    assert "dental implant" not in all_text.lower()


def test_pii_in_profiles(syn_dir):
    profiles = json.loads((syn_dir / "member_profiles.json").read_text())
    assert len(profiles) > 0
    for p in profiles:
        assert "member_id" in p
        assert "ssn" in p
        assert "dob" in p


def test_sqlite_tables_exist(syn_dir):
    conn = sqlite3.connect(str(syn_dir / "records.sqlite"))
    cur = conn.cursor()
    tables = {row[0] for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "members" in tables
    assert "tickets" in tables
    assert "coverage_records" in tables
    conn.close()


def test_sqlite_members_populated(syn_dir):
    conn = sqlite3.connect(str(syn_dir / "records.sqlite"))
    cur = conn.cursor()
    count = cur.execute("SELECT COUNT(*) FROM members").fetchone()[0]
    assert count > 0
    conn.close()


def test_deterministic_output(tmp_path):
    """Running seed twice produces identical file checksums."""
    import data.seed as seed_module

    dir1 = tmp_path / "run1"
    dir2 = tmp_path / "run2"

    monkeypatch_obj = pytest.MonkeyPatch()
    monkeypatch_obj.setattr(seed_module, "SYNTHETIC_DIR", dir1)
    seed_module.seed()
    checksums1 = {
        f.name: _checksum(f) for f in sorted(dir1.iterdir()) if f.suffix in (".md", ".json")
    }

    monkeypatch_obj.setattr(seed_module, "SYNTHETIC_DIR", dir2)
    seed_module.seed()
    checksums2 = {
        f.name: _checksum(f) for f in sorted(dir2.iterdir()) if f.suffix in (".md", ".json")
    }

    monkeypatch_obj.undo()
    assert checksums1 == checksums2
