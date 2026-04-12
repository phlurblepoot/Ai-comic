"""Scene generator tab."""

from __future__ import annotations

import gradio as gr

from comfy.client import ComfyUIError
from config import get_settings
from generators import scene as scene_gen
from library import scenes as scene_store
from ui.components import connection_banner


def _on_generate(description: str, width: int, height: int, seed_input: int | None):
    settings = get_settings()
    if not settings.is_configured():
        raise gr.Error("ComfyUI is not configured. Open the Settings tab first.")
    if not description.strip():
        raise gr.Error("Describe the scene first.")
    try:
        result = scene_gen.generate(
            description=description,
            width=int(width),
            height=int(height),
            seed=int(seed_input) if seed_input else None,
            settings=settings,
        )
    except ComfyUIError as exc:
        raise gr.Error(f"ComfyUI error: {exc}") from exc
    return (
        result.image,
        result.depth_map,
        str(result.image_path),
        str(result.depth_path) if result.depth_path else "",
        int(result.seed),
    )


def _on_save(name: str, description: str, image_path: str, depth_path: str) -> str:
    if not name.strip():
        raise gr.Error("Name the scene before saving.")
    if not image_path:
        raise gr.Error("Generate a scene first.")
    saved = scene_store.create(
        name=name.strip(),
        description=description.strip(),
        image_path=image_path,
        depth_map_path=depth_path,
    )
    return f"Saved **{saved.name}** (#{saved.id})."


def render() -> None:
    with gr.Column():
        connection_banner()
        gr.Markdown(
            "### Scenes\n"
            "Generates a location and its depth map. The depth map is cached "
            "so later panels can reuse the same spatial layout."
        )

        with gr.Row():
            with gr.Column(scale=1):
                desc = gr.Textbox(
                    label="Scene description",
                    lines=4,
                    placeholder="e.g. rainy neon alley in Tokyo, night, puddles reflecting signs",
                )
                name = gr.Textbox(label="Name", placeholder="neon_alley")
                with gr.Accordion("Advanced", open=False):
                    width = gr.Slider(label="Width", minimum=768, maximum=2048, step=64, value=1536)
                    height = gr.Slider(label="Height", minimum=768, maximum=2048, step=64, value=1024)
                    seed = gr.Number(label="Seed (blank = random)", value=None, precision=0)
                gen_btn = gr.Button("Generate scene", variant="primary")
                save_btn = gr.Button("Save to library")
            with gr.Column(scale=2):
                with gr.Row():
                    scene_img = gr.Image(label="Scene", type="pil", height=320)
                    depth_img = gr.Image(label="Depth map", type="pil", height=320)
                image_path = gr.Textbox(label="Scene saved to", interactive=False)
                depth_path = gr.Textbox(label="Depth map saved to", interactive=False)
                seed_used = gr.Number(label="Seed used", precision=0, interactive=False)
                status = gr.Markdown()

        gen_btn.click(
            _on_generate,
            inputs=[desc, width, height, seed],
            outputs=[scene_img, depth_img, image_path, depth_path, seed_used],
        )
        save_btn.click(
            _on_save,
            inputs=[name, desc, image_path, depth_path],
            outputs=status,
        )
