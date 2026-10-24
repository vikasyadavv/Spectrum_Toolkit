"""About the data (spectrum_toolkit.about): facts from the numbers, the measurement, settings, notes, steps."""
import numpy as np
import pytest

import spectrum_toolkit as stk
from spectrum_toolkit import Spectrum, SpectrumCollection
from spectrum_toolkit.about import NOTHING_DONE, _nice, _took, _when


def lines(info, key):
    """A section as a dict label -> value."""
    return dict(info[key])


def test_example_has_every_section():
    info = stk.about(stk.example())
    assert info["file"] == {"name": None, "type": "Example spectra (made up)"}
    data = lines(info, "data")
    assert data["Spectra"] == "3" and data["Points each"] == "1400" and data["Raman shift (cm⁻¹)"] == "400 – 1800"
    assert data["Step"] == "1" and data["Missing points"] == "none" and data["Map"] == "no" and data["Groups"] == "none"
    assert info["measurement"] == [] and info["settings"] == [] and info["history"] == [NOTHING_DONE]
    assert "made-up" in info["notes"][0]
    assert info["text"].splitlines()[:2] == ["About the data", "File: Example spectra (made up)"]


def test_facts_from_the_numbers():
    """Uneven step with its range, missing points, groups with counts, labels from the units."""
    x = np.array([100, 101, 102, 104, 105.0])
    Y = np.array([[1, 2, np.nan, 4, 5], [10, 20, 30, 40, 50.0], [0, 0, 0, 0, 0.0]])
    c = SpectrumCollection(x, Y, x_unit="Wavelength (nm)", y_unit="counts", groups=["A", "A", ""])
    data = lines(stk.about(c), "data")
    assert data["Wavelength (nm)"] == "100 – 105" and data["Step"] == "1 (1 – 2)"
    assert data["Intensity (counts)"] == "0 – 50" and data["Missing points"] == "1 of 15"
    assert data["Groups"] == "2: A (2), (no group) (1)"
    s = Spectrum(x, Y[1], x_unit="W", y_unit="wt")                   # .mat files: the units are variable names
    assert set(lines(stk.about(s), "data")) >= {"x (W)", "y (wt)"}


def test_measurement_settings_and_map_from_the_file():
    """The same labels for every file type; nested settings as "Section › name"; the map grid with its step."""
    meta = {"file_type": "wdf", "source": "/tmp/x/map.wdf", "instrument": "Renishaw WiRE 5.6", "title": "Map 4",
            "measurement": "map", "scan": "static", "laser_nm": 632.8, "accumulations": 2,
            "start": "2023-11-22T08:55:48Z", "end": "2023-11-22T09:32:40Z", "operator": "admin",
            "map": {"start": [0, 0, 0], "step": [1.0, 2.0, 1.0], "points": [3, 2, 1]}, "position_labels": ["X (µm)", "Y (µm)"],
            "method": {"Measurement": {"Scan Speed": "Fast", "Empty": ""}}, "load_notes": ["read it"]}
    c = SpectrumCollection(np.arange(5.0), np.ones((6, 5)), positions=np.zeros((6, 2)), meta=meta)
    info = stk.about(c)
    assert info["file"] == {"name": "map.wdf", "type": "Renishaw WiRE (.wdf)"}
    assert lines(info, "measurement") == {"Instrument": "Renishaw WiRE 5.6", "Title": "Map 4", "Type": "Map, static scan",
                                          "Laser": "632.8 nm", "Accumulations": "2", "Started": "22 Nov 2023, 08:55 UTC",
                                          "Took": "36 min 52 s", "Operator": "admin"}
    assert lines(info, "data")["Map"] == "3 × 2, step 1 × 2 µm"
    assert info["settings"] == [["Measurement › Scan Speed", "Fast"]]  # empty values left out
    assert info["notes"] == ["read it"] and "All instrument settings" in info["text"]


def test_history_lists_each_step_with_its_settings():
    c = stk.example()
    d = stk.baseline(c.trim(500, 1600), "airpls")
    steps = stk.about(d)["history"]
    assert steps[0].startswith("trim (lo 500, hi 1600") and steps[1].startswith("baseline: airpls (")
    spikes = SpectrumCollection(c.x, c.Y, history=({"step": "despike", "method": "single",
                                                    "spikes": {"Sample A": [{}, {}], "Sample C": [{}]}},))
    assert stk.about(spikes)["history"] == ["despike: single (3 spikes in 2 spectra)"]


def test_helpers_and_wrong_input():
    assert (_nice(12345.678), _nice(0.000123456), _nice(float("nan"))) == ("12346", "0.00012346", "–")
    assert _when("2023-11-22T06:36:44Z") == "22 Nov 2023, 06:36 UTC"
    assert (_took("2023-11-22T06:36:44Z", "2023-11-22T06:36:50Z"), _took("2023-11-22T06:00:00Z", "2023-11-22T07:05:00Z"),
            _took("2023-11-22T06:00:00Z", None)) == ("6 s", "1 h 5 min", None)
    with pytest.raises(TypeError, match="Spectrum or SpectrumCollection"):
        stk.about([1, 2, 3])
