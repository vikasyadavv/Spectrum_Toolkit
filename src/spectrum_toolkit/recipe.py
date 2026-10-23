"""Recipes: a processing chain saved as a file and re-applied in one line.

A recipe is a list of steps with their settings, e.g. despike → trim →
baseline → smooth → normalize. Process one data set the way you like,
turn what you did into a recipe, save it, and apply it to every new file:

>>> import numpy as np
>>> from spectrum_toolkit import Recipe, Spectrum
>>> x = np.arange(100.0, 1800.0, 1.2)
>>> raw = Spectrum(x, 500 + 0.1 * x + 900 * np.exp(-((x - 1000) / 8) ** 2))
>>> done = raw.trim(200, 1700).baseline().normalize("max")
>>> recipe = Recipe.from_history(done)              # what was done to `done`
>>> print(recipe)
Recipe (3 steps)
  1. trim: lo=200, hi=1700
  2. baseline: airpls, lam=1e+06, max_iter=50, tol=0.001
  3. normalize: max
>>> again = recipe.apply(raw)                       # the same chain on any data
>>> bool(np.allclose(again.y, done.y))
True

Three ways to make one:

- ``Recipe.from_history(data)``: from processed data (steps that cannot be
  repeated on other data, such as select/drop by name, are left out and
  listed in ``recipe.skipped``).
- Step by step: ``Recipe().despike().trim(200, 1800).baseline("asls", lam=1e5)``
  (each call returns a new recipe; settings are checked straight away).
- ``Recipe.load("my_recipe.json")`` after ``recipe.save("my_recipe.json")``.

Apply with ``recipe.apply(data)``, ``data.apply(recipe)`` or on a file:
``recipe.apply("new_sample.xlsx")`` (loads it first). ``recipe.run(data)``
returns the data after every step, for before/after plots.

The JSON file is plain text, readable and editable by hand; it records the
toolkit version that wrote it. Steps whose settings are wrong for the
installed version give a clear error when the recipe is loaded.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

from .core import Spectrum, SpectrumCollection

Data = Spectrum | SpectrumCollection

# Steps a recipe can hold, in the order the methods are listed.
STEPS = ("trim", "cut", "despike", "baseline", "smooth", "normalize", "derivative", "resample")

# Keys in a history entry that are results, not settings; dropped when repeating.
_RESULTS = {"despike": {"spikes"}, "trim": {"points_removed"}, "cut": {"points_removed"},
            "derivative": {"regridded"}}

# Settings of each despike method (despike has one signature for all methods).
_DESPIKE = {"single": {"threshold", "width", "sharpness", "grow", "passes"},
            "compare": {"threshold", "width", "grow"},
            "kalkan": {"window", "nstd", "ndata", "nbins", "passes"}}


def _check_step(step: dict) -> dict:
    """Return a clean copy of one step, or raise a clear error if it cannot be run."""
    step = dict(step)
    name = step.get("step")
    if name not in STEPS:
        raise ValueError(f"Unknown recipe step {name!r}. Recipes can hold: {', '.join(STEPS)}.")
    for key in _RESULTS.get(name, ()):
        step.pop(key, None)
    settings = {k: v for k, v in step.items() if k not in ("step", "method")}
    method = step.get("method")
    if name in ("trim", "cut"):
        if not settings or not set(settings) <= {"lo", "hi"}:
            raise ValueError(f"{name} takes lo and/or hi (a missing one means no limit), got {sorted(settings)}.")
        step = {"step": name, "lo": settings.get("lo"), "hi": settings.get("hi")}    # missing end = None
    elif name == "resample":
        if "x" not in settings:
            raise ValueError("resample needs the new axis x (a list of numbers).")
        from .edit import METHODS as RESAMPLE
        if method is not None and method not in RESAMPLE:
            raise ValueError(f"Unknown resample method {method!r}. Choose one of: {', '.join(RESAMPLE)}.")
        step["x"] = [float(v) for v in settings["x"]]
    elif name == "despike":
        method = method or "single"
        if method not in _DESPIKE:
            raise ValueError(f"Unknown despike method {method!r}. Choose one of: {', '.join(_DESPIKE)}.")
        wrong = set(settings) - _DESPIKE[method]
        if wrong:
            raise ValueError(f"despike {method!r} has no setting {sorted(wrong)}; it has {sorted(_DESPIKE[method])}.")
        # Store every setting, defaults included, so the recipe gives the same
        # result even if a later version changes a default.
        import inspect
        from .despike import despike
        defaults = {k: p.default for k, p in inspect.signature(despike).parameters.items() if k in _DESPIKE[method]}
        step = {"step": name, "method": method, **defaults, **settings}
    else:
        module = __import__(f"spectrum_toolkit.{name}", fromlist=["_settings", "DEFAULTS"])
        method = method or {"baseline": "airpls", "smooth": "savgol", "normalize": "snv",
                            "derivative": "savgol"}[name]
        if name == "normalize" and settings.get("reference") == "given":
            raise ValueError("This normalize step used a reference spectrum that was not saved with it. "
                             "Give the reference as numbers: Recipe().normalize('msc', reference=[...]).")
        # Raises a clear error for wrong settings, and returns every setting with
        # defaults filled in: stored, so the recipe gives the same result even if
        # a later version changes a default.
        full = module._settings(method, settings)
        step = {"step": name, "method": method, **full}
    return step


def _limits(lo: float | None, hi: float | None) -> dict:
    """lo and hi as numbers in increasing order; None stays None (open end)."""
    if lo is not None and hi is not None and lo > hi:
        lo, hi = hi, lo
    return {"lo": None if lo is None else float(lo), "hi": None if hi is None else float(hi)}


def _run_step(data: Data, step: dict, verbose: bool) -> Data:
    """Apply one checked step to the data."""
    settings = {k: v for k, v in step.items() if k not in ("step", "method")}
    name, method = step["step"], step.get("method")
    if name in ("trim", "cut"):
        return getattr(data, name)(settings["lo"], settings["hi"])
    if name == "resample":
        from .edit import resample
        return resample(data, np.asarray(settings["x"]), method or "linear")
    if name == "despike":
        return data.despike(method, verbose=verbose, **settings)
    if name == "normalize" and settings.get("reference") is not None:
        settings["reference"] = np.asarray(settings["reference"], dtype=float)
    return getattr(data, name)(method, **settings)


def _short(v: Any) -> str:
    """Compact text for one setting value."""
    if isinstance(v, float):
        return f"{v:g}"
    if isinstance(v, (list, tuple)) and len(v) > 4:
        return f"[{len(v)} values]"
    return str(v)


class Recipe:
    """An ordered list of processing steps with their settings.

    Parameters
    ----------
    steps : list of dicts like {"step": "baseline", "method": "airpls", "lam": 1e6}.
    name, description : free text, saved in the file.
    """

    def __init__(self, steps: list[dict] | None = None, name: str = "", description: str = ""):
        self.steps = [_check_step(s) for s in (steps or [])]
        self.name = name
        self.description = description
        self.skipped: list[str] = []                           # steps from_history could not keep

    # ------------------------------------------------------------ building
    def add(self, step: str, method: str | None = None, **settings: Any) -> "Recipe":
        """A new recipe with one more step (the original is unchanged)."""
        entry = {"step": step, **({"method": method} if method else {}), **settings}
        new = Recipe(self.steps + [entry], self.name, self.description)
        return new

    def trim(self, lo: float | None, hi: float | None) -> "Recipe":
        """Add: keep lo <= x <= hi (None: no limit on that side)."""
        return self.add("trim", **_limits(lo, hi))

    def cut(self, lo: float | None, hi: float | None) -> "Recipe":
        """Add: remove lo <= x <= hi (None: no limit on that side)."""
        return self.add("cut", **_limits(lo, hi))

    def despike(self, method: str = "single", **settings: Any) -> "Recipe":
        """Add: cosmic-ray removal (see spectrum_toolkit.despike)."""
        return self.add("despike", method, **settings)

    def baseline(self, method: str = "airpls", **settings: Any) -> "Recipe":
        """Add: baseline subtraction (see spectrum_toolkit.baseline)."""
        return self.add("baseline", method, **settings)

    def smooth(self, method: str = "savgol", **settings: Any) -> "Recipe":
        """Add: smoothing (see spectrum_toolkit.smooth)."""
        return self.add("smooth", method, **settings)

    def normalize(self, method: str = "snv", **settings: Any) -> "Recipe":
        """Add: normalisation (see spectrum_toolkit.normalize)."""
        if "reference" in settings and settings["reference"] is not None:
            ref = settings["reference"]
            settings["reference"] = [float(v) for v in (ref.y if isinstance(ref, Spectrum) else ref)]
        return self.add("normalize", method, **settings)

    def derivative(self, method: str = "savgol", **settings: Any) -> "Recipe":
        """Add: 1st or 2nd derivative (see spectrum_toolkit.derivative)."""
        return self.add("derivative", method, **settings)

    def resample(self, x, method: str = "linear") -> "Recipe":
        """Add: put the data on the axis x (see spectrum_toolkit.edit.resample)."""
        return self.add("resample", method, x=[float(v) for v in np.asarray(x)])

    @classmethod
    def from_history(cls, data: Data, name: str = "", description: str = "") -> "Recipe":
        """The recipe of everything done to data that can be repeated on other data.

        Loading, combining, select/drop (by name) and resampling (needs the
        axis) are not kept; they are listed in ``recipe.skipped``.
        """
        why = {"select": "picks spectra by name; other data has other names",
               "drop": "removes spectra by name; other data has other names",
               "combine": "joins files; combine the new files first, then apply the recipe",
               "resample": "needs the target axis; add it with Recipe().resample(x)"}
        steps, skipped = [], []
        for entry in data.history:
            kind = entry.get("step", "?")
            if kind in why:
                skipped.append(f"{kind}: {why[kind]}")
                continue
            try:
                steps.append(_check_step(entry))
            except ValueError as e:
                skipped.append(f"{kind}: {e}")
        recipe = cls(steps, name, description)
        recipe.skipped = skipped
        return recipe

    # ------------------------------------------------------------ using
    def apply(self, data: Data | str | Path, verbose: bool = False, load_options: dict | None = None) -> Data:
        """Apply every step in order; data may be a Spectrum, a collection or a file path.

        load_options : settings for loading a file path, e.g. ``{"x": "W", "y": "wt"}`` for a .mat file
            (any keyword of ``stk.load``).
        """
        return self.run(data, verbose, load_options)[-1][1]

    def run(self, data: Data | str | Path, verbose: bool = False,
            load_options: dict | None = None) -> list[tuple[str, Data]]:
        """Apply every step and keep each result: [("start", data), ("trim", ...), ...].

        Useful for before/after plots of each step: ``stk.compare(r[1][1], r[2][1])``.
        load_options : as in ``apply``.
        """
        if isinstance(data, (str, Path)):
            from .io import load
            data = load(data, verbose=verbose, **(load_options or {}))
            if isinstance(data, list):
                # Spectra with their own x columns: join them when they share the x
                # values (gaps allowed, nothing interpolated); otherwise ask the user.
                from .edit import combine
                try:
                    data = combine(*data, verbose=verbose)
                except ValueError as e:
                    raise ValueError("The file holds spectra with different x axes. Combine them first, "
                                     "choosing how to interpolate (stk.combine(..., interpolate=True)), "
                                     f"then apply the recipe. ({e})") from e
        results = [("start", data)]
        for i, step in enumerate(self.steps, start=1):
            try:
                data = _run_step(data, step, verbose)
            except Exception as e:                              # say which step failed
                raise type(e)(f"Recipe step {i} ({self._line(step)}) failed: {e}") from e
            results.append((step["step"], data))
        return results

    # ------------------------------------------------------------ saving
    def to_dict(self) -> dict:
        """Plain data (for JSON)."""
        from . import __version__
        return {"recipe": self.name, "description": self.description, "created": date.today().isoformat(),
                "spectrum_toolkit": __version__, "steps": self.steps}

    def save(self, path: str | Path) -> Path:
        """Write the recipe to a JSON file (".json" added if missing)."""
        path = Path(path)
        if path.suffix != ".json":
            path = path.with_suffix(".json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: str | Path) -> "Recipe":
        """Read a recipe written by save (settings are checked)."""
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(d.get("steps", []), d.get("recipe", ""), d.get("description", ""))

    # ------------------------------------------------------------ display
    @staticmethod
    def _line(step: dict) -> str:
        settings = ", ".join(f"{k}={_short(v)}" for k, v in step.items()
                             if k not in ("step", "method") and v is not None)
        parts = [p for p in (step.get("method"), settings) if p]
        return f"{step['step']}: {', '.join(parts)}" if parts else step["step"]

    def __str__(self) -> str:
        head = f"Recipe{' ' + repr(self.name) if self.name else ''} ({len(self.steps)} step{'s' * (len(self.steps) != 1)})"
        lines = [head] + [f"  {i}. {self._line(s)}" for i, s in enumerate(self.steps, start=1)]
        if self.skipped:
            lines += ["  not kept:"] + [f"    - {s}" for s in self.skipped]
        return "\n".join(lines)

    __repr__ = __str__

    def __len__(self) -> int:
        return len(self.steps)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Recipe) and self.steps == other.steps


def apply(data: Data | str | Path, recipe: Recipe | str | Path, verbose: bool = False) -> Data:
    """Apply a recipe (object or JSON file) to data or a file."""
    if not isinstance(recipe, Recipe):
        recipe = Recipe.load(recipe)
    return recipe.apply(data, verbose)


__all__ = ["Recipe", "apply", "STEPS"]
