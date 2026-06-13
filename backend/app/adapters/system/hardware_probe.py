"""Detect the machine's total physical RAM, cross-platform, using only stdlib.

Returns gigabytes as a float, or None when it cannot be determined (in which
case the picker simply omits the fit hint rather than guessing). This is the one
piece of model-fit logic that must touch the real machine, so it lives in an
adapter; the verdict math stays pure in core/domain/model_fit.py.
"""

import ctypes
import os
import sys


def detect_total_ram_gb() -> float | None:
    posix_gb = _posix_total_ram_gb()
    if posix_gb is not None:
        return posix_gb
    if sys.platform.startswith("win"):
        return _windows_total_ram_gb()
    return None


def _posix_total_ram_gb() -> float | None:
    """Works on Linux and macOS via sysconf physical page count."""
    try:
        if not hasattr(os, "sysconf"):
            return None
        names = os.sysconf_names
        if "SC_PHYS_PAGES" not in names or "SC_PAGE_SIZE" not in names:
            return None
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        if pages <= 0 or page_size <= 0:
            return None
        return (pages * page_size) / (1024.0**3)
    except (ValueError, OSError):
        return None


def _windows_total_ram_gb() -> float | None:
    try:
        class _MemoryStatusEx(ctypes.Structure):
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

        status = _MemoryStatusEx()
        status.dwLength = ctypes.sizeof(_MemoryStatusEx)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):  # type: ignore[attr-defined]
            return status.ullTotalPhys / (1024.0**3)
        return None
    except Exception:
        return None
