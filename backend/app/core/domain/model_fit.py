"""Pure helpers for judging whether a local model fits the user's machine.

A non-technical user mostly needs one thing answered: "will this AI run well on
my computer?" The biggest cause of a bad first experience is downloading a model
that is too large for the available RAM, which makes it crawl or fail. These
deterministic helpers turn a model's on-disk size plus the machine's total RAM
into a plain verdict the picker can show.

No I/O here: RAM is passed in (detected by an adapter), so this stays testable.
"""

import re

# A quantized model needs roughly its on-disk size in RAM, plus headroom for the
# OS, the app, and the working context. This overhead is intentionally generous.
_RAM_OVERHEAD_GB = 2.0

FIT_COMFORTABLE = "comfortable"
FIT_SLOWER = "works_slower"
FIT_TOO_BIG = "too_big"

_FIT_LABELS = {
    FIT_COMFORTABLE: "Best for your computer",
    FIT_SLOWER: "Will work, may be slower",
    FIT_TOO_BIG: "Too big for this computer",
}


def parse_size_gb(estimated_size: str | None) -> float | None:
    """Parse a human size string like '4.7 GB' or '274 MB' into gigabytes."""
    if not estimated_size:
        return None
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(tb|gb|mb|kb|b)?", estimated_size.strip().lower())
    if not match:
        return None
    value = float(match.group(1))
    unit = match.group(2) or "gb"
    factors = {"tb": 1024.0, "gb": 1.0, "mb": 1.0 / 1024.0, "kb": 1.0 / (1024.0**2), "b": 1.0 / (1024.0**3)}
    return value * factors.get(unit, 1.0)


def assess_model_fit(
    estimated_size: str | None,
    total_ram_gb: float | None,
) -> tuple[str | None, str | None]:
    """Return a (fit_code, fit_label) verdict, or (None, None) when unknown.

    Unknown is returned when either the model size or the machine RAM cannot be
    determined, so the UI simply shows no badge instead of a misleading one.
    """
    size_gb = parse_size_gb(estimated_size)
    if size_gb is None or total_ram_gb is None or total_ram_gb <= 0:
        return (None, None)

    needed_gb = size_gb + _RAM_OVERHEAD_GB
    if needed_gb <= total_ram_gb * 0.6:
        code = FIT_COMFORTABLE
    elif needed_gb <= total_ram_gb * 0.9:
        code = FIT_SLOWER
    else:
        code = FIT_TOO_BIG
    return (code, _FIT_LABELS[code])
