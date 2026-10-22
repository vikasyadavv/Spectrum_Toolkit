"""Tests for groups (src/spectrum_toolkit/groups.py): which sample each spectrum belongs to."""

from pathlib import Path

import numpy as np
import pytest

import spectrum_toolkit as stk
from spectrum_toolkit import Spectrum, SpectrumCollection
from spectrum_toolkit.groups import _name_group

DATA = Path(__file__).parent.parent / "data"
X = np.linspace(400, 1800, 200)


def collection(names):
    """One flat spectrum per name, each at its own height."""
    return SpectrumCollection(X, np.arange(len(names))[:, None] + np.ones((len(names), X.size)), names=names)


@pytest.mark.parametrize("name, group", [
    ("CV 1", "CV"), ("CV_2", "CV"), ("CV-3", "CV"), ("RhB", "RhB"),
    ("CV10-4M: Spectrum 1", "CV10-4M"), ("MB 10-4M: Spectrum 3 (2)", "MB 10-4M"),
    ("Spectrum 1", ""), ("Spot2", ""), ("Sample 4", ""), ("12", ""),
])
def test_group_from_one_name(name, group):
    assert _name_group(name) == group


def test_five_ways_to_set_groups():
    c = collection(["CV 1", "CV 2", "MB 1", "x_spot"])
    assert c.set_groups({"A": range(0, 2), "B": [2, "x_spot"]}).groups == ("A", "A", "B", "B")
    assert c.set_groups({"A": [0]}).groups == ("A", "", "", "")               # not listed: no group
    assert c.set_groups(["a", "a", None, "b"]).groups == ("a", "a", "", "b")
    assert c.set_groups("name").groups == ("CV", "CV", "MB", "x")                 # "spot" numbers, not names
    assert c.set_groups(pattern=r"^(\w+) \d").groups == ("CV", "CV", "MB", "")
    assert c.set_groups("name", rename={"CV": "crystal violet"}).group_names[0] == "crystal violet"
    assert c.set_groups(["a"] * 4).set_groups(None).groups == ()             # removed
    assert c.groups == () and c.group_names == []                             # the original is unchanged


@pytest.mark.parametrize("groups, kwargs, message", [
    ({"A": [0], "B": [0]}, {}, "in two groups"),
    ({"A": [9]}, {}, "does not exist"),
    ({"A": ["nope"]}, {}, "no spectrum named"),
    (["a", "b"], {}, "one per spectrum"),
    ("colour", {}, "Unknown groups"),
    (None, {"pattern": "("}, "not a valid regular expression"),
    (None, {"pattern": "zzz"}, "matches none"),
])
def test_wrong_groups_are_explained(groups, kwargs, message):
    with pytest.raises(ValueError, match=message):
        collection(["CV 1", "CV 2", "MB 1"]).set_groups(groups, **kwargs)


def test_names_that_say_nothing_are_never_guessed():
    c = collection(["Spectrum 1", "Spot2", "Spot3"])
    with pytest.raises(ValueError, match="do not show groups"):
        c.set_groups("name")
    with pytest.raises(ValueError, match="its own group"):
        collection(["a", "b", "c"]).set_groups("name")
    proposal = c.suggest_groups()
    assert proposal["groups"] is None and "one group or several" in proposal["message"]
    proposal = collection(["CV 1", "CV 2", "MB 1"]).suggest_groups()
    assert proposal["by"] == "name" and proposal["counts"] == {"CV": 2, "MB": 1}


def test_groups_follow_their_spectra_through_every_step():
    rng = np.random.default_rng(0)
    c = SpectrumCollection(X, 100 + rng.normal(0, 1, (4, X.size)), names=["a", "b", "c", "d"])
    c = c.set_groups(["A", "A", "B", "B"])
    done = c.trim(500, 1700).despike(verbose=False).baseline().smooth().normalize("max").derivative()
    assert done.groups == c.groups
    assert done.select(3, 0).groups == ("B", "A") and done.drop(0).groups == ("A", "B", "B")
    assert done[2].group == "B" and SpectrumCollection.from_spectra(list(done)).groups == c.groups
    parts = done.by_group()
    assert list(parts) == ["A", "B"] and parts["B"].names == ("c", "d") and parts["B"].history == done.history
    with pytest.raises(ValueError, match="no groups yet"):
        collection(["a", "b"]).by_group()


def test_one_group_per_file():
    files = [DATA / "CV10-4M.xlsx", DATA / "MB 10-4M.xlsx", DATA / "RhB10-4M.xlsx"]
    c = stk.combine(*files, interpolate=True, verbose=False)
    proposal = c.suggest_groups()
    assert proposal["by"] == "file" and proposal["counts"] == {"CV10-4M": 14, "MB 10-4M": 5, "RhB10-4M": 11}
    named = stk.combine(*files, interpolate=True, verbose=False, groups="file").set_groups(
        "file", rename={"CV10-4M": "CV", "MB 10-4M": "MB", "RhB10-4M": "RhB"})
    assert {g: list(named.groups).count(g) for g in named.group_names} == {"CV": 14, "MB": 5, "RhB": 11}
    assert c.set_groups("name").group_names == ["CV10-4M", "MB 10-4M", "RhB10-4M"]   # from "file: name"
    again = stk.combine(named.by_group()["MB"], named.by_group()["CV"], verbose=False)   # groups stay
    assert again.group_names == ["MB", "CV"]
    with pytest.raises(ValueError, match="which file"):
        collection(["a", "b"]).set_groups("file")


def test_one_spectrum_has_one_group():
    s = Spectrum(X, np.ones(X.size), name="s", group="CV")
    assert s.copy_with(y=s.y * 2).group == "CV"
    with pytest.raises(ValueError, match="copy_with"):
        stk.set_groups(s, "name")
