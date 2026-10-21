"""pytest setup shared by all tests."""

import importlib.util

# The web service module needs the optional "api" packages; without them,
# skip reading it for doctests instead of failing (pip install ".[api]").
collect_ignore = [] if importlib.util.find_spec("fastapi") else ["src/spectrum_toolkit/api.py"]
