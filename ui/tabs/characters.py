"""Character sheet generator tab."""

from __future__ import annotations

import gradio as gr

from comfy.client import ComfyUIError
from config import get_settings
from generators import character_sheet
from library import characters as character_store
from ui.components import connection_banner


def _on_generate(description: str, height_cm: float, width: int, height: int, seed_input: int | None):
    settings = get_settings()
    if not settings.is_configured():
        raise gr.Error("ComfyUI is not configured. Open the Settings tab first.")
    if not description or not description.strip():
        raise gr.Error("Enter a character description.")
    try:
        result = character_sheet.generate(
            description=description,
            width=int(width),
            height=int(height),
            seed=int(seed_input) if seed_input not in (None, "", 0) else None,
            settings=settings,
        )
    except ComfyUIError as exc:
        raise gr.Error(f"ComfyUI error: {exc}") from exc
    return (
        result.image,
        str(result.saved_path),
        int(result.seed),
        gr.update(value=result.seed),
    )


def _on_save(
    name: str,
    description: str,
    height_cm: float,
    sheet_path: str,
    seed: int,
) -> str:
    if not name or not name.strip():
        raise gr.Error("Give the character a name before saving.")
    if not sheet_path:
        raise gr.Error("Generate a sheet first.")
    character = character_store.create(
        name=name.strip(),
        description=(description or "").strip(),
        height_cm=float(height_cm) if height_cm else 170.0,
        sheet_path=sheet_path,
        seed=int(seed) if seed else None,
    )
    return f"Saved **{character.name}** to the library (id #{character.id})."


def render() -> None:
    with gr.Column():
        connection_banner()
        gr.Markdown(
            "### Character sheet\n"
            "Describe a character; the backend will produce a multi-angle "
            "turnaround sheet that later generations can reuse for consistency."
        )

        with gr.Row():
            with gr.Column(scale=1):
                description = gr.Textbox(
                    label="Character description",
                    lines=4,
                    placeholder="e.g. red-haired detective in her 30s, sharp features, freckles, determined expression",
                )
                name = gr.Textbox(label="Name", placeholder="Mara")
                height_cm = gr.Number(
                    label="Height (cm)",
                    value=170,
                    precision=0,
                    info="Used later to enforce correct scale in multi-character panels.",
                )
                with gr.Accordion("Advanced", open=False):
                    width = gr.Slider(label="Width", minimum=768, maximum=2048, step=64, value=1536)
                    height = gr.Slider(label="Height", minimum=768, maximum=2048, step=64, value=1024)
                    seed_input = gr.Number(label="Seed (blank = random)", value=None, precision=0)

                generate_btn = gr.Button("Generate sheet", variant="primary")

            with gr.Column(scale=2):
                preview = gr.Image(label="Character sheet", type="pil", height=512)
                seed_used = gr.Number(label="Seed used", precision=0, interactive=False)
                sheet_path = gr.Textbox(label="Saved to", interactive=False)
                save_btn = gr.Button("Save to library", variant="secondary")
                status = gr.Markdown()

        generate_btn.click(
            _on_generate,
            inputs=[description, height_cm, width, height, seed_input],
            outputs=[preview, sheet_path, seed_used, seed_input],
        )
        save_btn.click(
            _on_save,
            inputs=[name, description, height_cm, sheet_path, seed_used],
            outputs=status,
        )
