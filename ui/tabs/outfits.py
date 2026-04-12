"""Outfit generator tab."""

from __future__ import annotations

import gradio as gr

from comfy.client import ComfyUIError
from config import get_settings
from generators import outfit as outfit_gen
from library import characters, outfits
from ui.components import connection_banner


def _character_choices():
    return [f"{c.id}: {c.name}" for c in characters.list_all()]


def _outfit_choices():
    return [f"{o.id}: {o.name}" for o in outfits.list_all()]


def _parse_id(choice: str) -> int | None:
    if not choice:
        return None
    try:
        return int(choice.split(":", 1)[0])
    except (ValueError, IndexError):
        return None


def _on_generate_ref(description: str, seed: int | None):
    settings = get_settings()
    if not settings.is_configured():
        raise gr.Error("ComfyUI is not configured. Open the Settings tab first.")
    if not description.strip():
        raise gr.Error("Describe the outfit first.")
    try:
        result = outfit_gen.generate_reference(
            description=description,
            seed=int(seed) if seed else None,
            settings=settings,
        )
    except ComfyUIError as exc:
        raise gr.Error(f"ComfyUI error: {exc}") from exc
    return result.image, str(result.saved_path), int(result.seed)


def _on_save(name: str, description: str, tags: str, ref_path: str) -> str:
    if not name.strip():
        raise gr.Error("Name the outfit before saving.")
    if not ref_path:
        raise gr.Error("Generate a reference image first.")
    saved = outfits.create(
        name=name.strip(),
        description=description.strip(),
        ref_image_path=ref_path,
        tags=tags.strip(),
    )
    return f"Saved **{saved.name}** (#{saved.id})."


def _on_apply(character_choice: str, outfit_choice: str, extra_prompt: str):
    settings = get_settings()
    if not settings.is_configured():
        raise gr.Error("ComfyUI is not configured. Open the Settings tab first.")
    cid = _parse_id(character_choice)
    oid = _parse_id(outfit_choice)
    if cid is None or oid is None:
        raise gr.Error("Pick a saved character and a saved outfit.")
    character = characters.get(cid)
    outfit = outfits.get(oid)
    if not character or not character.sheet_path:
        raise gr.Error("That character has no saved sheet.")
    if not outfit or not outfit.ref_image_path:
        raise gr.Error("That outfit has no saved reference image.")
    try:
        result = outfit_gen.apply_to_character(
            character_image_path=character.sheet_path,
            outfit_image_path=outfit.ref_image_path,
            extra_prompt=extra_prompt,
            settings=settings,
        )
    except ComfyUIError as exc:
        raise gr.Error(f"ComfyUI error: {exc}") from exc
    return result.image, str(result.saved_path)


def render() -> None:
    with gr.Column():
        connection_banner()
        gr.Markdown("### Outfits")

        with gr.Tabs():
            with gr.Tab("Create outfit reference"):
                with gr.Row():
                    with gr.Column(scale=1):
                        desc = gr.Textbox(
                            label="Outfit description",
                            lines=3,
                            placeholder="e.g. long grey trench coat, dark jeans, heavy boots",
                        )
                        name = gr.Textbox(label="Name", placeholder="trench_coat")
                        tags = gr.Textbox(label="Tags (comma-separated)", placeholder="coat, casual")
                        seed = gr.Number(label="Seed (blank = random)", value=None, precision=0)
                        gen_btn = gr.Button("Generate reference", variant="primary")
                        save_btn = gr.Button("Save to library")
                    with gr.Column(scale=2):
                        preview = gr.Image(label="Outfit reference", type="pil", height=400)
                        seed_used = gr.Number(label="Seed used", precision=0, interactive=False)
                        ref_path = gr.Textbox(label="Saved to", interactive=False)
                        status = gr.Markdown()

                gen_btn.click(_on_generate_ref, inputs=[desc, seed], outputs=[preview, ref_path, seed_used])
                save_btn.click(_on_save, inputs=[name, desc, tags, ref_path], outputs=status)

            with gr.Tab("Apply outfit to character"):
                with gr.Row():
                    char_dd = gr.Dropdown(label="Character", choices=_character_choices(), interactive=True)
                    outfit_dd = gr.Dropdown(label="Outfit", choices=_outfit_choices(), interactive=True)
                refresh_btn = gr.Button("Refresh lists")
                extra = gr.Textbox(label="Extra direction (optional)", placeholder="keep her determined expression")
                apply_btn = gr.Button("Apply outfit", variant="primary")
                result_img = gr.Image(label="Result", type="pil", height=400)
                result_path = gr.Textbox(label="Saved to", interactive=False)

                refresh_btn.click(
                    lambda: (gr.update(choices=_character_choices()), gr.update(choices=_outfit_choices())),
                    outputs=[char_dd, outfit_dd],
                )
                apply_btn.click(_on_apply, inputs=[char_dd, outfit_dd, extra], outputs=[result_img, result_path])
