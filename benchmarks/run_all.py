"""Run every benchmark and write docs/benchmarks.md.

    uv run python benchmarks/run_all.py            # all, full size (a few minutes)
    uv run python benchmarks/run_all.py --quick    # fewer spectra, for a quick look
    uv run python benchmarks/run_all.py smooth     # only some sections (printed, file not written)

Every benchmark uses fixed random seeds, so the numbers are the same on
every run with the same library versions. Rerun after changing a method or
its defaults, and commit the new docs/benchmarks.md with the change.
"""

import platform
import sys
import time
from datetime import date
from pathlib import Path

import numpy as np
import scipy

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))                       # so "import despike" finds the benchmark files here

import spectrum_toolkit  # noqa: E402

import baseline, derivative, despike, normalize, smooth  # noqa: E402

SECTIONS = [("Cosmic-ray removal (despike)", despike), ("Baseline correction", baseline),
            ("Smoothing", smooth), ("Normalisation", normalize), ("Derivatives", derivative)]


def main():
    quick = "--quick" in sys.argv
    only = [a for a in sys.argv[1:] if not a.startswith("--")]
    parts = []
    for title, module in SECTIONS:
        if only and module.__name__ not in only:
            continue
        start = time.time()
        body = module.run(quick=quick)
        took = time.time() - start
        print(f"{title}: {took:.0f} s")
        parts.append(f"## {title}\n\n{module.__doc__.split(chr(10) + chr(10), 1)[1].strip()}\n\n{body}\n\n"
                     f"_Script: `benchmarks/{module.__name__}.py`._\n")
    header = (
        "# Benchmarks\n\n"
        "How the methods compare, measured on simulated spectra whose true answer is known "
        "(and on the real files in `data/` where useful). These numbers are why the defaults "
        "are what they are. **This file is generated; do not edit it by hand.** Rerun with:\n\n"
        "```\nuv run python benchmarks/run_all.py\n```\n\n"
        f"Generated {date.today().isoformat()}{' (QUICK run, fewer spectra)' if quick else ''} with "
        f"spectrum_toolkit {spectrum_toolkit.__version__}, Python {platform.python_version()}, "
        f"numpy {np.__version__}, scipy {scipy.__version__}.\n\n"
        "Simulated spectra (benchmarks/_simulate.py): points every 1.19 cm-1 from 100 to 1800 cm-1, "
        "Lorentzian bands 8-20 cm-1 wide, photon noise plus 15 counts read noise, like the real data.\n\n"
        "Contents: " + ", ".join(f"[{t}](#{t.lower().replace(' ', '-').replace('(', '').replace(')', '')})"
                                 for t, m in SECTIONS if not only or m.__name__ in only) + "\n\n"
    )
    text = header + "\n".join(parts)
    if only:
        print(text)
        return
    out = HERE.parent / "docs" / "benchmarks.md"
    out.write_text(text, encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
