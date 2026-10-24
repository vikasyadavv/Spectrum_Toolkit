"""Example spectra: three made-up Raman-like spectra, so anything can be tried without a data file.

The documentation pictures (docs/plotting.md) and the website's preview
before a file is loaded (GET /example) use the same spectra.

>>> import spectrum_toolkit as stk
>>> stk.example().names
('Sample A', 'Sample B', 'Sample C')
"""

from __future__ import annotations

import numpy as np

from .core import SpectrumCollection


def example() -> SpectrumCollection:
    """Three made-up Raman-like spectra, 400-1800 cm⁻¹, 1400 points, with a little noise.

    Always the same numbers (fixed random seed), so pictures made from them
    can be compared pixel by pixel.
    """
    x = np.linspace(400, 1800, 1400)
    rng = np.random.default_rng(1)                               # fixed seed: the same noise every time
    bands = [(915, 0.7, 6), (1180, 0.7, 10), (1370, 0.6, 18), (1585, 0.75, 7), (1620, 1.0, 7)]  # centre, height, half width
    Y = []
    for k in range(3):                                           # each sample 10 % weaker than the one before
        y = sum(h * (1 - 0.1 * k) / (1 + ((x - c) / w) ** 2) for c, h, w in bands)
        Y.append(y + rng.normal(0, 0.01, x.size))
    note = ("Three made-up Raman-like spectra (bands at 915, 1180, 1370, 1585 and 1620 cm⁻¹, a little noise): "
            "the same ones the documentation pictures use.")
    return SpectrumCollection(x, np.array(Y), names=["Sample A", "Sample B", "Sample C"], x_unit="Raman shift (cm⁻¹)",
                              y_unit="Intensity", meta={"file_type": "example", "load_notes": [note]})


__all__ = ["example"]
