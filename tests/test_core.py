"""Tests for the core objects (src/spectrum_toolkit/core.py).

Run with:  uv run pytest
pytest finds every function whose name starts with "test_" and runs it.
A test passes if no "assert" fails and no unexpected error is raised.
"""

import numpy as np
import pytest

from spectrum_toolkit import Spectrum, SpectrumCollection


def test_spectrum_basic():
    """A spectrum built from plain lists works and stores floats."""
    s = Spectrum([1, 2, 3], [10, 20, 30], name="a", x_unit="cm-1")
    assert len(s) == 3                 # three points
    assert s.x.dtype == float          # integers were converted to floats
    assert "3 points" in repr(s)       # the notebook summary mentions the size


def test_spectrum_rejects_bad_shapes():
    """Bad input gives a clear error instead of a broken object."""
    # pytest.raises checks that the code inside raises this error, and
    # match= checks that the message contains this text.
    with pytest.raises(ValueError, match="same length"):
        Spectrum([1, 2, 3], [1, 2])                    # 3 x values, 2 y values
    with pytest.raises(ValueError, match="one-dimensional"):
        Spectrum([[1, 2], [3, 4]], [[1, 2], [3, 4]])   # a table, not a row
    with pytest.raises(ValueError, match="two points"):
        Spectrum([1], [1])                             # a single point


def test_with_step_keeps_original_and_records_history():
    """A processing step returns a new spectrum and leaves the original alone."""
    s = Spectrum([1, 2, 3], [10, 20, 30])
    t = s.with_step(s.y / 30, "normalize", method="max")
    assert np.allclose(s.y, [10, 20, 30])                     # original untouched
    assert t.history == ({"step": "normalize", "method": "max"},)  # step recorded


def test_collection_indexing_and_stacking():
    """A collection can be indexed, looped over and rebuilt from spectra."""
    x = np.linspace(0, 1, 5)                           # 5 points from 0 to 1
    c = SpectrumCollection(x, np.ones((3, 5)), positions=np.zeros((3, 2)))
    assert len(c) == 3 and c.n_points == 5             # 3 spectra of 5 points
    assert c[1].name == "Spectrum 2"                   # default names count from 1
    assert [s.name for s in c] == ["Spectrum 1", "Spectrum 2", "Spectrum 3"]
    again = SpectrumCollection.from_spectra(list(c))   # split up and stack again
    assert again.Y.shape == (3, 5)


def test_collection_rejects_mismatch():
    """Spectra that do not line up are refused with a clear message."""
    with pytest.raises(ValueError, match="shape"):
        SpectrumCollection(np.arange(4), np.ones((2, 5)))   # 4 x values, rows of 5
    a, b = Spectrum([1, 2, 3], [1, 1, 1]), Spectrum([1, 2, 4], [1, 1, 1])
    with pytest.raises(ValueError, match="different x axis"):
        SpectrumCollection.from_spectra([a, b])             # x axes differ at the end
