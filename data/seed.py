"""Synthetic data seed — deterministic, reproducible.

Run this once before ingestion:
    python data/seed.py

Re-running produces identical output (same content, same filenames).

Corpus design:
  (a) Versioned conflict   — formulary_2024.md vs formulary_2026.md have
                             contradicting copay tiers for atorvastatin.
  (b) Superseded doc       — policy_prior_auth_v1.md is superseded by v2.
  (c) Coverage gap         — no document covers "dental implant coverage",
                             so that query must trigger abstention.
  (d) PII/PHI in profiles  — synthetic member profiles with fake member IDs,
                             SSNs, DOBs, diagnoses.
  (e) records.sqlite       — ticket + coverage records for tool calls.
"""

from __future__ import annotations

import sqlite3
import textwrap
from pathlib import Path

SYNTHETIC_DIR = Path(__file__).parent / "synthetic"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")


# ---------------------------------------------------------------------------
# (a) & (b) Formulary and policy documents
# ---------------------------------------------------------------------------

FORMULARY_2024 = """\
---
source_id: formulary_2024
title: Formulary Drug Coverage — Plan Year 2024
authority_level: primary
effective_date: "2024-01-01"
superseded_by: formulary_2026
tenant_id: demo
---

# Formulary Drug Coverage — Plan Year 2024

## Overview

This formulary lists covered prescription drugs and their cost-sharing tiers
for HealthPlan Demo members during plan year 2024.

## Tier Structure

| Tier | Description | Copay (30-day supply) |
|------|-------------|----------------------|
| Tier 1 | Preferred generics | $10 |
| Tier 2 | Non-preferred generics | $30 |
| Tier 3 | Preferred brand | $60 |
| Tier 4 | Non-preferred brand | $90 |

## Covered Medications — Cardiovascular

### Statins

- **Atorvastatin (generic)** — Tier 2 — $30 copay
  - Prior authorization required for doses above 40 mg.
  - Available at all in-network pharmacies.

- **Rosuvastatin (generic)** — Tier 1 — $10 copay

- **Simvastatin (generic)** — Tier 1 — $10 copay

## Mental Health Medications

- **Sertraline (generic)** — Tier 1 — $10 copay
- **Escitalopram (generic)** — Tier 1 — $10 copay

## Specialty Medications

Specialty medications require prior authorization. See the prior authorization
policy for details.

*This formulary is subject to change. Superseded by the 2026 Formulary.*
"""

FORMULARY_2026 = """\
---
source_id: formulary_2026
title: Formulary Drug Coverage — Plan Year 2026
authority_level: primary
effective_date: "2026-01-01"
supersedes: formulary_2024
tenant_id: demo
---

# Formulary Drug Coverage — Plan Year 2026

## Overview

This formulary lists covered prescription drugs and their cost-sharing tiers
for HealthPlan Demo members during plan year 2026. This document supersedes
the 2024 Formulary.

## Tier Structure

| Tier | Description | Copay (30-day supply) |
|------|-------------|----------------------|
| Tier 1 | Preferred generics | $10 |
| Tier 2 | Non-preferred generics | $35 |
| Tier 3 | Preferred brand | $65 |
| Tier 4 | Non-preferred brand | $95 |

## Covered Medications — Cardiovascular

### Statins

- **Atorvastatin (generic)** — Tier 1 — $10 copay
  - No prior authorization required for standard doses (up to 80 mg).
  - Available at all in-network pharmacies.

- **Rosuvastatin (generic)** — Tier 1 — $10 copay

- **Simvastatin (generic)** — Tier 1 — $10 copay

## Mental Health Medications

- **Sertraline (generic)** — Tier 1 — $10 copay
- **Escitalopram (generic)** — Tier 1 — $10 copay
- **Bupropion (generic)** — Tier 1 — $10 copay (new in 2026)

## Specialty Medications

Specialty medications require prior authorization. See the prior authorization
policy (v2) for details.

*This is the current formulary effective January 1, 2026.*
"""

PRIOR_AUTH_V1 = """\
---
source_id: policy_prior_auth_v1
title: Prior Authorization Policy — Version 1 (Superseded)
authority_level: secondary
effective_date: "2023-06-01"
superseded_by: policy_prior_auth_v2
tenant_id: demo
---

# Prior Authorization Policy — Version 1 (Superseded)

> **Notice:** This policy has been superseded by Prior Authorization Policy v2
> effective January 1, 2025. Please refer to the current policy.

## Purpose

This policy establishes criteria for prior authorization (PA) of specialty and
high-cost medications.

## Covered Under PA — Version 1

The following medication classes required PA under this version:

- All specialty medications
- Statins at doses above 40 mg
- Biologics (all)
- Any medication with a monthly cost exceeding $500

## Approval Criteria (v1)

1. Medical necessity documentation required.
2. Step therapy: generic alternatives must have been tried first.
3. Approval valid for 12 months.

*This version is no longer in effect.*
"""

PRIOR_AUTH_V2 = """\
---
source_id: policy_prior_auth_v2
title: Prior Authorization Policy — Version 2 (Current)
authority_level: primary
effective_date: "2025-01-01"
supersedes: policy_prior_auth_v1
tenant_id: demo
---

# Prior Authorization Policy — Version 2 (Current)

## Purpose

This policy establishes criteria for prior authorization (PA) of specialty and
high-cost medications, effective January 1, 2025. This supersedes v1.

## Covered Under PA — Version 2

The following medication classes require prior authorization:

- All specialty medications
- Biologics (all)
- Any medication with a monthly cost exceeding $1,000
- GLP-1 agonists (new in v2)

Note: Statins (including atorvastatin at standard doses up to 80 mg) no longer
require prior authorization as of this version.

## Approval Criteria (v2)

1. Medical necessity documentation required.
2. Step therapy applies to biologics only (not standard generics).
3. Approval valid for 24 months (extended from v1).
4. Electronic submission required via the Provider Portal.

## Appeals

Members may appeal a PA denial within 60 days of the denial notice. Expedited
appeals are available within 72 hours for urgent clinical situations.
"""

MEMBER_SERVICES_FAQ = """\
---
source_id: member_services_faq
title: Member Services FAQ
authority_level: secondary
effective_date: "2026-01-01"
tenant_id: demo
---

# Member Services FAQ

## Coverage Questions

### Q: How do I check if my medication is covered?
Look up your drug on the Formulary (plan year 2026). Tiers 1–4 indicate copay
amounts. You can also call Member Services at 1-800-555-PLAN.

### Q: What is a deductible?
Your deductible is the amount you pay out of pocket before the plan begins
paying. The 2026 individual deductible is $500.

### Q: Are generic drugs always covered?
Most generic drugs are covered at Tier 1 or Tier 2. A small number of generics
may require prior authorization if they are high-cost specialty generics.

## Claims

### Q: How do I file a claim?
Submit claims through the online member portal, by mail to the address on your
ID card, or via the mobile app.

### Q: How long does claim processing take?
Standard claims are processed within 30 days. Urgent pre-service determinations
are made within 72 hours.

## Network

### Q: How do I find an in-network provider?
Use the Provider Directory on the member portal. Always confirm the provider's
current network status before an appointment, as networks may change.

### Q: What if I need emergency care out of network?
Emergency services are covered at in-network rates regardless of where care is
provided.
"""

COVERAGE_POLICY = """\
---
source_id: coverage_policy_2026
title: Medical Coverage Policy — Plan Year 2026
authority_level: primary
effective_date: "2026-01-01"
tenant_id: demo
---

# Medical Coverage Policy — Plan Year 2026

## Covered Services

The following services are covered under the HealthPlan Demo medical plan
subject to applicable cost sharing:

- Preventive care (annual physical, screenings) — $0 copay
- Primary care visits — $25 copay
- Specialist visits — $50 copay
- Urgent care — $40 copay
- Emergency room — $250 copay (waived if admitted)
- Inpatient hospitalization — $500 per admission after deductible
- Mental health / behavioral health — Same as medical (parity)
- Physical therapy — $35 copay, up to 30 visits per year
- Lab work (in-network) — $20 copay

## Excluded Services

The following are NOT covered under this plan:

- Cosmetic procedures (unless medically necessary)
- Experimental treatments not approved by FDA or CMS
- Long-term custodial care
- Vision correction surgery (LASIK)

Note: Dental services are covered under a separate dental plan, not this
medical plan. Questions about dental coverage should be directed to the dental
plan administrator.

## Out-of-Pocket Maximum

Individual: $7,500 per plan year.
Family: $15,000 per plan year.
"""


# ---------------------------------------------------------------------------
# (d) Member profiles with synthetic PII/PHI
# ---------------------------------------------------------------------------

MEMBER_PROFILES = [
    {
        "member_id": "MBR-100042",
        "first_name": "Alice",
        "last_name": "Thornton",
        "dob": "1978-03-14",
        "ssn": "123-45-6789",
        "address": "42 Maple Street, Springfield, IL 62701",
        "phone": "555-867-5309",
        "plan": "HealthPlan Demo PPO 2026",
        "diagnoses": ["E11.9 Type 2 diabetes", "I10 Essential hypertension"],
        "medications": ["Metformin 1000mg", "Lisinopril 10mg"],
    },
    {
        "member_id": "MBR-100087",
        "first_name": "Robert",
        "last_name": "Chen",
        "dob": "1965-07-22",
        "ssn": "987-65-4321",
        "address": "18 Oak Avenue, Portland, OR 97201",
        "phone": "555-234-5678",
        "plan": "HealthPlan Demo PPO 2026",
        "diagnoses": ["Z87.891 Personal history of nicotine dependence", "E78.5 Hyperlipidemia"],
        "medications": ["Atorvastatin 20mg"],
    },
    {
        "member_id": "MBR-100199",
        "first_name": "Maria",
        "last_name": "Vasquez",
        "dob": "1990-11-05",
        "ssn": "555-12-3456",
        "address": "7 Elm Court, Austin, TX 78701",
        "phone": "555-345-6789",
        "plan": "HealthPlan Demo HMO 2026",
        "diagnoses": ["F32.1 Major depressive disorder, moderate"],
        "medications": ["Sertraline 50mg"],
    },
]


# ---------------------------------------------------------------------------
# (e) SQLite records database
# ---------------------------------------------------------------------------

def _seed_sqlite(db_path: Path) -> None:
    """Create and populate the records database deterministically."""
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    # Drop and recreate for idempotency
    cur.executescript("""
        DROP TABLE IF EXISTS members;
        DROP TABLE IF EXISTS tickets;
        DROP TABLE IF EXISTS coverage_records;

        CREATE TABLE members (
            member_id   TEXT PRIMARY KEY,
            first_name  TEXT NOT NULL,
            last_name   TEXT NOT NULL,
            dob         TEXT NOT NULL,
            plan        TEXT NOT NULL
        );

        CREATE TABLE tickets (
            ticket_id   TEXT PRIMARY KEY,
            member_id   TEXT NOT NULL,
            type        TEXT NOT NULL,
            status      TEXT NOT NULL,
            description TEXT,
            created_at  TEXT NOT NULL
        );

        CREATE TABLE coverage_records (
            record_id   INTEGER PRIMARY KEY,
            member_id   TEXT NOT NULL,
            drug_name   TEXT NOT NULL,
            covered     INTEGER NOT NULL,
            tier        INTEGER,
            copay_usd   REAL,
            pa_required INTEGER NOT NULL DEFAULT 0
        );
    """)

    # Members (non-sensitive subset — full profiles are in markdown)
    for p in MEMBER_PROFILES:
        cur.execute(
            "INSERT INTO members VALUES (?, ?, ?, ?, ?)",
            (p["member_id"], p["first_name"], p["last_name"], p["dob"], p["plan"]),
        )

    # Tickets
    tickets = [
        ("TKT-2001", "MBR-100042", "coverage_inquiry", "open",
         "Member asking about atorvastatin copay under 2026 formulary.", "2026-05-10T09:15:00Z"),
        ("TKT-2002", "MBR-100087", "pa_request", "approved",
         "Prior authorization request for atorvastatin 80mg.", "2026-04-02T14:30:00Z"),
        ("TKT-2003", "MBR-100199", "claim_dispute", "pending",
         "Claim for sertraline denied; member disputes under mental health parity.", "2026-05-28T11:00:00Z"),
    ]
    cur.executemany("INSERT INTO tickets VALUES (?, ?, ?, ?, ?, ?)", tickets)

    # Coverage records
    coverage = [
        (1, "MBR-100042", "Atorvastatin 20mg", 1, 1, 10.00, 0),
        (2, "MBR-100087", "Atorvastatin 80mg", 1, 1, 10.00, 0),
        (3, "MBR-100199", "Sertraline 50mg", 1, 1, 10.00, 0),
        (4, "MBR-100042", "Wegovy (semaglutide)", 0, None, None, 1),  # not covered without PA
    ]
    cur.executemany("INSERT INTO coverage_records VALUES (?, ?, ?, ?, ?, ?, ?)", coverage)

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def seed() -> None:
    """Generate all synthetic data files under data/synthetic/."""
    SYNTHETIC_DIR.mkdir(parents=True, exist_ok=True)

    # Formulary docs (versioned conflict: a vs b)
    _write(SYNTHETIC_DIR / "formulary_2024.md", FORMULARY_2024)
    _write(SYNTHETIC_DIR / "formulary_2026.md", FORMULARY_2026)

    # Prior auth policy (superseded v1 + current v2)
    _write(SYNTHETIC_DIR / "policy_prior_auth_v1.md", PRIOR_AUTH_V1)
    _write(SYNTHETIC_DIR / "policy_prior_auth_v2.md", PRIOR_AUTH_V2)

    # FAQ + general coverage policy
    _write(SYNTHETIC_DIR / "member_services_faq.md", MEMBER_SERVICES_FAQ)
    _write(SYNTHETIC_DIR / "coverage_policy_2026.md", COVERAGE_POLICY)

    # Member profiles (contain PII/PHI — never commit real data)
    import json
    profiles_path = SYNTHETIC_DIR / "member_profiles.json"
    profiles_path.write_text(
        json.dumps(MEMBER_PROFILES, indent=2), encoding="utf-8"
    )

    # SQLite records
    db_path = SYNTHETIC_DIR / "records.sqlite"
    _seed_sqlite(db_path)

    print(f"Seeded {len(list(SYNTHETIC_DIR.iterdir()))} files under {SYNTHETIC_DIR}")
    for f in sorted(SYNTHETIC_DIR.iterdir()):
        print(f"  {f.name}")


if __name__ == "__main__":
    seed()
