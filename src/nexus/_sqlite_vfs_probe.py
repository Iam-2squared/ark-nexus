"""Disposable-process VFS instrumentation of Python's own SQLite only.

Not imported by the server. No OS hooks, alternate SQLite load, default-VFS
replacement, original-VFS mutation, content capture or raw paths in output.
VFS xOpen/xWrite is not a syscall trace: unnamed physical paths, mmap/SHM,
OS caches, unlink remnants, crash dumps and swap remain unqualified.
"""

import _sqlite3
import collections
import ctypes as ct
import os
import sqlite3
from pathlib import Path

from nexus.private_storage import checked_path
from nexus.sqlite_workload import ProbeProblem, require, run_workload

KINDS = {
    "main_db": 0x100, "temp_db": 0x200, "transient_db": 0x400,
    "main_journal": 0x800, "temp_journal": 0x1000, "statement_journal": 0x2000,
    "super_journal": 0x4000, "wal": 0x80000,
}


class Unavailable(Exception):
    pass


class VFS(ct.Structure):
    pass


class Methods(ct.Structure):
    pass


class File(ct.Structure):
    _fields_ = [("pMethods", ct.POINTER(Methods))]


Pointer = ct.c_void_p
Int = ct.c_int
Int64 = ct.c_int64
OPEN = ct.CFUNCTYPE(Int, ct.POINTER(VFS), Pointer, Pointer, Int, ct.POINTER(Int))
DELETE = ct.CFUNCTYPE(Int, ct.POINTER(VFS), Pointer, Int)
VFS._fields_ = [
    ("iVersion", Int), ("szOsFile", Int), ("mxPathname", Int),
    ("pNext", ct.POINTER(VFS)), ("zName", ct.c_char_p), ("pAppData", Pointer),
    ("xOpen", Pointer), ("xDelete", Pointer),
    *[(name, Pointer) for name in (
        "xAccess", "xFullPathname", "xDlOpen", "xDlError", "xDlSym", "xDlClose",
        "xRandomness", "xSleep", "xCurrentTime", "xGetLastError", "xCurrentTimeInt64",
        "xSetSystemCall", "xGetSystemCall", "xNextSystemCall",
    )],
]
IO = {
    "xClose": (1, Int, (Pointer,)), "xRead": (1, Int, (Pointer, Pointer, Int, Int64)),
    "xWrite": (1, Int, (Pointer, Pointer, Int, Int64)), "xTruncate": (1, Int, (Pointer, Int64)),
    "xSync": (1, Int, (Pointer, Int)), "xFileSize": (1, Int, (Pointer, ct.POINTER(Int64))),
    "xLock": (1, Int, (Pointer, Int)), "xUnlock": (1, Int, (Pointer, Int)),
    "xCheckReservedLock": (1, Int, (Pointer, ct.POINTER(Int))),
    "xFileControl": (1, Int, (Pointer, Int, Pointer)), "xSectorSize": (1, Int, (Pointer,)),
    "xDeviceCharacteristics": (1, Int, (Pointer,)),
    "xShmMap": (2, Int, (Pointer, Int, Int, Int, ct.POINTER(Pointer))),
    "xShmLock": (2, Int, (Pointer, Int, Int, Int)), "xShmBarrier": (2, None, (Pointer,)),
    "xShmUnmap": (2, Int, (Pointer, Int)), "xFetch": (3, Int, (Pointer, Int64, Int, ct.POINTER(Pointer))),
    "xUnfetch": (3, Int, (Pointer, Int64, Pointer)),
}
Methods._fields_ = [("iVersion", Int), *((name, Pointer) for name in IO)]


def runtime_library():
    """Load exports from the already used extension/DLL; never search system SQLite."""
    candidates = []
    extension = getattr(_sqlite3, "__file__", None)
    if extension is not None:
        try:
            candidates.append((ct.CDLL(extension), "python_extension_dependency"))
        except OSError:
            pass
    if os.name == "nt":
        kernel = ct.WinDLL("kernel32", use_last_error=True)
        kernel.GetModuleHandleW.argtypes = [ct.c_wchar_p]
        kernel.GetModuleHandleW.restype = Pointer
        handle = kernel.GetModuleHandleW("sqlite3.dll")
        if handle:
            candidates.append((ct.CDLL("sqlite3.dll", handle=handle), "already_loaded_python_dll"))
    elif extension is None:
        candidates.append((ct.CDLL(None), "python_executable_exports"))
    required = ("sqlite3_libversion", "sqlite3_sourceid", "sqlite3_vfs_find",
                "sqlite3_vfs_register", "sqlite3_vfs_unregister")
    with sqlite3.connect(":memory:") as db:
        source_id = db.execute("SELECT sqlite_source_id()").fetchone()[0]
    for library, origin in candidates:
        if not all(hasattr(library, name) for name in required):
            continue
        library.sqlite3_libversion.restype = ct.c_char_p
        library.sqlite3_sourceid.restype = ct.c_char_p
        if (library.sqlite3_libversion().decode("ascii") != sqlite3.sqlite_version
                or library.sqlite3_sourceid().decode("ascii") != source_id):
            continue
        library.sqlite3_vfs_find.argtypes = [ct.c_char_p]
        library.sqlite3_vfs_find.restype = ct.POINTER(VFS)
        library.sqlite3_vfs_register.argtypes = [ct.POINTER(VFS), Int]
        library.sqlite3_vfs_register.restype = Int
        library.sqlite3_vfs_unregister.argtypes = [ct.POINTER(VFS)]
        library.sqlite3_vfs_unregister.restype = Int
        return library, origin
    raise Unavailable


class Observer:
    def __init__(self, library, root: Path):
        self.library = library
        self.root = root
        self.original = library.sqlite3_vfs_find(None)
        if (not self.original or self.original.contents.iVersion != 3
                or not 8 <= self.original.contents.szOsFile <= 4096):
            raise Unavailable
        self.original_address = ct.addressof(self.original.contents)
        self.name = b"nexus-disposable-observer-v1"
        if library.sqlite3_vfs_find(self.name):
            raise Unavailable
        self.files = {}
        self.refs = []
        self.counts = collections.Counter()
        self.stage = "all"
        self.callback_errors = 0
        self.named_outside = 0
        self.unnamed_opens = 0
        self.shm_calls = 0
        self.registration_count = 0
        self.original_open = OPEN(self.original.contents.xOpen)
        self.original_delete = DELETE(self.original.contents.xDelete)
        self.open_callback = OPEN(self.open)
        self.delete_callback = DELETE(self.delete)
        self.wrapper = VFS()
        ct.memmove(ct.byref(self.wrapper), self.original, ct.sizeof(VFS))
        self.wrapper.zName = self.name
        # SQLite owns pNext after registration. The default remains untouched.
        self.wrapper.szOsFile = self.original.contents.szOsFile + 16
        self.wrapper.xOpen = ct.cast(self.open_callback, Pointer).value
        self.wrapper.xDelete = ct.cast(self.delete_callback, Pointer).value

    def record(self, operation, kind, amount=1):
        self.counts[f"{self.stage}.{kind}.{operation}"] += amount

    def path_inside(self, address):
        if not address:
            return False
        name = os.fsdecode(ct.string_at(address))
        try:
            if ".." in Path(name).parts:
                return False
            return checked_path(Path(name)).is_relative_to(self.root)
        except (ValueError, UnicodeError):
            return False

    def open(self, _vfs, name, outer_file, flags, output_flags):
        """Preserve sqlite3_filename pointer metadata when delegating xOpen."""
        try:
            kind = next((name for name, bit in KINDS.items() if flags & bit), "other")
            if name:
                if not self.path_inside(name):
                    self.named_outside += 1
                    return 14  # SQLITE_CANTOPEN, synthetic scope fails closed.
            else:
                self.unnamed_opens += 1
            self.record("open", kind)
            self.record("unnamed_open" if not name else "named_open", kind)
            real_file = outer_file + 16
            result = self.original_open(self.original, name, real_file, flags, output_flags)
            methods = ct.cast(real_file, ct.POINTER(File)).contents.pMethods
            # The underlying xClose must still run when failed xOpen sets pMethods.
            if methods:
                if not 1 <= methods.contents.iVersion <= 3:
                    self.callback_errors += 1
                    return 10
                proxy = Methods()
                proxy.iVersion = methods.contents.iVersion
                callbacks = []
                for method, (version, result_type, arguments) in IO.items():
                    if version > methods.contents.iVersion:
                        continue
                    pointer = getattr(methods.contents, method)
                    if not pointer:
                        continue
                    signature = ct.CFUNCTYPE(result_type, *arguments)
                    native = signature(pointer)

                    def forward(file, *args, _method=method, _native=native,
                                _result_type=result_type):
                        try:
                            if _method == "xWrite":
                                self.record("write_calls", kind)
                                self.record("write_bytes", kind, args[1])
                            elif _method in ("xShmMap", "xShmLock", "xShmBarrier", "xShmUnmap"):
                                self.shm_calls += 1
                            value = _native(file + 16, *args)
                            if _method == "xClose":
                                self.record("close", kind)
                                ct.cast(file, ct.POINTER(File)).contents.pMethods = ct.POINTER(Methods)()
                                self.files.pop(file, None)
                            return value
                        except BaseException:
                            self.callback_errors += 1
                            return None if _result_type is None else 10

                    callback = signature(forward)
                    setattr(proxy, method, ct.cast(callback, Pointer).value)
                    callbacks.append(callback)
                # Keep original native file/methods, callbacks and proxy alive until unregister.
                self.refs.append((proxy, callbacks, methods))
                self.files[outer_file] = proxy
                ct.cast(outer_file, ct.POINTER(File)).contents.pMethods = ct.pointer(proxy)
            return result
        except BaseException:
            self.callback_errors += 1
            return 10

    def delete(self, _vfs, name, sync_directory):
        try:
            if not self.path_inside(name):
                self.named_outside += 1
                return 10
            self.counts[f"{self.stage}.all.delete"] += 1
            return self.original_delete(self.original, name, sync_directory)
        except BaseException:
            self.callback_errors += 1
            return 10

    def unchanged(self):
        found = self.library.sqlite3_vfs_find(None)
        return bool(found) and ct.addressof(found.contents) == self.original_address

    def register(self):
        require(self.library.sqlite3_vfs_register(ct.byref(self.wrapper), 0) == 0)
        self.registration_count += 1
        require(self.unchanged())

    def unregister(self):
        require(not self.files)
        require(self.library.sqlite3_vfs_unregister(ct.byref(self.wrapper)) == 0)
        require(self.unchanged() and not self.library.sqlite3_vfs_find(self.name))


def capture(root: Path, rows: int) -> dict:
    try:
        library, origin = runtime_library()
        observer = Observer(library, root)
    except Unavailable:
        return {"status": "NOT RUN", "captured": False, "reason": "capability_unavailable",
                "native_registration_count": 0, "alternate_sqlite_loaded": False,
                "default_vfs_changed": False, "private_import_allowed": False}
    observer.register()
    try:
        def connection(path):
            before = sum(observer.counts.values())
            db = sqlite3.connect(path.as_uri() + "?vfs=" + observer.name.decode("ascii"), uri=True)
            if sum(observer.counts.values()) <= before:
                db.close()
                raise ProbeProblem("Python SQLite native observation was not reached")
            return db

        def stage(mode):
            observer.stage = mode

        workload = run_workload(root / "observed-workload", rows=rows,
                                connection_factory=connection, before_case=stage)
        with sqlite3.connect(":memory:") as compiled:
            file_control_supported = "TEMP_STORE=3" not in {
                value[0] for value in compiled.execute("PRAGMA compile_options")
            }
        positive_control = {"status": "NOT RUN", "reason": "compiled_memory_only"}
        if file_control_supported:
            positive_control = run_workload(
                root / "file-positive-control", rows=rows, connection_factory=connection,
                before_case=lambda mode: stage("file_control_" + mode), temp_store="file",
            )
            positive_control["production_configuration"] = False
            positive_control["statement_journal_open_count"] = sum(
                observer.counts[f"file_control_{mode}.statement_journal.open"]
                for mode in ("delete", "wal")
            )
        require(observer.callback_errors == 0 and observer.named_outside == 0)
        require(all(observer.counts[f"{mode}.main_db.write_calls"] > 0
                    and observer.counts[f"{mode}.main_db.open"] == 1
                    for mode in ("delete", "wal")))
        require(observer.counts["delete.main_journal.write_calls"] > 0)
        require(observer.counts["wal.wal.write_calls"] > 0)
        return {"status": "synthetic_PASS", "captured": True, "reason": "vfs_capture_only",
                "runtime_binding": "python_sqlite3_vfs_reached", "native_origin": origin,
                "native_registration_count": observer.registration_count,
                "alternate_sqlite_loaded": False, "default_vfs_changed": False,
                "callback_errors": observer.callback_errors,
                "named_outside_private_count": observer.named_outside,
                "unnamed_open_count": observer.unnamed_opens,
                "shm_callback_count": observer.shm_calls,
                "counts": dict(sorted(observer.counts.items())), "workload": workload,
                "file_positive_control": positive_control,
                "os_syscalls_captured": False, "physical_unnamed_paths_qualified": False,
                "backup_connections_captured": False, "private_import_allowed": False}
    finally:
        observer.unregister()
