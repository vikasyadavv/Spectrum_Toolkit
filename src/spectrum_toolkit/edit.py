"""Editing data: trim, cut, pick spectra, and combine spectra from many files.

Every function returns a NEW object and records what it did in ``history``;
the original is never changed.

- ``trim(s, lo, hi)``  keep only x between lo and hi.
- ``cut(s, lo, hi)``   remove x between lo and hi (e.g. a laser line).
- ``select(c, ...)``   keep some spectra of a collection, by number or name.
- ``drop(c, ...)``     remove some spectra of a collection.
- ``check_axes(...)``  compare the x axes of several spectra (are they the same?).
- ``combine(...)``     put spectra from several files into one collection.

The same operations are available as methods: ``s.trim(500, 1800)``,
``c.drop("3")`` and so on.

>>> from spectrum_toolkit import Spectrum
>>> s = Spectrum([100, 200, 300, 400], [1, 2, 3, 4])
>>> trim(s, 150, 350).x
array([200., 300.])
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

from .core import Spectrum, SpectrumCollection

Data = Spectrum | SpectrumCollection


# ------------------------------------------------------------------ helpers
def _range(lo: float | None, hi: float | None) -> tuple[float, float]:
    """Return (lo, hi) in increasing order, so trim(1800, 500) also works.
    None means "no limit on that side": trim(450, None) keeps everything from 450 up."""
    lo = -np.inf if lo is None else lo                # open end: no lower limit
    hi = np.inf if hi is None else hi                 # open end: no upper limit
    return (lo, hi) if lo <= hi else (hi, lo)


def _apply_mask(data: Data, keep: np.ndarray, step: str, **params: Any) -> Data:
    """Keep the x points where ``keep`` is True; record the step in history."""
    if keep.sum() < 2:
        raise ValueError(f"{step} would leave {int(keep.sum())} point(s); a spectrum needs at least 2. "
                         f"x runs from {data.x.min():.6g} to {data.x.max():.6g}.")
    entry = {"step": step, **params, "points_removed": int((~keep).sum())}
    if isinstance(data, Spectrum):
        return data.copy_with(x=data.x[keep], y=data.y[keep], history=data.history + (entry,))
    return data.copy_with(x=data.x[keep], Y=data.Y[:, keep], history=data.history + (entry,))


# ------------------------------------------------------------- trim and cut
def trim(data: Data, lo: float | None, hi: float | None) -> Data:
    """Keep only the points with lo <= x <= hi. Either end may be None (no limit).

    Works on a Spectrum or a whole SpectrumCollection.

    >>> s = Spectrum([100, 200, 300, 400], [1, 2, 3, 4])
    >>> trim(s, 200, 300).y
    array([2., 3.])
    >>> trim(s, 250, None).y                          # from 250 to the end
    array([3., 4.])
    """
    lo, hi = _range(lo, hi)
    keep = (data.x >= lo) & (data.x <= hi)            # True inside the range
    return _apply_mask(data, keep, "trim", **_limits(lo, hi))


def cut(data: Data, lo: float | None, hi: float | None) -> Data:
    """Remove the points with lo <= x <= hi, e.g. a laser line or a bad region.

    The points are removed, not set to zero, so the x axis has a gap there.

    >>> s = Spectrum([100, 200, 300, 400], [1, 2, 3, 4])
    >>> cut(s, 150, 250).x
    array([100., 300., 400.])
    """
    lo, hi = _range(lo, hi)
    keep = ~((data.x >= lo) & (data.x <= hi))         # True outside the range
    return _apply_mask(data, keep, "cut", **_limits(lo, hi))


def _limits(lo: float, hi: float) -> dict:
    """History values: the limits in increasing order, with an open end kept as None
    (JSON has no infinity, and None replays the same way in a recipe)."""
    return {"lo": None if np.isinf(lo) else lo, "hi": None if np.isinf(hi) else hi}


# --------------------------------------------------------- select and drop
def _positions(c: SpectrumCollection, keys: Sequence[int | str]) -> list[int]:
    """Turn numbers (0 = first, -1 = last) and names into row numbers."""
    rows = []
    for k in keys:
        if isinstance(k, str):                        # a name, e.g. "Spot2"
            if k not in c.names:
                raise ValueError(f"No spectrum named {k!r}. Names: {list(c.names)}.")
            rows.append(c.names.index(k))
        else:                                         # a number, as in c[0]
            if not -len(c) <= k < len(c):
                raise ValueError(f"Spectrum number {k} does not exist; there are {len(c)} (0 to {len(c) - 1}).")
            rows.append(k % len(c))                   # -1 -> last row
    return rows


def _pick(c: SpectrumCollection, rows: list[int], step: str, keys: Sequence) -> SpectrumCollection:
    """A collection with only the given rows, in the given order."""
    if not rows:
        raise ValueError(f"{step} would leave no spectra.")
    return c.copy_with(
        Y=c.Y[rows],
        names=tuple(c.names[r] for r in rows),
        positions=None if c.positions is None else c.positions[rows],   # map coordinates follow their spectra
        groups=tuple(c.groups[r] for r in rows) if c.groups else (),    # so do groups
        history=c.history + ({"step": step, "spectra": [c.names[r] for r in rows] if step == "select" else list(keys)},),
    )


def select(c: SpectrumCollection, *keys: int | str) -> SpectrumCollection:
    """Keep only the named or numbered spectra (0 = first), in the order given.

    >>> c = SpectrumCollection([1, 2], [[1, 1], [2, 2], [3, 3]], names=["a", "b", "c"])
    >>> select(c, "c", 0).names
    ('c', 'a')
    """
    return _pick(c, _positions(c, keys), "select", keys)


def drop(c: SpectrumCollection, *keys: int | str) -> SpectrumCollection:
    """Remove the named or numbered spectra (0 = first).

    >>> c = SpectrumCollection([1, 2], [[1, 1], [2, 2], [3, 3]], names=["a", "b", "c"])
    >>> drop(c, "b").names
    ('a', 'c')
    """
    gone = set(_positions(c, keys))
    names = [c.names[r] for r in sorted(gone)]
    return _pick(c, [r for r in range(len(c)) if r not in gone], "drop", names)


# ------------------------------------------------------- comparing x axes
@dataclass
class AxisReport:
    """How the x axes of several spectra compare. Printing it gives a table.

    Attributes
    ----------
    case : "same"       all x axes are identical;
           "same grid"  every x value is one of the same set of values, but
                        some spectra are longer or have points missing
                        (combining keeps the x values all of them have;
                        no number is changed);
           "different"  the x values differ, so combining needs interpolation.
    lo, hi : the x range every spectrum covers (the overlap).
    rows : one dict per spectrum: name, points, x_from, x_to, step, overlap
        (share of its own range inside lo..hi), shift (largest distance
        between its x values and those of the spectrum with the most points,
        in x units; 0 means they match).
    reference : number of the spectrum whose x axis would be used.
    common : for "same"/"same grid", the x values present in every spectrum.
    """

    case: str
    lo: float
    hi: float
    reference: int
    rows: list[dict] = field(default_factory=list)
    common: np.ndarray | None = None

    def __str__(self) -> str:
        text = {"same": "All x axes are the same.",
                "same grid": "The x values match, but some spectra are longer or have points missing.",
                "different": "The x axes differ; combining them needs interpolation."}[self.case]
        lines = [text, f"Common range: {self.lo:.6g} to {self.hi:.6g}. Reference x: spectrum {self.reference} "
                       f"({self.rows[self.reference]['name']}).",
                 f"{'#':>3}  {'name':<28}{'points':>7}{'x from':>11}{'x to':>11}{'step':>9}{'overlap':>9}{'shift':>9}"]
        for i, r in enumerate(self.rows):
            lines.append(f"{i:>3}  {r['name'][:27]:<28}{r['points']:>7}{r['x_from']:>11.6g}{r['x_to']:>11.6g}"
                         f"{r['step']:>9.4g}{r['overlap']:>8.0%} {r['shift']:>9.3g}")
        return "\n".join(lines)


def _step(x: np.ndarray) -> float:
    """Typical distance between neighbouring x values."""
    return float(np.median(np.diff(x)))


def _nearest(values: np.ndarray, grid: np.ndarray) -> np.ndarray:
    """For each value, the position in ``grid`` (ascending) of the closest grid value."""
    idx = np.clip(np.searchsorted(grid, values), 1, grid.size - 1)     # first grid value >= each value
    # Step back one place where the grid value just below is closer.
    return np.where(np.abs(values - grid[idx - 1]) < np.abs(values - grid[idx]), idx - 1, idx)


def check_axes(spectra: Sequence[Spectrum], reference: int | str | None = None) -> AxisReport:
    """Compare the x axes of several spectra.

    Parameters
    ----------
    spectra : the spectra to compare (each with x in ascending order).
    reference : number or name of the spectrum whose x axis to use when
        interpolating. Default: the first one, unless another one has a
        clearly coarser step (more than 5 % larger); then that one, because
        interpolating coarse data onto a finer grid invents detail.
    """
    lo = max(s.x[0] for s in spectra)                 # the overlap starts at the highest start
    hi = min(s.x[-1] for s in spectra)                # ... and ends at the lowest end
    if lo >= hi:
        raise ValueError("These spectra have no x range in common, so they cannot be combined.")
    steps = [_step(s.x) for s in spectra]

    # ----- which spectrum's x axis to use
    names = [s.name for s in spectra]
    if reference is None:
        ref = 0
        if max(steps) > 1.05 * steps[0]:
            # Among the spectra with (nearly) the coarsest step, the one with
            # the most points, so a spectrum with gaps is not the reference.
            coarse = [i for i, st in enumerate(steps) if st >= 0.95 * max(steps)]
            ref = max(coarse, key=lambda i: len(spectra[i]))
    elif isinstance(reference, str):
        if reference not in names:
            raise ValueError(f"No spectrum named {reference!r}. Names: {names}.")
        ref = names.index(reference)
    else:
        ref = reference % len(spectra)

    # ----- do all x values sit on one shared set of values (a "grid")?
    # The grid is taken from the spectrum with the most points, so a spectrum
    # with a few points missing does not hide the match.
    grid = max(spectra, key=len).x
    tol = 0.01 * _step(grid)                          # "the same x" = closer than 1 % of a step
    same_grid, rows, sets = True, [], []
    for s, st in zip(spectra, steps):
        # For every x of this spectrum, the position of the nearest grid value.
        idx = _nearest(s.x, grid)
        shift = float(np.max(np.abs(s.x - grid[idx])))     # how far off the grid it is
        same_grid &= shift <= tol and np.unique(idx).size == idx.size
        sets.append(idx)
        rows.append({"name": s.name, "points": len(s), "x_from": float(s.x[0]), "x_to": float(s.x[-1]),
                     "step": st, "overlap": (hi - lo) / (s.x[-1] - s.x[0]), "shift": shift})

    common = None
    if same_grid:
        # Grid positions present in every spectrum.
        keep = sets[0]
        for idx in sets[1:]:
            keep = np.intersect1d(keep, idx)
        common = grid[keep]
        case = "same" if common.size == grid.size and all(len(s) == grid.size for s in spectra) else "same grid"
    else:
        case = "different"
    return AxisReport(case, float(lo), float(hi), ref, rows, common)


# ------------------------------------------------------------ interpolation
# The methods offered, with what each does. All of them pass exactly through
# the measured points; they differ in how they draw the curve between them.
METHODS = {
    "linear": "straight line between neighbouring points (numpy.interp). Safe default: never overshoots.",
    "quadratic": "piecewise quadratic spline (scipy make_interp_spline, k=2).",
    "cubic": "cubic spline (scipy CubicSpline): smooth curve, can overshoot next to sharp peaks.",
    "spline": "same as 'cubic' (the usual meaning of 'spline interpolation').",
    "pchip": "shape-preserving cubic (scipy PchipInterpolator): smooth, never overshoots; good for sharp peaks.",
    "akima": "Akima spline (scipy Akima1DInterpolator): smooth, little overshoot, robust to outliers.",
}


def _interp(x_new: np.ndarray, x: np.ndarray, y: np.ndarray, method: str) -> np.ndarray:
    """Values of the curve through (x, y) at x_new, drawn with the chosen method.

    x must be ascending, and x_new inside x's range (no extrapolation).
    """
    if method == "linear":
        return np.interp(x_new, x, y)
    from scipy import interpolate as si             # imported here: only needed for these methods
    if method == "quadratic":
        return si.make_interp_spline(x, y, k=2)(x_new)
    if method in ("cubic", "spline"):
        return si.CubicSpline(x, y)(x_new)
    if method == "pchip":
        return si.PchipInterpolator(x, y)(x_new)
    if method == "akima":
        return si.Akima1DInterpolator(x, y)(x_new)
    if method in ("polynomial", "poly"):
        raise ValueError("A single polynomial through a whole spectrum (hundreds of points) swings wildly "
                         "between points (Runge's phenomenon), so it is not offered. 'quadratic' and 'cubic' "
                         "are polynomials fitted piece by piece, which is the safe way to do it.")
    raise ValueError(f"Unknown interpolation method {method!r}. Choose one of: {', '.join(METHODS)}.")


def resample(data: Data, x: Sequence[float], method: str = "linear") -> Data:
    """Put a spectrum or collection onto new x values by interpolation.

    Parameters
    ----------
    x : the new x values; they must lie inside the data's x range.
    method : one of ``METHODS``: "linear" (default), "quadratic", "cubic",
        "pchip", "akima".

    >>> s = Spectrum([0, 1, 2], [0, 10, 20])
    >>> resample(s, [0.5, 1.5]).y
    array([ 5., 15.])
    """
    x_new = np.asarray(x, dtype=float)
    order = np.argsort(data.x, kind="stable")        # interpolation needs ascending x
    xs = data.x[order]
    if x_new.min() < xs[0] or x_new.max() > xs[-1]:
        raise ValueError(f"New x ({x_new.min():.6g} to {x_new.max():.6g}) goes outside the data "
                         f"({xs[0]:.6g} to {xs[-1]:.6g}); values there would be guessed, not measured.")
    entry = {"step": "resample", "method": method, "points": int(x_new.size)}
    if isinstance(data, Spectrum):
        return data.copy_with(x=x_new, y=_interp(x_new, xs, data.y[order], method), history=data.history + (entry,))
    Y = np.vstack([_interp(x_new, xs, row[order], method) for row in data.Y])
    return data.copy_with(x=x_new, Y=Y, history=data.history + (entry,))


# ----------------------------------------------------------------- combine
def _flatten(items: Iterable[Any]) -> list[tuple[Spectrum, str]]:
    """Every spectrum in the inputs, with a label saying where it came from.

    Inputs can be file paths (loaded here), Spectrum, SpectrumCollection, or
    lists of these (``load`` returns a list for x/y pairs with different x).
    """
    from .io import load                              # imported here to avoid a circular import

    out: list[tuple[Spectrum, str]] = []
    for item in items:
        if isinstance(item, (str, Path)):             # a file: load it quietly
            item = load(item, verbose=False)
        if isinstance(item, (list, tuple)):
            out += _flatten(item)
            continue
        if not isinstance(item, (Spectrum, SpectrumCollection)):
            raise TypeError(f"Cannot combine a {type(item).__name__}; give spectra, collections or file paths.")
        # The file it was loaded from, without folder and extension: "CV10-4M".
        source = Path(item.meta.get("source", "")).stem
        if isinstance(item, SpectrumCollection):
            out += [(s, source) for s in item]
        else:
            out.append((item, source or item.name))
    return out


def _unique_names(pairs: list[tuple[Spectrum, str]]) -> list[str]:
    """Names for the combined spectra.

    When the spectra come from more than one file, every name gets its file
    name in front, so "Spectrum 1" from two files becomes "CV10-4M: Spectrum 1"
    and "RhB10-4M: Spectrum 1". A file holding one spectrum gives just the
    file name.
    """
    names = [s.name or src for s, src in pairs]
    if len({src for _, src in pairs}) > 1:
        names = [f"{src}: {n}" if src and src != n else n for n, (_, src) in zip(names, pairs)]
    seen: dict[str, int] = {}
    out = []
    for n in names:                                    # still equal? number them: "a", "a (2)"
        seen[n] = seen.get(n, 0) + 1
        out.append(n if seen[n] == 1 else f"{n} ({seen[n]})")
    return out


def combine(*items: Any, interpolate: bool | str = False, reference: int | str | None = None,
            min_overlap: float = 0.9, groups: Any = None, verbose: bool = True) -> SpectrumCollection:
    """Put spectra from several files (or objects) into one collection on one x axis.

    Three situations are handled:

    1. All x axes are the same: the spectra are simply stacked.
    2. Same x values, but some spectra are longer: only the common range is
       kept; no values are changed.
    3. The x values differ slightly (another calibration, another
       instrument): this needs interpolation, which changes the numbers a
       little, so it is only done when asked with ``interpolate=True`` (or
       the name of a method, e.g. ``interpolate="pchip"``).
       Otherwise an error explains the differences (see ``check_axes``).

    Parameters
    ----------
    *items : file paths, Spectrum, SpectrumCollection, or lists of them, in
        any mix: ``combine("a.txt", "b.txt", collection)``.
    interpolate : allow case 3. ``True`` means linear interpolation; a name
        chooses the method: "linear", "quadratic", "cubic", "pchip" or
        "akima" (see ``METHODS``). Every spectrum is put on the reference x
        axis, inside the common range only (never extrapolated).
    reference : number or name of the spectrum whose x axis to use (case 3);
        see ``check_axes`` for the default.
    min_overlap : case 3 is refused if any spectrum has less than this share
        of its x range inside the common range (default 90 %), because then
        the axes are not "close" and much data would be lost.
    groups : set the groups of the result, as in ``set_groups``; "file" gives
        one group per file, e.g. combine("CV.txt", "MB.txt", groups="file").
        Default: groups the inputs already had are kept.
    verbose : print what was done.
    """
    if len(items) == 1 and isinstance(items[0], (list, tuple)):
        items = tuple(items[0])                        # combine([a, b, c]) works too
    pairs = _flatten(items)
    if len(pairs) < 2:
        raise ValueError("combine needs at least two spectra.")
    names = _unique_names(pairs)
    # Interpolation needs x in increasing order; loaded data already is.
    spectra = []
    for (s, _), n in zip(pairs, names):
        order = np.argsort(s.x, kind="stable")
        spectra.append(s.copy_with(x=s.x[order], y=s.y[order], name=n))

    report = check_axes(spectra, reference)
    ref = spectra[report.reference]
    notes = []

    if report.case == "same":
        x, Y = ref.x, np.vstack([s.y for s in spectra])
        notes.append("All x axes are the same; spectra stacked as they are.")
    elif report.case == "same grid":
        x = report.common
        # For each spectrum, take the y values at the shared x values.
        tol = 0.01 * _step(x)
        # For each spectrum, the y values at the shared x values (its x is within 1 % of a step).
        Y = np.vstack([s.y[np.abs(s.x - x[_nearest(s.x, x)]) <= tol] for s in spectra])
        dropped = sum(len(s) for s in spectra) - Y.size
        notes.append(f"Same x values, but not all spectra have all of them; kept the {len(x)} x values "
                     f"every spectrum has ({dropped} point(s) dropped in total, no values changed).")
    else:
        if not interpolate:
            raise ValueError("The x axes of these spectra are not the same, so they cannot be stacked directly.\n"
                             f"{report}\n"
                             "To put them on one x axis by interpolation, use combine(..., interpolate=True); "
                             "choose whose x axis with reference=.")
        short = [r for r in report.rows if r["overlap"] < min_overlap]
        if short:
            raise ValueError("The x ranges are too different to combine: " +
                             "; ".join(f"{r['name']} ({r['x_from']:.6g}-{r['x_to']:.6g}) has only "
                                       f"{r['overlap']:.0%} of its range in the common range" for r in short) +
                             f". Common range: {report.lo:.6g}-{report.hi:.6g}. Trim them first, or lower min_overlap.")
        method = "linear" if interpolate is True else str(interpolate)
        x = ref.x[(ref.x >= report.lo) & (ref.x <= report.hi)]
        Y = np.vstack([_interp(x, s.x, s.y, method) for s in spectra])
        worst = max(r["shift"] for r in report.rows)
        notes.append(f"x axes differ (largest shift {worst:.3g}); interpolated every spectrum ({method}) onto the x "
                     f"axis of {ref.name!r}, {len(x)} points from {x[0]:.6g} to {x[-1]:.6g}.")
        rstep = _step(ref.x)
        coarser = [r["name"] for r in report.rows if r["step"] > 1.05 * rstep]
        finer = [r for r in report.rows if r["step"] < 0.95 * rstep]
        if coarser:
            notes.append(f"Note: {', '.join(coarser)} had a coarser step than the reference; "
                         "interpolating them onto a finer grid adds no real detail.")
        if finer:
            notes.append(f"Note: {len(finer)} spectra had a finer step ({min(r['step'] for r in finer):.3g}) than the "
                         f"reference ({rstep:.3g}); their fine detail is reduced to the reference's step.")

    x_units = {s.x_unit for s, _ in pairs if s.x_unit}
    y_units = {s.y_unit for s, _ in pairs if s.y_unit}
    if len(x_units) > 1:
        notes.append(f"Different x labels in the inputs: {sorted(x_units)}; kept {ref.x_unit or sorted(x_units)[0]!r}.")

    result = SpectrumCollection(
        x, Y, names=names,
        x_unit=ref.x_unit or (sorted(x_units)[0] if x_units else ""),
        y_unit=sorted(y_units)[0] if len(y_units) == 1 else "",
        meta={"combine_notes": notes, "axis_report": report,
              "sources": [str(s.meta.get("source", "")) for s, _ in pairs]},
        groups=tuple(s.group for s, _ in pairs),                       # groups the inputs had stay

        history=({"step": "combine", "case": report.case,
                  "interpolation": ("linear" if interpolate is True else interpolate) if report.case == "different" else None,
                  "reference": ref.name, "n_spectra": len(names)},),
    )
    if groups is not None:
        from .groups import set_groups
        result = set_groups(result, groups)
    if verbose:
        print("\n".join([f"Combined: {len(result)} spectra, {result.n_points} points each, "
                         f"x {x[0]:.6g} to {x[-1]:.6g}"] + [f"  - {n}" for n in notes]))
    return result


__all__ = ["trim", "cut", "select", "drop", "check_axes", "combine", "resample", "AxisReport", "METHODS"]
