"""Strict count/classification allowlist before child evidence reaches CI stdout."""

from nexus.sqlite_workload import MAX_DATABASE_BYTES, TABLES, require

UNAVAILABLE = {
    "status": "NOT RUN", "captured": False, "reason": "capability_unavailable",
    "native_registration_count": 0, "alternate_sqlite_loaded": False,
    "default_vfs_changed": False, "private_import_allowed": False,
}
_KINDS = {"main_db", "temp_db", "transient_db", "main_journal", "temp_journal",
          "statement_journal", "super_journal", "wal", "other", "all"}
_OPERATIONS = {"open", "named_open", "unnamed_open", "readonly_open", "readwrite_open",
               "write_calls", "write_bytes", "close", "delete"}


def _object(value, fields):
    require(type(value) is dict and set(value) == set(fields))


def _count(value):
    require(type(value) is int and 0 <= value <= 2 ** 40)


def _true_fields(value, fields):
    require(all(value[name] is True for name in fields))


def _false_fields(value, fields):
    require(all(value[name] is False for name in fields))


def statement_journal_gates(counts, *, file_control_supported):
    """Qualification needs a writing FILE control for the same journal mode.

    Generic VFS capture can succeed even when a small workload never spills a
    subjournal. A FILE/WAL control is not a positive control for DELETE mode.
    These bounded gates never qualify physical storage or private imports.
    """
    require(type(counts) is dict and type(file_control_supported) is bool)
    gates = {}
    for mode in ("delete", "wal"):
        gate = {"storage_location_qualified": False, "private_import_allowed": False}
        for configuration, prefix in (("file_control", "file_control_" + mode),
                                      ("memory", mode)):
            for field, operation in (("open_count", "open"), ("write_calls", "write_calls"),
                                     ("write_bytes", "write_bytes")):
                count = counts.get(prefix + ".statement_journal." + operation, 0)
                _count(count)
                gate[configuration + "_" + field] = count
        positive = file_control_supported and all(gate[name] > 0 for name in (
            "file_control_open_count", "file_control_write_calls", "file_control_write_bytes",
        ))
        gate["positive_control_observed"] = positive
        if any(gate[name] > 0 for name in (
            "memory_open_count", "memory_write_calls", "memory_write_bytes",
        )):
            gate.update(status="BLOCKED", reason="memory_subjournal_observed")
        elif not file_control_supported:
            gate.update(status="NOT RUN", reason="compiled_memory_only")
        elif not positive:
            gate.update(status="NOT RUN", reason="positive_control_not_observed")
        else:
            gate.update(status="synthetic_PASS",
                        reason="positive_control_observed_memory_subjournal_absent")
        gates[mode] = gate
    return gates


def _workload(value, rows, temp, *, positive=False):
    fields = {"status", "workloads", "storage_location_qualified", "private_import_allowed"}
    if positive:
        fields |= {"production_configuration", "statement_journal_open_count"}
    _object(value, fields)
    require(value["status"] == "synthetic_PASS")
    _false_fields(value, ("storage_location_qualified", "private_import_allowed"))
    if positive:
        _false_fields(value, ("production_configuration",))
        _count(value["statement_journal_open_count"])
    require(type(value["workloads"]) is list and len(value["workloads"]) == 2)
    for part, mode in zip(value["workloads"], ("delete", "wal"), strict=True):
        _object(part, {"rows", "journal_mode", "cache_pages", "page_size", "max_database_bytes",
                       "temp_store", "cases", "interrupted_transaction_rollback", "temp_sort_rows",
                       "native_capture_claimed", "backup_restore_logical_equal",
                       "restored_fts_query_equal"})
        for name in ("rows", "cache_pages", "page_size", "max_database_bytes", "temp_store",
                     "temp_sort_rows"):
            _count(part[name])
        require(part["rows"] == rows and part["journal_mode"] == mode
                and part["cache_pages"] == 16 and part["temp_store"] == temp
                and part["temp_sort_rows"] == rows and part["max_database_bytes"] == MAX_DATABASE_BYTES
                and 512 <= part["page_size"] <= 65536
                and part["page_size"] & (part["page_size"] - 1) == 0)
        _true_fields(part, ("interrupted_transaction_rollback", "backup_restore_logical_equal",
                            "restored_fts_query_equal"))
        _false_fields(part, ("native_capture_claimed",))
        require(type(part["cases"]) is list and len(part["cases"]) == 3)
        names = ("late_unique_insert", "late_check_update", "late_trigger_fts_update")
        for case, name in zip(part["cases"], names, strict=True):
            _object(case, {"case", "partial_row_callbacks", "statement_rollback",
                           "prior_transaction_write_retained", "stored_integrity",
                           "fts_query_equal", "fts_internal_integrity"})
            require(case["case"] == name)
            _count(case["partial_row_callbacks"])
            require(case["partial_row_callbacks"] == rows - 1)
            _true_fields(case, ("statement_rollback", "prior_transaction_write_retained",
                                "stored_integrity", "fts_query_equal", "fts_internal_integrity"))


def validate_native(value, rows):
    if type(value) is dict and value.get("captured") is False:
        _object(value, UNAVAILABLE)
        require(value == UNAVAILABLE)
        _false_fields(value, ("captured", "alternate_sqlite_loaded", "default_vfs_changed",
                             "private_import_allowed"))
        _count(value["native_registration_count"])
        return
    _object(value, {"status", "captured", "reason", "runtime_binding", "native_origin",
                    "native_registration_count", "alternate_sqlite_loaded", "default_vfs_changed",
                    "callback_errors", "named_outside_private_count", "unnamed_open_count",
                    "shm_callback_count", "counts", "workload", "file_positive_control",
                    "statement_journal_gates", "experimental_backup_capture",
                    "os_syscalls_captured", "physical_unnamed_paths_qualified",
                    "backup_connections_captured", "private_import_allowed"})
    require(value["captured"] is True and value["status"] == "synthetic_PASS"
            and value["reason"] == "vfs_capture_only"
            and value["runtime_binding"] == "python_sqlite3_vfs_reached"
            and value["native_origin"] in {"python_extension_dependency",
                                           "already_loaded_python_dll", "python_executable_exports"})
    _false_fields(value, ("alternate_sqlite_loaded", "default_vfs_changed", "os_syscalls_captured",
                         "physical_unnamed_paths_qualified", "backup_connections_captured",
                         "private_import_allowed"))
    for name in ("native_registration_count", "callback_errors", "named_outside_private_count",
                 "unnamed_open_count", "shm_callback_count"):
        _count(value[name])
    require(value["native_registration_count"] == 1 and value["callback_errors"] == 0
            and value["named_outside_private_count"] == 0)
    require(type(value["counts"]) is dict and len(value["counts"]) <= 200)
    for name, count in value["counts"].items():
        require(type(name) is str)
        parts = name.split(".")
        require(len(parts) == 3 and parts[0] in {"delete", "wal", "file_control_delete",
                                               "file_control_wal", "backup_delete", "backup_wal"}
                and parts[1] in _KINDS and parts[2] in _OPERATIONS)
        _count(count)
    require(all(value["counts"].get(mode + ".main_db.open") == 1
                and value["counts"].get(mode + ".main_db.write_calls", 0) > 0
                for mode in ("delete", "wal")))
    require(value["counts"].get("delete.main_journal.write_calls", 0) > 0
            and value["counts"].get("wal.wal.write_calls", 0) > 0)
    _workload(value["workload"], rows, 2)
    control = value["file_positive_control"]
    if type(control) is dict and control.get("status") == "NOT RUN":
        _object(control, {"status", "reason"})
        require(control["reason"] == "compiled_memory_only")
    else:
        _workload(control, rows, 1, positive=True)
        require(control["statement_journal_open_count"] == sum(
            value["counts"].get("file_control_" + mode + ".statement_journal.open", 0)
            for mode in ("delete", "wal")))
    expected_gates = statement_journal_gates(
        value["counts"], file_control_supported=control["status"] != "NOT RUN",
    )
    _object(value["statement_journal_gates"], ("delete", "wal"))
    for mode, expected in expected_gates.items():
        gate = value["statement_journal_gates"][mode]
        _object(gate, expected)
        for name in ("file_control_open_count", "file_control_write_calls", "file_control_write_bytes",
                     "memory_open_count", "memory_write_calls", "memory_write_bytes"):
            _count(gate[name])
        require(type(gate["positive_control_observed"]) is bool
                and type(gate["status"]) is str and type(gate["reason"]) is str)
        _false_fields(gate, ("storage_location_qualified", "private_import_allowed"))
        require(gate == expected)
    backup = value["experimental_backup_capture"]
    _object(backup, {"status", "workloads", "actual_python_connections_captured",
                     "production_backup_api_captured", "storage_location_qualified",
                     "private_import_allowed"})
    require(backup["status"] == "synthetic_PASS"
            and type(backup["workloads"]) is list and len(backup["workloads"]) == 2)
    _true_fields(backup, ("actual_python_connections_captured",))
    _false_fields(backup, ("production_backup_api_captured", "storage_location_qualified",
                          "private_import_allowed"))
    for part, mode in zip(backup["workloads"], ("delete", "wal"), strict=True):
        _object(part, {"journal_mode", "rows", "logical_tables_compared", "source_readonly",
                       "source_temp_store", "destination_temp_store", "logical_tables_equal",
                       "stored_integrity", "fts_query_equal", "fts_internal_integrity"})
        for name in ("rows", "logical_tables_compared", "source_temp_store", "destination_temp_store"):
            _count(part[name])
        require(part["journal_mode"] == mode and part["rows"] == rows
                and part["logical_tables_compared"] == len(TABLES)
                and part["source_temp_store"] == part["destination_temp_store"] == 2)
        _true_fields(part, ("source_readonly", "logical_tables_equal", "stored_integrity",
                            "fts_query_equal", "fts_internal_integrity"))
        require(value["counts"].get(f"backup_{mode}.main_db.open") == 2
                and value["counts"].get(f"backup_{mode}.main_db.close") == 2
                and value["counts"].get(f"backup_{mode}.main_db.readonly_open") == 1
                and value["counts"].get(f"backup_{mode}.main_db.readwrite_open") == 1
                and value["counts"].get(f"backup_{mode}.main_db.write_calls", 0) > 0)


def evidence_object(pairs):
    result = {}
    for name, value in pairs:
        require(name not in result)
        result[name] = value
    return result
