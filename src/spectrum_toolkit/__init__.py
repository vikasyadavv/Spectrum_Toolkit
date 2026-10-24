"""Spectrum Toolkit: load, process and plot spectroscopic data."""

from .core import Spectrum, SpectrumCollection
from .baseline import baseline, find_baseline
from .despike import despike
from .smooth import smooth
from .normalize import normalize
from .derivative import derivative
from .edit import check_axes, combine, cut, drop, resample, select, trim
from .groups import by_group, set_groups, suggest_groups
from .io import load, mat_variables
from .example import example
from .recipe import Recipe, apply
from .plot import compare, line_colors, panels, plot, scatter
from .style import export, get_style, save_style, set_style, style_file, to_rgba

__version__ = "0.0.1"
__all__ = ["Spectrum", "SpectrumCollection", "load", "mat_variables", "example", "combine", "check_axes", "trim", "cut", "select", "drop", "resample", "set_groups", "suggest_groups", "by_group", "despike", "baseline", "find_baseline", "smooth", "normalize", "derivative", "plot", "panels", "compare", "scatter", "line_colors", "export", "get_style", "set_style", "save_style", "style_file", "to_rgba", "Recipe", "apply"]
