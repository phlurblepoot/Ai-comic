"""Compose tab — put saved characters + outfit + scene into a single panel."""

from __future__ import annotations

import gradio as gr

from comfy.client import ComfyUIError
from config import get_settings
from generators import outfit as outfit_gen
from generators import panel as panel_gen
from generators.composition import CharacterSlot
from library import characters, outfits, panels, scenes
from ui.components import connection_banner


def _character_choices():
    return [f"{c.id}: {c.name} ({c.height_cm:.0f}cm)" for c in characters.list_all()]


def _outfit_choices():
    return ["(none)"] + [f"{o.id}: {o.name}" for o in outfits.list_all()]


def _scene_choices():
    return ["(none)"] + [f"{s.id}: {s.name}" for s in scenes.list_all()]


def _parse_id(choice: str) -> int | None:
    if not choice or choice == "(none)":
        return None
    try:
        return int(choice.split(":", 1)[0])
    except (ValueError, IndexError):
        return None


def _refresh():
    return (
        gr.update(choices=_character_choices()),
        gr.update(choices=_character_choices()),
        gr.update(choices=_outfit_choices()),
        gr.update(choices=_scene_choices()),
    )


def _on_compose(
    primary_choice: str,
    secondary_choice: str,
    outfit_choice: str,
    scene_choice: str,
    prompt: str,
    pose_strength: float,
    depth_strength: float,
    width: int,
    height: int,
):
    settings = get_settings()
    if not settings.is_configured():
        raise gr.Error("ComfyUI is not configured. Open the Settings tab first.")
    primary_id = _parse_id(primary_choice)
    if primary_id is None:
        raise gr.Error("Pick at least one character.")
    primary = characters.get(primary_id)
    if not primary or not primary.sheet_path:
        raise gr.Error("Primary character has no sheet.")

    slots = [CharacterSlot(name=primary.name, height_cm=primary.height_cm)]
    secondary = None
    secondary_id = _parse_id(secondary_choice)
    if secondary_id:
        secondary = characters.get(secondary_id)
        if secondary:
            slots.append(CharacterSlot(name=secondary.name, height_cm=secondary.height_cm))

    # Optional: apply outfit to the primary character first, then feed that
    # image into the composition as the identity reference.
    reference_path = primary.sheet_path
    outfit_id = _parse_id(outfit_choice)
    if outfit_id:
        outfit = outfits.get(outfit_id)
        if outfit and outfit.ref_image_path:
            try:
                res = outfit_gen.apply_to_character(
                    character_image_path=primary.sheet_path,
                    outfit_image_path=outfit.ref_image_path,
                    extra_prompt="full body, clear outfit visibility",
                    settings=settings,
                )
                reference_path = str(res.saved_path)
            except ComfyUIError as exc:
                raise gr.Error(f"Outfit application failed: {exc}") from exc

    scene_id = _parse_id(scene_choice)
    scene_depth_path = None
    scene_img_path = None
    prompt_prefix = ""
    if scene_id:
        scene = scenes.get(scene_id)
        if scene:
            scene_img_path = scene.image_path
            scene_depth_path = scene.depth_map_path
            if scene.description:
                prompt_prefix = f"Scene: {scene.description}. "

    full_prompt = prompt_prefix + (prompt or "").strip()
    if not full_prompt:
        full_prompt = ", ".join(
            f"{slot.name} ({slot.height_cm:.0f}cm tall)" for slot in slots
        )

    try:
        result = panel_gen.compose(
            prompt=full_prompt,
            primary_reference_path=reference_path,
            scene_image_path=scene_img_path,
            scene_depth_path=scene_depth_path,
            characters=slots,
            width=int(width),
            height=int(height),
            openpose_strength=float(pose_strength),
            depth_strength=float(depth_strength),
            settings=settings,
        )
    except ComfyUIError as exc:
        raise gr.Error(f"ComfyUI error: {exc}") from exc
    return result.image, result.skeleton, str(result.image_path), int(result.seed)


def _on_save_panel(title: str, image_path: str) -> str:
    if not image_path:
        raise gr.Error("Compose a panel first.")
    saved = panels.create(title=title.strip() or "untitled", image_path=image_path)
    return f"Saved panel #{saved.id}."


def render() -> None:
    with gr.Column():
        connection_banner()
        gr.Markdown(
            "### Compose\n"
            "Pick a primary character (optional second), an outfit, and a scene. "
            "Heights from the library drive a programmatically-built OpenPose "
            "skeleton so relative scale is enforced in the output."
        )

        with gr.Row():
            primary = gr.Dropdown(label="Primary character", choices=_character_choices())
            secondary = gr.Dropdown(label="Second character (optional)", choices=_character_choices())
        with gr.Row():
            outfit_dd = gr.Dropdown(label="Outfit (applied to primary)", choices=_outfit_choices(), value="(none)")
            scene_dd = gr.Dropdown(label="Scene", choices=_scene_choices(), value="(none)")
        refresh_btn = gr.Button("Refresh lists")

        prompt = gr.Textbox(
            label="Panel prompt / action",
            placeholder="e.g. standing side by side, rain falling, looking at camera",
            lines=3,
        )
        with gr.Accordion("Advanced", open=False):
            pose_strength = gr.Slider(0.0, 1.0, value=0.85, step=0.05, label="OpenPose strength")
            depth_strength = gr.Slider(0.0, 1.0, value=0.55, step=0.05, label="Depth strength")
            width = gr.Slider(768, 2048, value=1536, step=64, label="Width")
            height = gr.Slider(768, 2048, value=1024, step=64, label="Height")

        compose_btn = gr.Button("Compose panel", variant="primary")
        with gr.Row():
            panel_img = gr.Image(label="Panel", type="pil", height=480)
            skeleton_img = gr.Image(label="OpenPose skeleton used", type="pil", height=480)
        image_path = gr.Textbox(label="Saved to", interactive=False)
        seed_used = gr.Number(label="Seed used", precision=0, interactive=False)

        with gr.Row():
            title = gr.Textbox(label="Panel title", placeholder="rooftop confrontation")
            save_btn = gr.Button("Save panel")
        status = gr.Markdown()

        refresh_btn.click(_refresh, outputs=[primary, secondary, outfit_dd, scene_dd])
        compose_btn.click(
            _on_compose,
            inputs=[primary, secondary, outfit_dd, scene_dd, prompt, pose_strength, depth_strength, width, height],
            outputs=[panel_img, skeleton_img, image_path, seed_used],
        )
        save_btn.click(_on_save_panel, inputs=[title, image_path], outputs=status)
