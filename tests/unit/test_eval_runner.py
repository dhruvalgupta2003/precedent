import json

import pytest
import run as harness


def _raises(exc):
    def scorer(case):
        raise exc

    return scorer


@pytest.mark.parametrize("exc", [NotImplementedError, ImportError], ids=["not-implemented", "import-error"])
def test_a_case_whose_feature_is_not_built_is_pending_not_failed(exc):
    result = harness.run_case(_raises(exc), {"id": "P01", "expected": {"verdict": "WARN"}})
    assert result.status == "pending"


@pytest.mark.parametrize(("passed", "status"), [(True, "pass"), (False, "fail")])
def test_a_scorer_answer_becomes_pass_or_fail(passed, status):
    result = harness.run_case(lambda case: (passed, "WARN"), {"id": "P01", "expected": {"verdict": "WARN"}})
    assert (result.status, result.got) == (status, "WARN")


def test_a_suite_with_nothing_implemented_is_pending():
    results = [harness.CaseResult("a", "pending"), harness.CaseResult("b", "pending")]
    assert harness.gate("why", results) == ("PENDING", "0/2 implemented")


def test_pending_cases_do_not_count_against_the_pass_rate():
    results = [harness.CaseResult("a", "pass", {}, "x"), harness.CaseResult("b", "pending")]
    assert harness.gate("why", results)[0] == "PASS"


def test_a_single_false_block_fails_preflight_even_with_a_high_pass_rate():
    passes = [harness.CaseResult(f"p{i}", "pass", {"verdict": "WARN"}, "WARN") for i in range(10)]
    false_block = harness.CaseResult("n1", "fail", {"verdict": "CLEAR"}, "BLOCK")
    verdict, detail = harness.gate("preflight", [*passes, false_block])
    assert verdict == "FAIL"
    assert "1 false BLOCK" in detail
    assert "pass rate" not in detail  # 10/11 = 91% clears the pass-rate bar; the false BLOCK alone fails it


def test_a_low_pass_rate_fails_the_suite():
    results = [harness.CaseResult("a", "pass", {}, 1), harness.CaseResult("b", "fail", {}, 2)]
    assert harness.gate("safety", results)[0] == "FAIL"


def test_strict_mode_fails_while_anything_is_pending(tmp_path, monkeypatch):
    monkeypatch.setattr(harness, "RESULTS", tmp_path)
    assert harness.main(["safety"]) == 0
    assert harness.main(["safety", "--strict"]) == 1
    saved = json.loads((tmp_path / "safety.json").read_text())
    assert {c["status"] for c in saved["cases"]} == {"pending"}


@pytest.mark.parametrize("suite", list(harness.SCORERS))
def test_every_golden_case_has_a_unique_id_and_an_expected_answer(suite):
    cases = list(harness.load(suite))
    ids = [c["id"] for c in cases]
    assert cases, f"{suite} has no cases"
    assert len(ids) == len(set(ids))
    assert all("expected" in c for c in cases)
