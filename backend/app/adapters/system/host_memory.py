"""How much memory this computer actually has.

One number, read from the OS, used by everything that has to decide what the
machine can afford: the context window, the Models screen, the memory bar. It
lived inside an API route, which meant the engine could not ask the question the
route was already answering.

Returns 0 when the OS won't say (some Windows builds), which every caller reads
as "assume nothing" and falls back to a conservative default.
"""

from __future__ import annotations

import os

# What we return when the OS won't say. Every caller reads it as "assume nothing".
_UNKNOWN = 0


def total_physical_ram_bytes() -> int:
    """Total installed RAM in bytes, or 0 if it cannot be determined."""
    try:
        return int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"))
    except (ValueError, OSError, AttributeError):
        # No sysconf (Windows): fall through to the kernel call below.
        return _windows_total_physical_ram_bytes()


def _windows_total_physical_ram_bytes() -> int:
    """Windows has no ``sysconf``; ask the kernel through the C API instead."""
    try:
        import ctypes

        class _MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = _MemoryStatus()
        status.dwLength = ctypes.sizeof(_MemoryStatus)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):  # type: ignore[attr-defined]
            return int(status.ullTotalPhys)
    except Exception:  # noqa: BLE001 - not knowing the RAM must never break startup
        return _UNKNOWN
    return _UNKNOWN
