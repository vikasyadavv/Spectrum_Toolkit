"""Core data objects of Spectrum Toolkit.

Every file loader produces one of these objects, and every processing step
(trim, baseline, smoothing ...) takes one and returns a NEW one. Nothing is
ever changed in place, so the original data is always available for a
before/after comparison.

Two objects:

- ``Spectrum``: one spectrum, i.e. an x axis (e.g. Raman shift) and a
  y axis (e.g. intensity) of the same length.
- ``SpectrumCollection``: many spectra that share ONE x axis, such as the
  5 samples in a spreadsheet or the 550 pixels of a Raman map.

Example
-------
>>> s = Spectrum([100, 101, 102], [5, 9, 4], name="test")
>>> len(s)
3
"""

# Lets us write type hints such as "Spectrum | None" inside the class that
# defines Spectrum itself (Python would otherwise complain the name is unknown).
from __future__ import annotations

# dataclass: writes the boring __init__ for us from the field list below.
# field: lets a field default to a fresh empty dict for every new object.
# replace: makes a copy of a dataclass with some fields changed.
from dataclasses import dataclass, field, replace

# Any: "any type at all"; Iterator: something you can loop over once.
# Both are only used in type hints, which document what a function expects.
from typing import Any, Iterator

# numpy: fast arrays of numbers; all spectral data is stored as numpy arrays.
import numpy as np


def require_distinct_x(x: np.ndarray, what: str) -> None:
    """Raise a clear error if x (sorted ascending) has the same value twice.

    Methods that divide by the spacing between points (derivatives, splines,
    windows in x units) cannot work when two points share one x value.
    """
    repeats = int(np.sum(np.diff(x) == 0))
    if repeats:
        raise ValueError(f"{what} needs every x value once, but {repeats} x value(s) appear more than once. "
                         "Check the file (is it a map, or several spectra in one column?), or remove the "
                         "repeated points first.")


def _as_1d_float(values: Any, name: str) -> np.ndarray:
    """Convert a list/array to a 1-D array of floats, or raise a clear error.

    The leading underscore in the name means "internal helper, not part of the
    public library".
    """
    # Convert whatever we got (list, tuple, numpy array, pandas column ...)
    # into a numpy array of floating-point numbers. Integers become floats.
    arr = np.asarray(values, dtype=float)
    # A spectrum axis must be a single row of numbers, not a table.
    if arr.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional, got shape {arr.shape}.")
    return arr


# frozen=True: once created, the object's fields cannot be reassigned
#   (s.y = ... raises an error). This protects the original data.
# eq=False: do not auto-generate "==" comparison; comparing big arrays with
#   "==" is ambiguous in numpy, so we leave it out on purpose.
@dataclass(frozen=True, eq=False)
class Spectrum:
    """One spectrum.

    Attributes
    ----------
    x, y : 1-D arrays of equal length.
    name : label shown in plots and legends.
    x_unit, y_unit : axis labels, e.g. "Raman shift (cm⁻¹)", "Intensity (counts)".
    meta : anything read from the file (instrument, laser, acquisition time ...).
    history : processing steps applied so far, oldest first. Each entry is a
        dict with at least a "step" key, so the full recipe can be saved and
        re-applied to another file.
    group : the sample or class it belongs to, e.g. "CV"; "" for none.
    """

    # The fields of the object, in the order they can be passed when creating
    # one: Spectrum(x, y, name, x_unit, y_unit, meta, history).
    x: np.ndarray
    y: np.ndarray
    name: str = ""
    x_unit: str = ""
    y_unit: str = ""
    # default_factory=dict gives every Spectrum its OWN empty dict. A plain
    # "= {}" would make all spectra share one dict, a classic Python trap.
    meta: dict = field(default_factory=dict)
    # A tuple (not a list) because tuples cannot be modified after creation.
    history: tuple = ()
    group: str = ""

    def __post_init__(self) -> None:
        """Check and clean the data right after the object is created."""
        # Turn x and y into 1-D float arrays (raises an error if impossible).
        x = _as_1d_float(self.x, "x")
        y = _as_1d_float(self.y, "y")
        # Every x value needs exactly one y value.
        if x.shape != y.shape:
            raise ValueError(f"x and y must have the same length, got {x.size} and {y.size}.")
        # With fewer than two points nothing (plotting, processing) makes sense.
        if x.size < 2:
            raise ValueError("A spectrum needs at least two points.")
        # The object is frozen, so normal assignment is blocked. This is the
        # one sanctioned way to store the cleaned arrays during creation.
        object.__setattr__(self, "x", x)
        object.__setattr__(self, "y", y)
        # Accept a list for history too, but always store it as a tuple.
        object.__setattr__(self, "history", tuple(self.history))
        object.__setattr__(self, "group", "" if self.group is None else str(self.group))

    def __len__(self) -> int:
        """len(spectrum) gives the number of points."""
        return self.x.size

    def __repr__(self) -> str:
        """The short summary shown when you type the variable name in a notebook."""
        # Join the names of all processing steps, or say "none" if there are none.
        steps = ", ".join(h["step"] for h in self.history) or "none"
        # :.6g prints a number with up to 6 significant digits, e.g. 3645.92.
        return (f"Spectrum({self.name!r}, {len(self)} points, "
                f"x {self.x.min():.6g} to {self.x.max():.6g}, steps: {steps})")

    def copy_with(self, **changes: Any) -> "Spectrum":
        """Return a new Spectrum with some fields replaced.

        Example: ``s.copy_with(name="sample 2")``. The original is unchanged.
        """
        return replace(self, **changes)

    # ----- editing (the work is done in edit.py; these are shortcuts) -----
    def trim(self, lo: float, hi: float) -> "Spectrum":
        """Keep only lo <= x <= hi. See ``spectrum_toolkit.edit.trim``."""
        from .edit import trim          # imported here: edit.py itself imports this file
        return trim(self, lo, hi)

    def cut(self, lo: float, hi: float) -> "Spectrum":
        """Remove lo <= x <= hi. See ``spectrum_toolkit.edit.cut``."""
        from .edit import cut
        return cut(self, lo, hi)

    def despike(self, method: str = "single", **settings: Any) -> "Spectrum":
        """Remove cosmic-ray spikes. See ``spectrum_toolkit.despike.despike``."""
        from .despike import despike
        return despike(self, method, **settings)

    def baseline(self, method: str = "airpls", **settings: Any) -> "Spectrum":
        """Subtract the baseline. See ``spectrum_toolkit.baseline.baseline``."""
        from .baseline import baseline
        return baseline(self, method, **settings)

    def smooth(self, method: str = "savgol", **settings: Any) -> "Spectrum":
        """Reduce noise. See ``spectrum_toolkit.smooth.smooth``."""
        from .smooth import smooth
        return smooth(self, method, **settings)

    def normalize(self, method: str = "snv", **settings: Any) -> "Spectrum":
        """Put the intensity on a comparable scale. See ``spectrum_toolkit.normalize.normalize``."""
        from .normalize import normalize
        return normalize(self, method, **settings)

    def derivative(self, method: str = "savgol", **settings: Any) -> "Spectrum":
        """First or second derivative. See ``spectrum_toolkit.derivative.derivative``."""
        from .derivative import derivative
        return derivative(self, method, **settings)

    def plot(self, kind: str = "lines", **settings: Any):
        """Draw it with matplotlib; returns the Axes. See ``spectrum_toolkit.plot.plot``."""
        from .plot import plot
        return plot(self, kind=kind, **settings)

    def apply(self, recipe: Any, verbose: bool = False) -> "Spectrum":
        """Apply a Recipe (or a recipe .json file). See ``spectrum_toolkit.recipe``."""
        from .recipe import apply
        return apply(self, recipe, verbose)

    def with_step(self, y: np.ndarray, step: str, x: np.ndarray | None = None, **params: Any) -> "Spectrum":
        """Return the result of a processing step, recorded in the history.

        Every processing function ends by calling this, e.g.
        ``s.with_step(new_y, "smooth", method="savgol", window=11)``.

        Parameters
        ----------
        y : the processed y values.
        step : short name of the step ("trim", "baseline", ...).
        x : new x values, only for steps that change x (e.g. trim).
        **params : the settings used, stored so the step can be repeated.
        """
        return replace(
            self,
            # Keep the old x unless the step produced a new one.
            x=self.x if x is None else x,
            y=y,
            # Append one entry: {"step": "smooth", "method": "savgol", ...}.
            history=self.history + ({"step": step, **params},),
        )


@dataclass(frozen=True, eq=False)
class SpectrumCollection:
    """Many spectra on one shared x axis.

    Attributes
    ----------
    x : 1-D array, length n_points.
    Y : 2-D array, shape (n_spectra, n_points); one ROW per spectrum.
    names : one label per spectrum.
    x_unit, y_unit : axis labels, shared by all spectra.
    positions : optional (n_spectra, k) array of stage coordinates for maps,
        e.g. k = 2 for X, Y.
    meta : anything read from the file.
    history : processing steps applied to all spectra, oldest first.
    groups : one group label per spectrum (the sample or class, e.g. "CV"),
        "" for a spectrum in no group; () when no groups are set. Groups
        follow their spectra through every step. Set them with set_groups.
    """

    x: np.ndarray
    # Capital Y signals "a matrix" (many spectra), lower-case y "one spectrum".
    Y: np.ndarray
    names: tuple = ()
    x_unit: str = ""
    y_unit: str = ""
    positions: np.ndarray | None = None
    meta: dict = field(default_factory=dict)
    history: tuple = ()
    groups: tuple = ()

    def __post_init__(self) -> None:
        """Check and clean the data right after the object is created."""
        x = _as_1d_float(self.x, "x")
        # atleast_2d turns a single spectrum (1-D) into a 1-row table, so a
        # collection of one spectrum also works.
        Y = np.atleast_2d(np.asarray(self.Y, dtype=float))
        # Each row must have exactly one value per x point.
        if Y.ndim != 2 or Y.shape[1] != x.size:
            raise ValueError(f"Y must have shape (n_spectra, {x.size}), got {Y.shape}.")
        # If no names were given, number the spectra "Spectrum 1", "Spectrum 2" ...
        names = tuple(self.names) or tuple(f"Spectrum {i + 1}" for i in range(Y.shape[0]))
        if len(names) != Y.shape[0]:
            raise ValueError(f"Got {len(names)} names for {Y.shape[0]} spectra.")
        # Map coordinates are optional; when given, one row per spectrum.
        if self.positions is not None:
            pos = np.asarray(self.positions, dtype=float)
            if pos.ndim != 2 or pos.shape[0] != Y.shape[0]:
                raise ValueError(f"positions must have shape ({Y.shape[0]}, k), got {pos.shape}.")
            object.__setattr__(self, "positions", pos)
        # Store the cleaned values (see the note in Spectrum.__post_init__).
        object.__setattr__(self, "x", x)
        object.__setattr__(self, "Y", Y)
        object.__setattr__(self, "names", names)
        object.__setattr__(self, "history", tuple(self.history))
        # Groups: one text per spectrum ("" = none); all empty is the same as no groups.
        groups = tuple("" if g is None else str(g) for g in self.groups)
        if groups and len(groups) != Y.shape[0]:
            raise ValueError(f"Got {len(groups)} groups for {Y.shape[0]} spectra; give one per spectrum.")
        object.__setattr__(self, "groups", groups if any(groups) else ())

    def __len__(self) -> int:
        """len(collection) gives the number of spectra (rows)."""
        return self.Y.shape[0]

    def __getitem__(self, i: int) -> Spectrum:
        """collection[i] gives spectrum number i as a Spectrum (0 is the first)."""
        return Spectrum(self.x, self.Y[i], name=self.names[i], x_unit=self.x_unit,
                        y_unit=self.y_unit, meta=self.meta, history=self.history,
                        group=self.groups[i] if self.groups else "")

    def __iter__(self) -> Iterator[Spectrum]:
        """Lets you write: for s in collection: ..."""
        return (self[i] for i in range(len(self)))

    def __repr__(self) -> str:
        """The short summary shown when you type the variable name in a notebook."""
        return (f"SpectrumCollection({len(self)} spectra × {self.x.size} points, "
                f"x {self.x.min():.6g} to {self.x.max():.6g})")

    def copy_with(self, **changes: Any) -> "SpectrumCollection":
        """Return a new collection with some fields replaced; the original is unchanged."""
        return replace(self, **changes)

    # ----- editing (the work is done in edit.py; these are shortcuts) -----
    def trim(self, lo: float, hi: float) -> "SpectrumCollection":
        """Keep only lo <= x <= hi, for every spectrum. See ``spectrum_toolkit.edit.trim``."""
        from .edit import trim
        return trim(self, lo, hi)

    def cut(self, lo: float, hi: float) -> "SpectrumCollection":
        """Remove lo <= x <= hi, for every spectrum. See ``spectrum_toolkit.edit.cut``."""
        from .edit import cut
        return cut(self, lo, hi)

    def select(self, *keys: int | str) -> "SpectrumCollection":
        """Keep only these spectra, by number (0 = first) or name. See ``edit.select``."""
        from .edit import select
        return select(self, *keys)

    def drop(self, *keys: int | str) -> "SpectrumCollection":
        """Remove these spectra, by number (0 = first) or name. See ``edit.drop``."""
        from .edit import drop
        return drop(self, *keys)

    def despike(self, method: str = "single", **settings: Any) -> "SpectrumCollection":
        """Remove cosmic-ray spikes from every spectrum. See ``spectrum_toolkit.despike.despike``."""
        from .despike import despike
        return despike(self, method, **settings)

    def baseline(self, method: str = "airpls", **settings: Any) -> "SpectrumCollection":
        """Subtract the baseline from every spectrum. See ``spectrum_toolkit.baseline.baseline``."""
        from .baseline import baseline
        return baseline(self, method, **settings)

    def smooth(self, method: str = "savgol", **settings: Any) -> "SpectrumCollection":
        """Reduce noise in every spectrum. See ``spectrum_toolkit.smooth.smooth``."""
        from .smooth import smooth
        return smooth(self, method, **settings)

    def normalize(self, method: str = "snv", **settings: Any) -> "SpectrumCollection":
        """Put every spectrum's intensity on a comparable scale. See ``spectrum_toolkit.normalize.normalize``."""
        from .normalize import normalize
        return normalize(self, method, **settings)

    def derivative(self, method: str = "savgol", **settings: Any) -> "SpectrumCollection":
        """First or second derivative of every spectrum. See ``spectrum_toolkit.derivative.derivative``."""
        from .derivative import derivative
        return derivative(self, method, **settings)

    def plot(self, kind: str = "lines", **settings: Any):
        """Draw the spectra with matplotlib; returns the Axes. See ``spectrum_toolkit.plot.plot``."""
        from .plot import plot
        return plot(self, kind=kind, **settings)

    def apply(self, recipe: Any, verbose: bool = False) -> "SpectrumCollection":
        """Apply a Recipe to every spectrum (or a recipe .json file). See ``spectrum_toolkit.recipe``."""
        from .recipe import apply
        return apply(self, recipe, verbose)

    # ----- groups (the work is done in groups.py) -----
    def set_groups(self, groups: Any = None, *, pattern: str | None = None,
                   rename: dict | None = None) -> "SpectrumCollection":
        """Say which group (sample) each spectrum belongs to. See ``spectrum_toolkit.groups.set_groups``."""
        from .groups import set_groups
        return set_groups(self, groups, pattern=pattern, rename=rename)

    def suggest_groups(self) -> dict:
        """Propose groups from the files or the names, without setting them. See ``groups.suggest_groups``."""
        from .groups import suggest_groups
        return suggest_groups(self)

    def by_group(self) -> dict:
        """One collection per group, in the order the groups first appear. See ``groups.by_group``."""
        from .groups import by_group
        return by_group(self)

    @property
    def group_names(self) -> list[str]:
        """The groups, in the order they first appear ("" = spectra in no group)."""
        return list(dict.fromkeys(self.groups))

    @property
    def n_points(self) -> int:
        """Number of points in each spectrum (length of the shared x axis)."""
        return self.x.size

    # classmethod: called on the class itself, SpectrumCollection.from_spectra(...),
    # as an alternative way to create a collection.
    @classmethod
    def from_spectra(cls, spectra: list[Spectrum]) -> "SpectrumCollection":
        """Stack spectra that already share the same x axis into one collection."""
        if not spectra:
            raise ValueError("No spectra given.")
        # Use the first spectrum's x axis as the reference.
        x = spectra[0].x
        for s in spectra[1:]:
            # Same number of points AND the same values (allowing tiny rounding
            # differences), otherwise the rows would not line up.
            if s.x.shape != x.shape or not np.allclose(s.x, x):
                raise ValueError(f"{s.name!r} has a different x axis; resample before stacking.")
        first = spectra[0]
        # vstack puts the y arrays on top of each other: one row per spectrum.
        return cls(x, np.vstack([s.y for s in spectra]), names=tuple(s.name for s in spectra),
                   x_unit=first.x_unit, y_unit=first.y_unit, groups=tuple(s.group for s in spectra))
