"""Child-only pytest boundaries and readonly SQLite headers, synthetic scope.

No fixture is replaced or finalized here. The unobserved mode has no boundary
file/SQL reads. Collection digests describe current public synthetic test names,
not the unknown historical failing collection or any provider export.
"""

import hashlib
import os

from nexus.private_storage import checked_database_path, database_identity

BOUNDARY_PHASES = frozenset({
    "test_setup_before", "test_setup_after", "fixture_setup_before", "fixture_setup_after",
    "test_call_before", "test_call_after", "test_teardown_before", "test_teardown_after",
    "fixture_teardown_after",
})
MAX_BOUNDARIES = 32


def header_summary(path, expected_identity):
    path = checked_database_path(path)
    if database_identity(path) != expected_identity:
        raise ValueError("Synthetic file identity changed")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        metadata = os.fstat(descriptor)
        if (metadata.st_dev, metadata.st_ino) != expected_identity[:2]:
            raise ValueError("Synthetic file identity changed")
        header = os.read(descriptor, 100)
    finally:
        os.close(descriptor)
    result = {"valid": len(header) == 100 and header[:16] == b"SQLite format 3\x00",
              "main_bytes": metadata.st_size, "page_size": None, "pages": None,
              "change_counter": None, "schema_cookie": None, "freelist": None}
    if result["valid"]:
        page_size = int.from_bytes(header[16:18], "big")
        result.update(page_size=65536 if page_size == 1 else page_size,
                      pages=int.from_bytes(header[28:32], "big"),
                      change_counter=int.from_bytes(header[24:28], "big"),
                      schema_cookie=int.from_bytes(header[40:44], "big"),
                      freelist=int.from_bytes(header[36:40], "big"))
    return result


def pytest_lifecycle(observer, frozen_node):
    import pytest

    class Lifecycle:
        def __init__(self):
            self.collection_count = 0
            self.frozen_test_index = None
            self.collection_digest = None
            self.events = []

        def pytest_collection_modifyitems(self, items):
            self.collection_count = len(items)
            positions = [i + 1 for i, item in enumerate(items) if item.nodeid == frozen_node]
            if len(positions) == 1:
                self.frozen_test_index = positions[0]
            digest = hashlib.sha256()
            for item in items:
                value = item.nodeid.encode("utf-8")
                digest.update(len(value).to_bytes(8, "big"))
                digest.update(value)
            self.collection_digest = digest.hexdigest()

        def boundary(self, phase):
            if not observer.enabled:
                return
            if len(self.events) >= MAX_BOUNDARIES:
                observer.capped = True
                return
            event = {"sequence": len(self.events) + 1, "phase": phase,
                     "status": "not_bound", "snapshot_sequence": None,
                     "database_present": None, "identity_same": None,
                     "main_header": None, "commit_boundary_sequence": observer.commit_boundaries}
            if observer.path is not None:
                try:
                    checked_database_path(observer.path)
                    event["database_present"] = observer.path.is_file()
                    event["status"] = "not_created"
                except (OSError, ValueError):
                    observer.observation_errors += 1
                    event["status"] = "unavailable"
                if event["database_present"]:
                    before = len(observer.timeline)
                    observer.reopened(phase, 0)
                    try:
                        if len(observer.timeline) != before + 1:
                            raise ValueError("Synthetic snapshot unavailable")
                        event.update(snapshot_sequence=observer.timeline[-1]["sequence"],
                                     identity_same=observer.timeline[-1]["file_identity_same"],
                                     main_header=header_summary(observer.path, observer.identity),
                                     status="captured")
                    except (OSError, ValueError):
                        observer.observation_errors += 1
                        event["status"] = "unavailable"
            self.events.append(event)

        @pytest.hookimpl(hookwrapper=True)
        def pytest_fixture_setup(self, fixturedef, request):
            watched = fixturedef.argname == "client" and request.node.nodeid == frozen_node
            if watched:
                self.boundary("fixture_setup_before")
            yield
            if watched:
                self.boundary("fixture_setup_after")

        def pytest_fixture_post_finalizer(self, fixturedef, request):
            if fixturedef.argname == "client" and request.node.nodeid == frozen_node:
                self.boundary("fixture_teardown_after")

        @pytest.hookimpl(hookwrapper=True)
        def pytest_runtest_setup(self, item):
            if item.nodeid == frozen_node:
                self.boundary("test_setup_before")
            yield
            if item.nodeid == frozen_node:
                self.boundary("test_setup_after")

        @pytest.hookimpl(hookwrapper=True)
        def pytest_runtest_call(self, item):
            if item.nodeid == frozen_node:
                self.boundary("test_call_before")
            yield
            if item.nodeid == frozen_node:
                self.boundary("test_call_after")

        @pytest.hookimpl(hookwrapper=True)
        def pytest_runtest_teardown(self, item, nextitem):
            if item.nodeid == frozen_node:
                self.boundary("test_teardown_before")
            yield
            if item.nodeid == frozen_node:
                self.boundary("test_teardown_after")

        def report(self):
            return {"collection_count": self.collection_count,
                    "frozen_test_index": self.frozen_test_index,
                    "collection_sha256": self.collection_digest,
                    "collection_origin": "current_synthetic_pytest",
                    "historical_order_reconstructed": False,
                    "boundary_observer_enabled": observer.enabled, "events": self.events}

    return Lifecycle()


def validate_lifecycle(value, timeline, require):
    from nexus.data_forensics import _integer

    require(type(value) is dict and set(value) == {
        "collection_count", "frozen_test_index", "collection_sha256", "collection_origin",
        "historical_order_reconstructed", "boundary_observer_enabled", "events"})
    require(_integer(value["collection_count"], 100_000)
            and (value["frozen_test_index"] is None or type(value["frozen_test_index"]) is int
                 and 1 <= value["frozen_test_index"] <= value["collection_count"])
            and value["collection_origin"] == "current_synthetic_pytest"
            and value["historical_order_reconstructed"] is False
            and type(value["boundary_observer_enabled"]) is bool)
    digest = value["collection_sha256"]
    require(digest is None or type(digest) is str and len(digest) == 64
            and all(char in "0123456789abcdef" for char in digest))
    events = value["events"]
    require(type(events) is list and len(events) <= MAX_BOUNDARIES)
    if not value["boundary_observer_enabled"]:
        require(not events)
    for index, event in enumerate(events):
        require(type(event) is dict and set(event) == {
            "sequence", "phase", "status", "snapshot_sequence", "database_present",
            "identity_same", "main_header", "commit_boundary_sequence"})
        require(type(event["sequence"]) is int and event["sequence"] == index + 1
                and type(event["phase"]) is str and event["phase"] in BOUNDARY_PHASES
                and type(event["status"]) is str
                and event["status"] in {"captured", "not_bound", "not_created", "unavailable"}
                and (event["database_present"] is None or type(event["database_present"]) is bool)
                and (event["identity_same"] is None or type(event["identity_same"]) is bool)
                and _integer(event["commit_boundary_sequence"]))
        sequence = event["snapshot_sequence"]
        require(sequence is None or type(sequence) is int and 1 <= sequence <= len(timeline))
        if event["status"] == "captured":
            require(event["database_present"] and sequence is not None
                    and timeline[sequence - 1]["phase"] == event["phase"]
                    and timeline[sequence - 1]["readonly_observer"] is True
                    and event["identity_same"] is timeline[sequence - 1]["file_identity_same"])
            header = event["main_header"]
            require(type(header) is dict and set(header) == {
                "valid", "main_bytes", "page_size", "pages", "change_counter", "schema_cookie", "freelist"})
            require(type(header["valid"]) is bool and _integer(header["main_bytes"]))
            for field in ("page_size", "pages", "change_counter", "schema_cookie", "freelist"):
                require(_integer(header[field], 2**32) if header["valid"] else header[field] is None)
            if header["valid"]:
                require(512 <= header["page_size"] <= 65536
                        and header["page_size"] & (header["page_size"] - 1) == 0)
        else:
            require(event["main_header"] is None)
