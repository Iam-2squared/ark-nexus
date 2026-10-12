"""Tiny additive benchmark tests; the opt-in 50k measurement is not a CI speed gate."""

import json
import sqlite3
import sys
import tracemalloc

import pytest

from nexus import synthetic_benchmark as benchmark


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    checkout = tmp_path / "synthetic-checkout"
    checkout.mkdir(mode=0o700)
    (checkout / "tmp").mkdir(mode=0o700)
    monkeypatch.setattr(benchmark, "_CHECKOUT_ROOT", checkout)
    return checkout


def test_small_stages_verify_counts_provenance_and_summary_only(workspace):
    root = workspace / "tmp" / "new-synthetic-benchmark"
    report = benchmark.run_benchmark(root, (3, 251))
    saved = json.loads((root / "report.json").read_text(encoding="utf-8"))
    assert saved == report
    assert report["coverage"] == "synthetic_only"
    assert report["performance_targets"] is None
    assert report["conditions"]["full_process_rss_measured"] is False
    assert report["conditions"]["external_ai_connections"] == 0
    assert report["conditions"]["paid_api_calls"] == 0
    assert report["conditions"]["logical_cpu_count"] is not None
    for stage, count in zip(report["stages"], (3, 251), strict=True):
        assert stage["messages"] == count
        assert stage["conversations"] == (count + 249) // 250
        assert stage["sqlite_temp_store"] == 2
        assert stage["checks"]["messages_inserted"] == count
        assert stage["checks"]["reimport_inserted"] == 0
        assert stage["checks"]["reimport_duplicates"] == count
        assert stage["checks"]["backup_records_equal"] is True
        assert stage["checks"]["backup_counts_equal"] is True
        assert stage["checks"]["search_totals"] == {
            "unicode_all_matches": count, "unique_term": 1, "literal_percent": count,
        }
        assert stage["tracked_python_peak_bytes"] > 0
        assert stage["seconds"]["import"] >= 0
        assert stage["seconds"]["reimport"] >= 0
        assert stage["seconds"]["integrity"] >= 0
    raw = (root / "report.json").read_text(encoding="utf-8")
    for forbidden in (str(workspace), "nexus.sqlite3", "account_alias", "source_id",
                      "synthetic-benchmark-m", "token000", "content", "import_hash", "key"):
        assert forbidden not in raw
    assert tracemalloc.is_tracing() is False


def test_existing_root_is_refused_and_never_modified(workspace):
    root = workspace / "tmp" / "existing"
    root.mkdir(mode=0o700)
    sentinel = root / "sentinel"
    sentinel.write_bytes(b"synthetic sentinel")
    with pytest.raises(benchmark.BenchmarkProblem, match="already exists"):
        benchmark.run_benchmark(root, (5,))
    assert sentinel.read_bytes() == b"synthetic sentinel"
    assert list(root.iterdir()) == [sentinel]


@pytest.mark.parametrize("relative", ["outside/new", "tmp", "new", "tmp/../../escape"])
def test_scope_escape_is_rejected_before_writing(workspace, relative):
    destination = workspace / relative
    with pytest.raises(ValueError):
        benchmark.run_benchmark(destination, (5,))
    assert not (destination / "report.json").exists()
    assert not (destination / "stage-5").exists()


@pytest.mark.parametrize("stages", [(), (0,), (-1,), (50_001,), (10, 10), (True,),
                                   ("10",), tuple(range(1, 8)), ([10],)])
def test_invalid_stages_do_not_create_a_directory(workspace, stages):
    root = workspace / "tmp" / "invalid"
    with pytest.raises(benchmark.BenchmarkProblem, match="Invalid"):
        benchmark.run_benchmark(root, stages)
    assert not root.exists()


def test_symlink_ancestor_cannot_escape_benchmark_scope(workspace, tmp_path):
    target = tmp_path / "synthetic-sentinel-target"
    target.mkdir(mode=0o700)
    sentinel = target / "sentinel"
    sentinel.write_bytes(b"synthetic sentinel")
    link = workspace / "tmp" / "linked"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("Creating symlinks requires Windows Developer Mode or permissions")
    with pytest.raises(ValueError, match="symlink"):
        benchmark.run_benchmark(link / "new", (5,))
    assert list(target.iterdir()) == [sentinel]
    assert sentinel.read_bytes() == b"synthetic sentinel"


def test_existing_memory_tracker_is_preserved_and_refused(workspace):
    tracemalloc.start()
    try:
        with pytest.raises(benchmark.BenchmarkProblem, match="separate"):
            benchmark.run_benchmark(workspace / "tmp" / "new", (5,))
        assert tracemalloc.is_tracing() is True
        assert not (workspace / "tmp" / "new").exists()
    finally:
        tracemalloc.stop()


def test_interruption_leaves_no_success_report_and_restores_tracker(workspace, monkeypatch):
    def interrupted(_store):
        raise KeyboardInterrupt("SYNTHETIC-PRIVATE-INPUT-MARKER")

    monkeypatch.setattr(benchmark.Store, "integrity_report", interrupted)
    root = workspace / "tmp" / "interrupted"
    with pytest.raises(KeyboardInterrupt):
        benchmark.run_benchmark(root, (5,))
    assert not (root / "report.json").exists()
    assert tracemalloc.is_tracing() is False


@pytest.mark.parametrize("failure", [OSError, sqlite3.OperationalError, KeyboardInterrupt])
def test_cli_runtime_diagnostics_never_echo_paths_input_or_tracebacks(
    workspace, monkeypatch, capsys, failure,
):
    marker = "SYNTHETIC-PRIVATE-INPUT-MARKER"

    def failed(*_args, **_kwargs):
        raise failure(marker + str(workspace))

    monkeypatch.setattr(benchmark, "run_benchmark", failed)
    monkeypatch.setattr(sys, "argv", ["synthetic_benchmark", "--root",
                                    str(workspace / "tmp" / marker), "--stages", "5"])
    with pytest.raises(SystemExit) as stopped:
        benchmark.main()
    assert stopped.value.code == 1
    captured = capsys.readouterr()
    assert marker not in captured.out + captured.err
    assert str(workspace) not in captured.out + captured.err
    assert "Traceback" not in captured.out + captured.err
    assert "No existing data was overwritten" in captured.err


def test_cli_argument_errors_do_not_echo_private_values(workspace, monkeypatch, capsys):
    marker = "SYNTHETIC-PRIVATE-INVALID-ARGUMENT"
    monkeypatch.setattr(sys, "argv", ["synthetic_benchmark", "--root",
                                    str(workspace / "tmp" / marker), "--stages", marker])
    with pytest.raises(SystemExit) as stopped:
        benchmark.main()
    assert stopped.value.code == 2
    captured = capsys.readouterr()
    assert marker not in captured.out + captured.err
    assert str(workspace) not in captured.out + captured.err


def test_default_cli_stages_are_opt_in_1000_10000_50000(workspace, monkeypatch, capsys):
    observed = {}

    def capture(root, stages):
        observed.update(root=root, stages=tuple(stages))

    monkeypatch.setattr(benchmark, "run_benchmark", capture)
    monkeypatch.setattr(sys, "argv", ["synthetic_benchmark"])
    benchmark.main()
    assert observed["stages"] == (1_000, 10_000, 50_000)
    assert observed["root"].parent == workspace / "tmp" / "synthetic-benchmark"
    assert len(observed["root"].name) == 32
    assert "checks passed" in capsys.readouterr().out
