"""Everything testable without an embedding model or a billable run.

Runs against the real pre-warmed corpus in data/runs/, so these are not toy
fixtures — a regression in the trust mapping shows up here.

    ./.venv/bin/python -m pytest tests/ -q
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

HERE = Path(__file__).parent.parent
sys.path.insert(0, str(HERE))

from desk import freshness, ingest  # noqa: E402
from desk.agents_config import TTL_DAYS  # noqa: E402
from desk.research import Lane  # noqa: E402

NOW = datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def records():
    """Every record that could ship, from BOTH corpus directories.

    Not `load_records()`: that follows `active_dir()`, which depends on `USE_LIVE`,
    which the tests never set — so the suite quietly validated `data/samples/` while
    the app served `data/runs/`. An unverified rate record sat in runs/ and the suite
    passed. Validate whatever exists, wherever it exists.
    """
    seen, recs = set(), []
    for directory in (ingest.RUNS_DIR, ingest.SAMPLES_DIR):
        for record in ingest.load_records(directory):
            key = (record.get("doc_key") or record.get("lane_key"), record.get("kind"))
            if key in seen:      # same fact in both dirs; runs wins, it is read first
                continue
            seen.add(key)
            recs.append(record)
    if not recs:
        pytest.skip("no corpus on disk — run prewarm.py first")
    return recs


# --- keying ---------------------------------------------------------------


def test_rate_key_is_origin_free():
    """The MFN rate belongs to the code, not the lane (corpus-verified)."""
    vn = Lane("8507.60.00", "Vietnam")
    cn = Lane("8507.60.00", "China")
    assert vn.doc_id("rate") == cn.doc_id("rate")
    assert vn.doc_id("overlay") != cn.doc_id("overlay")


def test_overlay_key_includes_origin():
    lane = Lane("8507.60.00", "Vietnam")
    assert lane.doc_id("overlay") == "8507.60.00|Vietnam|United States#overlay"
    assert lane.doc_id("rate") == "8507.60.00|United States#rate"


# --- freshness ------------------------------------------------------------


def test_ttls_differ_by_fact_class():
    """The whole reason there are two agents."""
    assert TTL_DAYS["rate"] > TTL_DAYS["overlay"]


def test_overlay_goes_stale_before_rate():
    stamp = (NOW - timedelta(days=30)).isoformat()
    assert freshness.is_stale(stamp, "overlay", now=NOW) is True
    assert freshness.is_stale(stamp, "rate", now=NOW) is False


def test_missing_timestamp_is_stale():
    """Absence of proof is not freshness."""
    assert freshness.is_stale(None, "rate", now=NOW) is True
    assert freshness.is_stale("not-a-date", "rate", now=NOW) is True


def test_unknown_kind_gets_strictest_ttl():
    assert freshness.ttl_for("nonsense") == min(TTL_DAYS.values())


def test_naive_timestamp_treated_as_utc():
    naive = (NOW - timedelta(days=1)).replace(tzinfo=None).isoformat()
    assert freshness.age_in_days(naive, now=NOW) == pytest.approx(1.0, abs=0.01)


def test_boundary_is_stale_at_exactly_ttl():
    stamp = (NOW - timedelta(days=TTL_DAYS["overlay"])).isoformat()
    assert freshness.is_stale(stamp, "overlay", now=NOW) is True


def test_verdict_describes_staleness_in_words():
    stamp = (NOW - timedelta(days=40)).isoformat()
    verdict = freshness.assess({"kind": "overlay", "researched_at": stamp}, now=NOW)
    assert "STALE" in verdict.describe()
    assert str(TTL_DAYS["overlay"]) in verdict.describe()


# --- trust mapping over the real corpus -----------------------------------


def test_every_record_parses_as_structured_json(records):
    for record in records:
        assert ingest.parsed_content(record) is not None, record.get("doc_key")


def test_claims_are_keyed_by_json_path(records):
    """Per-cell citation depends on this. Without output_schema it would not hold."""
    for record in records:
        paths = ingest.claim_index(record["metadata"])
        assert paths, f"no path-keyed claims in {record.get('doc_key')}"
        assert all(p.startswith("$") for p in paths)


def test_echoed_input_fields_are_separated_from_research(records):
    """`pre_existing` zero-citation claims are echoes of input_data, not facts."""
    rate = [r for r in records if r["kind"] == "rate"]
    assert rate, "expected rate records in the corpus"
    for record in rate:
        researched, echoes = ingest.split_claims(record["metadata"])
        assert researched, "a rate record with no researched claims is a bug"
        for claim in echoes:
            assert not claim.get("citations")
            assert (claim.get("confidence") or "").lower() == "pre_existing"


def test_every_source_in_the_corpus_is_primary(records):
    """Consequence of sources.allow being a hard whitelist (smoke 3)."""
    for record in records:
        sources = record["metadata"].get("sources") or []
        assert sources, f"no sources for {record.get('doc_key')}"
        assert ingest.primary_source_count(record["metadata"]) == len(sources)


def test_rate_records_verified_against_official_schedule(records):
    for record in [r for r in records if r["kind"] == "rate"]:
        content = ingest.parsed_content(record)
        assert content.get("verified_against_official_schedule") is True
        assert content.get("general_rate")
        assert "not verified" not in str(content["general_rate"]).lower()


def test_overlay_records_never_report_a_base_rate(records):
    """Overlay and base rate must not bleed into each other."""
    for record in [r for r in records if r["kind"] == "overlay"]:
        content = ingest.parsed_content(record)
        assert "general_rate" not in content


# --- duty filter: schema validation only, no text heuristics ---------------
#
# An earlier version of this suite had ~15 tests for regex guards that inferred
# meaning from prose. The guards produced false positives and were removed; these
# two checks read fields the agent explicitly set.


def test_duty_marked_not_in_force_is_excluded():
    content = {"additional_duties": [
        {"authority": "EO 14257", "rate": "20%", "in_force": False},
    ]}
    in_force, excluded = ingest.split_duties(content, as_of=NOW.isoformat())
    assert in_force == []
    assert "not in force" in excluded[0]["excluded_because"]


def test_duty_whose_window_closed_is_excluded():
    """A Section 122-style surcharge that ended before the research date."""
    content = {"additional_duties": [
        {"authority": "Proclamation 11012", "rate": "10%", "in_force": True,
         "effective_date": "2026-02-24", "ends": "2026-07-24"},
    ]}
    in_force, excluded = ingest.split_duties(content, as_of=NOW.isoformat())
    assert in_force == []
    assert "window closed" in excluded[0]["excluded_because"]


def test_open_ended_duty_in_force_survives():
    content = {"additional_duties": [
        {"authority": "Section 301 List 3", "rate": "25%", "in_force": True,
         "effective_date": "2024-01-01", "ends": None},
    ]}
    in_force, excluded = ingest.split_duties(content, as_of=NOW.isoformat())
    assert len(in_force) == 1 and excluded == []


def test_empty_duties_is_a_valid_answer():
    assert ingest.split_duties({"additional_duties": []}) == ([], [])
    assert ingest.split_duties(None) == ([], [])


def test_unverified_gaps_are_carried_to_node_metadata(records):
    """The actual lesson: `confidence` does not account for coverage gaps."""
    for record in records:
        content = ingest.parsed_content(record) or {}
        meta = ingest.node_metadata(record)
        assert meta["unverified"] == (content.get("unverified") or [])


def test_duty_counts_add_up(records):
    for record in [r for r in records if r["kind"] == "overlay"]:
        content = ingest.parsed_content(record)
        meta = ingest.node_metadata(record)
        total = len(content.get("additional_duties") or [])
        assert meta["duties_in_force"] + meta["duties_excluded"] == total


# --- question normalization edge cases ------------------------------------


def test_code_without_origin_asks_for_the_country():
    """The crash Tom hit: the 'Use this' button prefills a code with no country, and
    a question with a code but no origin produced no Lane and no flag."""
    from desk.normalize import heuristic

    for question in ("What's the duty on HTS 6404.11.00 from ",
                     "What's the duty on HTS 6404.11.00 from <country>?",
                     "What's the duty on HTS 6404.11.00?"):
        out = heuristic(question)
        assert out.lane is None
        assert out.needs_origin is True, question
        assert out.needs_hts_code is False, "the code was present"


def test_code_with_origin_produces_a_lane():
    from desk.normalize import heuristic

    out = heuristic("What's the duty on HTS 6404.11.00 from Vietnam?")
    assert out.lane is not None
    assert out.needs_origin is False and out.needs_hts_code is False
    assert out.lane.key == "6404.11.00|Vietnam|United States"


def test_neither_code_nor_origin_flags_both():
    from desk.normalize import heuristic

    out = heuristic("What's the duty on running shoes?")
    assert out.lane is None
    assert out.needs_hts_code is True and out.needs_origin is True


# --- documents ------------------------------------------------------------


def test_documents_get_stable_ids_and_dated_text(records):
    docs = ingest.to_documents(records)
    ids = [d.doc_id for d in docs]
    assert len(ids) == len(set(ids)), "duplicate doc_ids would break refresh upsert"
    for doc in docs:
        # The agent only sees text; the date must survive there too.
        assert "Researched:" in doc.text
        assert doc.metadata["researched_at"]
        assert doc.metadata["kind"] in {"rate", "overlay"}


def test_document_ids_are_stable_across_reingest(records):
    first = {d.doc_id for d in ingest.to_documents(records)}
    second = {d.doc_id for d in ingest.to_documents(records)}
    assert first == second


def test_coverage_counts_lanes_by_overlay_not_rate(records):
    cov = ingest.coverage(records)
    assert cov["overlay_docs"] == len(cov["lanes"])
    assert cov["rate_docs"] == len(cov["hts_codes"])


# --- postprocessor --------------------------------------------------------


def _node(kind: str, age_days: float):
    from llama_index.core.schema import NodeWithScore, TextNode

    stamp = (NOW - timedelta(days=age_days)).isoformat()
    return NodeWithScore(
        node=TextNode(text="x", metadata={"kind": kind, "researched_at": stamp,
                                         "doc_key": f"{kind}-{age_days}d"}),
        score=1.0,
    )


def test_strict_postprocessor_withholds_stale_nodes():
    nodes = [_node("overlay", 1), _node("overlay", 40), _node("rate", 40)]
    kept = freshness.FreshnessPostprocessor(strict=True, now=NOW).postprocess_nodes(nodes)
    keys = {n.node.metadata["doc_key"] for n in kept}
    assert keys == {"overlay-1d", "rate-40d"}


def test_lenient_postprocessor_keeps_but_marks_stale():
    nodes = [_node("overlay", 40)]
    kept = freshness.FreshnessPostprocessor(strict=False, now=NOW).postprocess_nodes(nodes)
    assert len(kept) == 1
    assert kept[0].node.metadata[freshness.STALE_KEY] is True
    assert kept[0].node.metadata[freshness.AGE_KEY] == pytest.approx(40, abs=0.1)


def test_preamble_forces_dates_and_flags_echoes():
    text = freshness.freshness_preamble([_node("overlay", 40), _node("rate", 2)], now=NOW)
    assert "STALE" in text
    assert "research date" in text
    assert "pre_existing" in text


def test_preamble_empty_without_nodes():
    assert freshness.freshness_preamble([]) == ""
