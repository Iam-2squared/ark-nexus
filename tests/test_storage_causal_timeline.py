"""Additive diagnostic regressions; the original frozen gates remain untouched."""

from copy import deepcopy

import pytest
from test_data_forensics import minimal_case, watched_store

from nexus import data_forensics as forensic


@pytest.mark.parametrize("command,phase", [("COMMIT", "commit"), ("ROLLBACK", "rollback")])
def test_sql_transaction_boundaries_are_observed_without_rewriting_sql(tmp_path, command, phase):
    store, observer = watched_store(tmp_path)
    connection = observer.connect(store.path)
    connection.execute("BEGIN IMMEDIATE")
    connection.execute("INSERT INTO projects(id,name) VALUES('synthetic','Synthetic')")
    connection.execute(command)
    phases = [point["phase"] for point in observer.timeline]
    assert phase + "_before" in phases and phase + "_after" in phases
    connection.close()


@pytest.mark.parametrize("fails,phase", [(False, "commit"), (True, "rollback")])
def test_connection_context_boundaries_keep_builtin_transaction_semantics(tmp_path, fails, phase):
    store, observer = watched_store(tmp_path)
    connection = observer.connect(store.path)
    try:
        with connection:
            connection.execute("INSERT INTO projects(id,name) VALUES('synthetic','Synthetic')")
            if fails:
                raise RuntimeError("Synthetic failure")
    except RuntimeError:
        assert fails
    phases = [point["phase"] for point in observer.timeline]
    assert phase + "_before" in phases and phase + "_after" in phases
    assert connection.execute("SELECT count(*) FROM projects").fetchone()[0] == int(not fails)
    connection.close()


@pytest.mark.parametrize("sequences", [(0,), (2,), (1, 1), (1, 3)])
def test_timeline_sequence_reuse_and_gaps_fail_closed(sequences):
    report = minimal_case()
    first = report["timeline"][0]
    report["timeline"] = []
    for sequence in sequences:
        point = deepcopy(first)
        point["sequence"] = sequence
        report["timeline"].append(point)
    with pytest.raises(forensic.ForensicsProblem):
        forensic.validate_case(report)
