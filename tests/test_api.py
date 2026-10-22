"""Tests for the web service (src/spectrum_toolkit/api.py), run without a
server through FastAPI's TestClient."""

import io
import json
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("matplotlib")
from fastapi.testclient import TestClient                     # noqa: E402

from spectrum_toolkit import SpectrumCollection, api          # noqa: E402

DATA = Path(__file__).parent.parent / "data"
X = np.arange(100, 1800, 1.19)
client = TestClient(api.app)


def sample(n=3, seed=0):
    """n noisy spectra with a sloping background and one band, as the JSON data format."""
    rng = np.random.default_rng(seed)
    clean = 300 + 0.3 * X + 3000 / (1 + ((X - 1000) / 6) ** 2)
    c = SpectrumCollection(X, rng.poisson(clean, (n, X.size)).astype(float), names=[f"s{i}" for i in range(n)])
    return api.to_json(c)


def text_file(n=2):
    """A two-column-per-spectrum text file in memory (x, y1, y2, ...)."""
    d = sample(n)
    rows = ["\t".join(f"{v:g}" for v in [x, *(Y[i] for Y in d["Y"])]) for i, x in enumerate(d["x"])]
    return io.BytesIO("\n".join(rows).encode())


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_options_lists_methods_and_style():
    o = client.get("/options").json()
    assert "snip" in o["steps"]["baseline"]["methods"]
    assert o["steps"]["derivative"]["methods"]["savgol"]["n"] == 1
    assert set(o["steps"]["despike"]["methods"]) == {"single", "compare", "kalkan"}
    assert o["style"]["settings"]["line_width"]["meaning"]
    assert "matlab" in o["style"]["presets"] and "tiff" in o["figure_formats"]
    json.dumps(o)                                              # everything is plain JSON


def test_json_round_trip():
    d = sample()
    back = api.to_json(api.from_json(d))
    assert np.allclose(back["Y"], d["Y"]) and back["names"] == d["names"]


def test_load_text_upload():
    r = client.post("/load", files={"file": ("two.txt", text_file(2), "text/plain")})
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert len(d["Y"]) == 2 and len(d["x"]) == X.size


def test_load_bad_file_is_422():
    r = client.post("/load", files={"file": ("junk.txt", io.BytesIO(b"hello\nworld\n"), "text/plain")})
    assert r.status_code == 422 and r.json()["detail"]


def test_load_empty_file_is_422():
    r = client.post("/load", files={"file": ("empty.txt", io.BytesIO(b""), "text/plain")})
    assert r.status_code == 422 and "empty" in r.json()["detail"]


def test_upload_limit(monkeypatch):
    monkeypatch.setattr(api, "MAX_UPLOAD", 1000)
    r = client.post("/load", files={"file": ("big.txt", io.BytesIO(b"1 2\n" * 1000), "text/plain")})
    assert r.status_code == 413


def test_process_and_all_steps():
    steps = [{"step": "baseline", "method": "snip"}, {"step": "normalize", "method": "snv"}]
    r = client.post("/process", json={"data": sample(), "recipe": {"steps": steps}, "all_steps": True})
    assert r.status_code == 200, r.text
    out = r.json()
    assert [s["step"] for s in out["steps"]] == ["start", "baseline", "normalize"]
    Y = np.array(out["data"]["Y"])
    assert np.allclose(Y.mean(axis=1), 0, atol=1e-9)           # SNV: mean 0 per spectrum
    assert out["data"]["history"][-1]["step"] == "normalize"


def test_process_unknown_method_is_422():
    r = client.post("/process", json={"data": sample(), "recipe": {"steps": [{"step": "smooth", "method": "nope"}]}})
    assert r.status_code == 422 and "nope" in r.json()["detail"]


def test_process_missing_data_is_422():
    r = client.post("/process", json={"recipe": {"steps": []}})
    assert r.status_code == 422


def test_process_file():
    recipe = json.dumps({"steps": [{"step": "trim", "lo": 200, "hi": 1700}]})
    r = client.post("/process-file", files={"file": ("two.txt", text_file(2), "text/plain")}, data={"recipe": recipe})
    assert r.status_code == 200, r.text
    x = np.array(r.json()["data"]["x"])
    assert x.min() >= 200 and x.max() <= 1700
    r = client.post("/process-file", files={"file": ("two.txt", text_file(2), "text/plain")},
                    data={"recipe": recipe, "summary_only": "true"})
    d = r.json()["data"]
    assert d["Y"] is None and d["history"][-1]["step"] == "trim"     # sizes and history, no numbers
    assert list(r.json())[0] == "kind"                                # ready to paste into /figure


@pytest.mark.parametrize("fmt,magic", [("png", b"\x89PNG"), ("tiff", b"II*\x00"), ("pdf", b"%PDF"),
                                        ("svg", b"<?xml"), ("jpg", b"\xff\xd8")])
def test_figure_formats(fmt, magic):
    r = client.post("/figure", json={"data": sample(), "kind": "lines", "style": "publication",
                                     "format": fmt, "dpi": 100, "name": "my fig"})
    assert r.status_code == 200, r.text
    assert r.content.startswith(magic)
    assert f'my_fig.{fmt}' in r.headers["content-disposition"]


def test_figure_settings_and_extras():
    r = client.post("/figure", json={"data": sample(), "kind": "stack", "style": "matlab",
                                     "settings": {"line_width": 2, "grid": True}, "marks": {"1000": "band"},
                                     "title": "t", "format": "png", "dpi": 80})
    assert r.status_code == 200, r.text


def test_figure_per_side_settings_and_wrong_value():
    """Per-side style settings arrive from the website as JSON; a wrong value is a clear 422."""
    settings = {"box": "closed", "top_tick_length": 9, "x_tick_direction": "in", "left_tick_label_color": "cmyk(0, 1, 1, 0)",
                "xlabel_italic": True, "title_location": "left", "legend": True, "legend_box": True,
                "legend_fill": [255, 255, 200], "legend_columns": 2, "tick_sides": ["bottom", "top", "left"]}
    r = client.post("/figure", json={"data": sample(), "title": "t", "settings": settings, "format": "png", "dpi": 60})
    assert r.status_code == 200, r.text
    r = client.post("/figure", json={"data": sample(), "settings": {"top_tick_alpha": 5}})
    assert r.status_code == 422 and "top_tick_alpha" in r.json()["detail"]


def test_figure_wrong_highlight_is_422():
    r = client.post("/figure", json={"data": sample(), "highlight": 0})
    assert r.status_code == 422 and "highlight must be" in r.json()["detail"]


def test_figure_bad_format_is_422():
    r = client.post("/figure", json={"data": sample(), "format": "bmp"})
    assert r.status_code == 422 and "bmp" in r.json()["detail"]


def test_cors_allows_the_website_only():
    ok = client.options("/process", headers={"Origin": "https://cheminations.com",
                                              "Access-Control-Request-Method": "POST"})
    assert ok.headers.get("access-control-allow-origin") == "https://cheminations.com"
    bad = client.options("/process", headers={"Origin": "https://example.com",
                                               "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in bad.headers


@pytest.mark.skipif(not (DATA / "CV10-4M.xlsx").exists(), reason="real data files are local only")
def test_load_real_excel():
    with (DATA / "CV10-4M.xlsx").open("rb") as f:
        r = client.post("/load", files={"file": ("CV10-4M.xlsx", f)})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["data"] or body["separate"]


def test_load_placeholder_and_empty_boxes():
    """The /docs page fills unused boxes with "string" (or sends them empty): a clear 422, or ignored."""
    r = client.post("/load", files={"file": ("two.txt", text_file(2), "text/plain")}, data={"layout": "string"})
    assert r.status_code == 422                                # not one of the choices
    r = client.post("/load", files={"file": ("two.txt", text_file(2), "text/plain")}, data={"sheet": "", "layout": "auto"})
    assert r.status_code == 200, r.text
    r = client.post("/load", files={"file": ("two.txt", text_file(2), "text/plain")}, data={"layout": "shared"})
    assert r.status_code == 200, r.text


def test_unexpected_error_is_explained(monkeypatch):
    """A bug answers 500 with its message instead of a bare "Internal Server Error"."""
    def broken(*args, **kwargs):
        raise KeyError("oops")
    monkeypatch.setattr(api, "load", broken)
    r = TestClient(api.app, raise_server_exceptions=False).post(
        "/load", files={"file": ("two.txt", text_file(2), "text/plain")})
    assert r.status_code == 500 and "KeyError" in r.json()["detail"]


def test_load_answer_always_has_the_same_fields():
    """Sizes first (like MATLAB size), the same keys for every file; summary_only leaves out the numbers."""
    keys = ["n_spectra", "n_points", "size_Y", "size_x", "x_range", "names", "x_unit", "y_unit",
            "notes", "history", "x", "Y"]
    r = client.post("/load", files={"file": ("two.txt", text_file(2), "text/plain")}).json()
    assert list(r) == ["data", "separate", "message"] and list(r["data"]) == keys
    assert r["data"]["size_Y"] == [2, X.size] and r["data"]["size_x"] == [X.size] and len(r["data"]["Y"]) == 2
    r = client.post("/load", files={"file": ("two.txt", text_file(2), "text/plain")},
                    data={"summary_only": "true"}).json()
    assert r["data"]["x"] is None and r["data"]["Y"] is None and r["data"]["n_spectra"] == 2


def test_figure_line_settings_color_mode_and_emphasize():
    body = {"data": sample(), "format": "tiff", "emphasize": [1],
            "settings": {"line_format": ["o-", "*--"], "marker_every": 20, "line_alpha": 0.7}}
    for mode in ({"color_mode": "cmyk"}, {"color": "cmyk"}):                # new name, and the old one
        r = client.post("/figure", json={**body, **mode})
        assert r.status_code == 200
        from PIL import Image
        assert Image.open(io.BytesIO(r.content)).mode == "CMYK"
    r = client.post("/figure", json={"data": sample(), "color_mode": "red"})
    assert r.status_code == 422 and "line_color" in r.json()["detail"]      # points to where line colours go
    r = client.post("/figure", json={"data": sample(), "emphasize": [9]})
    assert r.status_code == 422 and "emphasize" in r.json()["detail"]


def test_figure_marks_and_highlight_with_own_settings():
    body = {"data": sample(), "peaks": 2, "marks": {"1000": {"label": "C=C", "color": "red"}},
            "highlight": [{"range": [980, 1020], "label": "band", "hatch": "//"}],
            "settings": {"peak_line": True, "peak_label_pad": 15, "mark_span": "peak", "highlight_label_box": True}}
    assert client.post("/figure", json=body).status_code == 200
    r = client.post("/figure", json={**body, "marks": {"1000": {"colour": "red"}}})
    assert r.status_code == 422 and "marks" in r.json()["detail"]


def test_figure_notes_inset_and_panels():
    body = {"data": sample(), "notes": [{"text": "here", "x": 1000, "y": 0.5, "arrow": [1000, 1]}],
            "inset": [950, 1050]}
    r = client.post("/figure", json=body)
    assert r.status_code == 200 and "x-warning" not in r.headers
    panels = {"panels": [{"data": sample(), "kind": "stack", "peaks": 1, "settings": {"line_width": 2}},
                         {"data": sample(2), "kind": "mean", "marks": {"1000": "M"}, "letter": "(z)"}],
              "layout": [1, 2], "share_y": True, "title": "Both"}
    assert client.post("/figure", json=panels).status_code == 200
    r = client.post("/figure", json={"panels": [{"data": sample(), "settings": {"nonsense": 1}}]})
    assert r.status_code == 422 and "Panel 1" in r.json()["detail"]
    r = client.post("/figure", json={"panels": "two"})
    assert r.status_code == 422


def test_figure_warns_about_missing_fonts():
    r = client.post("/figure", json={"data": sample(), "settings": {"font": "No Such Font"}},
                    headers={"Origin": "https://cheminations.com"})
    assert r.status_code == 200 and "No Such Font" in r.headers["x-warning"]
    assert "x-warning" in r.headers["access-control-expose-headers"].lower()


def test_figure_panels_layout_text_and_shared_parts():
    body = {"panels": [{"data": sample()}, {"data": sample(), "region": [950, 1050]}, {"data": sample(), "kind": "image"}],
            "layout": "AA;BC", "heights": [2, 1], "xlabel": "Raman shift", "title": "T",
            "settings": {"panel_legend": "figure top", "panel_shared_labels": True, "panel_spacing_y": 0.1}}
    assert client.post("/figure", json=body).status_code == 200
    r = client.post("/figure", json={**body, "layout": "AB;BA"})
    assert r.status_code == 422 and "rectangle" in r.json()["detail"]


def test_style_check_answers_every_setting_and_what_changed(tmp_path):
    from spectrum_toolkit import style
    r = client.post("/style-check", json={"style": "publication", "settings": {"line_width": 2, "font": "No Such Font"}})
    assert r.status_code == 200
    answer = r.json()
    assert set(answer["style"]) == set(style.SETTINGS) | {"preset"}           # every setting, ready to save
    assert answer["changed"]["line_width"] == 2 and answer["changed"]["box_width"] == 1.0   # from the preset
    assert "x_range" not in answer["changed"]
    assert "No Such Font" in answer["warnings"][0]
    saved = style.save_style({"preset": "matlab", "grid": False}, tmp_path / "mine")  # a file the user saved
    again = client.post("/style-check", json={"style": json.loads(saved.read_text())}).json()
    assert again["changed"]["grid"] is False and again["changed"]["font"] == "Arial"   # from the matlab preset
    assert client.post("/style-check", json={}).json()["changed"] == {}         # nothing asked: the defaults
    assert client.post("/style-check", json={"style": "matplotlib"}).json()["style"] == {"preset": "matplotlib"}


def test_style_check_style_draws_the_same_figure():
    asked = {"style": "matlab", "settings": {"line_width": 2.5, "legend_box": True}}
    full = client.post("/style-check", json=asked).json()["style"]
    first = client.post("/figure", json={"data": sample(), **asked, "dpi": 50}).content
    second = client.post("/figure", json={"data": sample(), "style": full, "dpi": 50}).content
    assert first == second


def test_style_check_wrong_settings_and_no_files():
    r = client.post("/style-check", json={"settings": {"line_width": "thick"}})
    assert r.status_code == 422 and "line_width" in r.json()["detail"]
    r = client.post("/style-check", json={"style": {"nonsense": 1}})
    assert r.status_code == 422 and "nonsense" in r.json()["detail"]
    for where in ("/style-check", "/figure"):                                  # a file path is never opened
        r = client.post(where, json={"data": sample(), "style": "/etc/anything.json"})
        assert r.status_code == 422 and "preset name" in r.json()["detail"]
