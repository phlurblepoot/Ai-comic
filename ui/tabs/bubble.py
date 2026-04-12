"""Speech bubble editor tab.

Two ways to add bubbles:

1. *Visual editor* — a Fabric.js page embedded in an iframe. Drag-and-drop,
    live preview, export flattened PNG or JSON.
2. *Server-side render* — paste a JSON layout (easily captured from the editor
    via Export JSON) and re-render deterministically with PIL. Useful for
    reproducibility, scripting, or text-only tweaks.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import gradio as gr
from PIL import Image

from bubble.renderer import render
from config import get_settings
from library import panels

_EDITOR_HTML = (Path(__file__).resolve().parent.parent.parent / "bubble" / "editor.html").read_text(encoding="utf-8")


def _panel_choices():
    return ["(upload instead)"] + [
        f"{p.id}: {p.title or f'panel #{p.id}'}" for p in panels.list_all()
    ]


def _encode_bg(image: Image.Image) -> str:
    from io import BytesIO

    buf = BytesIO()
    image.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def _build_editor_html(image: Image.Image | None) -> str:
    if image is None:
        return f'<iframe srcdoc="{_EDITOR_HTML.replace(chr(34), "&quot;")}" style="width:100%; height: 900px; border: 0;"></iframe>'
    bg = _encode_bg(image)
    # Inject the background URL into the editor page.
    injected = _EDITOR_HTML.replace(
        "const bgParam = params.get('bg');",
        f"const bgParam = {json.dumps(bg)};",
    )
    return f'<iframe srcdoc="{injected.replace(chr(34), "&quot;")}" style="width:100%; height: 900px; border: 0;"></iframe>'


def _parse_id(choice: str) -> int | None:
    if not choice or choice.startswith("("):
        return None
    try:
        return int(choice.split(":", 1)[0])
    except (ValueError, IndexError):
        return None


def _on_load_editor(panel_choice: str, uploaded: Image.Image | None):
    pid = _parse_id(panel_choice)
    if pid is not None:
        panel = next((p for p in panels.list_all() if p.id == pid), None)
        if panel and panel.image_path and Path(panel.image_path).exists():
            return _build_editor_html(Image.open(panel.image_path))
    if uploaded is not None:
        return _build_editor_html(uploaded)
    return _build_editor_html(None)


def _on_render_server_side(panel_choice: str, uploaded: Image.Image | None, layout_json: str):
    pid = _parse_id(panel_choice)
    base: Image.Image | None = None
    if pid is not None:
        panel = next((p for p in panels.list_all() if p.id == pid), None)
        if panel and panel.image_path and Path(panel.image_path).exists():
            base = Image.open(panel.image_path)
    if base is None and uploaded is not None:
        base = uploaded
    if base is None:
        raise gr.Error("Pick a saved panel or upload an image first.")

    try:
        layout = json.loads(layout_json) if layout_json.strip() else {"bubbles": []}
    except json.JSONDecodeError as exc:
        raise gr.Error(f"Invalid JSON: {exc}") from exc

    rendered = render(base, layout)
    settings = get_settings()
    out_dir = settings.assets_path / "panels" / "bubbles"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "rendered.png"
    rendered.save(out_path, format="PNG")
    return rendered, str(out_path)


def render_tab() -> None:
    with gr.Column():
        gr.Markdown(
            "### Speech bubbles\n"
            "Pick a saved panel (or upload) and either edit bubbles interactively "
            "or render a JSON layout server-side."
        )
        with gr.Row():
            panel_dd = gr.Dropdown(label="Saved panel", choices=_panel_choices(), value="(upload instead)")
            uploaded = gr.Image(label="…or upload a panel", type="pil", height=200)
            refresh_btn = gr.Button("Refresh panels")

        refresh_btn.click(lambda: gr.update(choices=_panel_choices()), outputs=panel_dd)

        with gr.Tabs():
            with gr.Tab("Visual editor"):
                load_btn = gr.Button("Load into editor", variant="primary")
                editor_html = gr.HTML()
                load_btn.click(_on_load_editor, inputs=[panel_dd, uploaded], outputs=editor_html)
                gr.Markdown(
                    "Inside the editor, *Export PNG* downloads the flattened "
                    "image; *Export JSON* copies a reproducible layout into the "
                    "text area — paste it into the **Server-side render** tab "
                    "to save a deterministic version."
                )

            with gr.Tab("Server-side render"):
                layout_json = gr.Textbox(
                    label="Bubble layout JSON",
                    lines=12,
                    placeholder='{"bubbles": [{"shape": "rounded", "x": 100, "y": 50, "width": 300, "height": 150, "text": "Hi!", "tail": {"x": 220, "y": 320}}]}',
                )
                render_btn = gr.Button("Render", variant="primary")
                preview = gr.Image(label="Preview", type="pil", height=480)
                saved = gr.Textbox(label="Saved to", interactive=False)
                render_btn.click(
                    _on_render_server_side,
                    inputs=[panel_dd, uploaded, layout_json],
                    outputs=[preview, saved],
                )


# Backwards compatible alias (app.py imports `render`).
render = render_tab
