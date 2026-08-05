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


# --- corrupt persisted state (Qodo review, PR #44) ------------------------


def test_truncated_json_reads_as_none_not_an_exception(tmp_path):
    """A process killed mid-write leaves a partial file. Reading it must not raise
    into the progress UI or break resumability."""
    from desk.research import read_json

    partial = tmp_path / "half.json"
    partial.write_text('{"lane_key": "8507.60.00|Vietnam|United',      # truncated
                       encoding="utf-8")
    assert read_json(partial) is None

    missing = tmp_path / "nope.json"
    assert read_json(missing) is None

    good = tmp_path / "ok.json"
    good.write_text('{"status": "running"}', encoding="utf-8")
    assert read_json(good) == {"status": "running"}


def test_read_json_rejects_valid_json_that_is_not_an_object(tmp_path):
    """`[1, 2]` and `"text"` parse cleanly and then break the first .get() call,
    which is a worse failure than not parsing at all."""
    from desk.io import read_json

    for payload in ("[1, 2]", '"just a string"', "42", "true", "null"):
        f = tmp_path / "x.json"
        f.write_text(payload, encoding="utf-8")
        assert read_json(f) is None, f"{payload} is not a usable record"


def test_corrupt_job_file_is_skipped_by_open_jobs(tmp_path, monkeypatch):
    from desk import research

    monkeypatch.setattr(research, "JOBS_DIR", tmp_path)
    (tmp_path / "bad.json").write_text("{oh no", encoding="utf-8")
    (tmp_path / "good.json").write_text('{"lane_key": "x|y|z", "kind": "overlay"}', encoding="utf-8")
    jobs = research.open_jobs()
    assert len(jobs) == 1 and jobs[0]["lane_key"] == "x|y|z"


def test_corrupt_lookup_cache_is_skipped(tmp_path, monkeypatch):
    from desk import classify

    monkeypatch.setattr(classify, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(classify, "SAMPLE_DIR", tmp_path / "absent")
    (tmp_path / f"{classify.slugify('widgets')}.json").write_text("not json at all", encoding="utf-8")
    assert classify.cached("widgets") is None


# --- change detection and env parsing (Qodo review, PR #44) ---------------


def test_diff_distinguishes_false_from_missing():
    """`str(x or "")` collapsed False, 0 and None into the same thing, hiding a real
    change. verified_against_official_schedule is explicitly allowed to be false."""
    from desk.delta import diff_content

    changes = diff_content("rate",
                           {"verified_against_official_schedule": None},
                           {"verified_against_official_schedule": False})
    assert changes, "None -> False is a real change and must be reported"

    unchanged = diff_content("rate",
                             {"verified_against_official_schedule": False},
                             {"verified_against_official_schedule": False})
    assert not unchanged


def test_diff_reports_a_rate_becoming_unverified():
    from desk.delta import diff_content

    changes = diff_content("rate",
                           {"general_rate": "3.4%", "verified_against_official_schedule": True},
                           {"general_rate": "not verified", "verified_against_official_schedule": False})
    fields = {c["field"] for c in changes}
    assert "general_rate" in fields
    assert "verified_against_official_schedule" in fields


def test_bad_env_int_falls_back_instead_of_raising(monkeypatch):
    """A typo in .env should not crash model setup from deep inside LlamaIndex."""
    from desk.models import _int_env

    monkeypatch.setenv("DESK_TEST_INT", "not a number")
    assert _int_env("DESK_TEST_INT", 2048) == 2048
    monkeypatch.setenv("DESK_TEST_INT", "")
    assert _int_env("DESK_TEST_INT", 2048) == 2048
    monkeypatch.setenv("DESK_TEST_INT", "512")
    assert _int_env("DESK_TEST_INT", 2048) == 512
    monkeypatch.delenv("DESK_TEST_INT")
    assert _int_env("DESK_TEST_INT", 2048) == 2048


# --- cached-failure regression (Qodo review, PR #44) ----------------------


def test_cached_loader_does_not_catch_configuration_errors():
    """The cached loader must contain no except clause; the wrapper must have one.

    Catching inside `@st.cache_resource` stored None as the cached resource, so a
    reader who corrected their .env kept seeing the same error until restarting.
    Streamlit does not cache exceptions, so propagating is what makes retry work.

    Checked by reading the source rather than importing app.py: importing it runs
    module-level Streamlit and dotenv calls, and reaching through `__wrapped__` to
    bypass the cache depends on a private attribute that may change.
    """
    import ast

    tree = ast.parse((HERE / "app.py").read_text(encoding="utf-8"))
    funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}

    loader = funcs["_load_index"]
    assert any("cache_resource" in ast.unparse(d) for d in loader.decorator_list), \
        "_load_index is the cached one"
    assert not [n for n in ast.walk(loader) if isinstance(n, ast.ExceptHandler)], \
        "the cached loader must propagate, not swallow: catching here caches None"

    wrapper = funcs["_index"]
    assert not wrapper.decorator_list, "the wrapper must not be cached"
    assert [n for n in ast.walk(wrapper) if isinstance(n, ast.ExceptHandler)], \
        "the wrapper is what turns the error into a message for the reader"


# --- the shared reader (Qodo review, PR #44) ------------------------------


def test_read_json_survives_every_way_a_file_can_be_unreadable(tmp_path):
    """Truncated, absent, and not-a-file all return None rather than raising.

    OSError was the gap: `ingest.load_records` caught only JSONDecodeError, so an
    unreadable path took the page down while a corrupt one did not.
    """
    from desk.io import read_json

    truncated = tmp_path / "half.json"
    truncated.write_text('{"lane_key": "8507.60.00|Vietnam|Unit', encoding="utf-8")
    assert read_json(truncated) is None

    assert read_json(tmp_path / "absent.json") is None

    a_directory = tmp_path / "dir.json"
    a_directory.mkdir()
    assert read_json(a_directory) is None, "IsADirectoryError is an OSError"

    good = tmp_path / "ok.json"
    good.write_text('{"status": "running"}', encoding="utf-8")
    assert read_json(good) == {"status": "running"}


def test_load_records_skips_an_unreadable_path(tmp_path):
    """The OSError case, through the real loader."""
    (tmp_path / "notafile.json").mkdir()
    (tmp_path / "good.json").write_text(
        '{"kind": "rate", "doc_key": "x|US", "researched_at": "2026-08-05T00:00:00+00:00"}',
        encoding="utf-8")
    records = ingest.load_records(tmp_path)
    assert len(records) == 1 and records[0]["doc_key"] == "x|US"


def test_change_log_reader_skips_bad_lines_and_bounds_the_read(tmp_path):
    from desk.io import TAIL_BYTES, read_json_lines

    log = tmp_path / "changes.jsonl"
    assert read_json_lines(log) == [], "a missing log is empty, not an error"

    lines = [f'{{"at": "2026-08-0{i % 9 + 1}", "n": {i}}}' for i in range(40)]
    lines.insert(7, "{ this is not json")
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    entries = read_json_lines(log)
    assert len(entries) == 40, "the unparseable line is skipped, the rest survive"

    # A log far bigger than the tail window is read only in part.
    big = tmp_path / "big.jsonl"
    big.write_text("".join('{"at": "2026-08-05", "pad": "%s"}\n' % ("x" * 500)
                           for _ in range(2000)), encoding="utf-8")
    assert big.stat().st_size > TAIL_BYTES
    tail = read_json_lines(big, limit=6)
    assert 0 < len(tail) <= 24, "bounded, and enough to fill a limit of 6"


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
