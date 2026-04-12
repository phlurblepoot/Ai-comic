"""Library tab — browse saved characters, outfits, scenes, panels."""

from __future__ import annotations

from pathlib import Path

import gradio as gr

from library import characters, outfits, panels, scenes


def _gallery_items(rows, image_attr: str) -> list:
    items = []
    for row in rows:
        path = getattr(row, image_attr, "") or ""
        label = f"{row.name} (#{row.id})" if hasattr(row, "name") else f"Panel #{row.id}"
        if path and Path(path).exists():
            items.append((path, label))
    return items


def _refresh_all():
    return (
        _gallery_items(characters.list_all(), "sheet_path"),
        _gallery_items(outfits.list_all(), "ref_image_path"),
        _gallery_items(scenes.list_all(), "image_path"),
        _gallery_items(panels.list_all(), "image_path"),
        _character_rows(),
        _outfit_rows(),
        _scene_rows(),
    )


def _character_rows():
    return [[c.id, c.name, c.height_cm, c.description[:80]] for c in characters.list_all()]


def _outfit_rows():
    return [[o.id, o.name, o.tags, o.description[:80]] for o in outfits.list_all()]


def _scene_rows():
    return [[s.id, s.name, s.description[:80]] for s in scenes.list_all()]


def _delete_character(character_id: int) -> str:
    if not character_id:
        raise gr.Error("Enter a character id to delete.")
    ok = characters.delete(int(character_id))
    return "Deleted." if ok else "Not found."


def _delete_outfit(outfit_id: int) -> str:
    if not outfit_id:
        raise gr.Error("Enter an outfit id to delete.")
    ok = outfits.delete(int(outfit_id))
    return "Deleted." if ok else "Not found."


def _delete_scene(scene_id: int) -> str:
    if not scene_id:
        raise gr.Error("Enter a scene id to delete.")
    ok = scenes.delete(int(scene_id))
    return "Deleted." if ok else "Not found."


def render() -> None:
    with gr.Column():
        gr.Markdown("### Library")
        refresh_btn = gr.Button("Refresh")

        with gr.Tabs():
            with gr.Tab("Characters"):
                char_gallery = gr.Gallery(label="Saved characters", columns=4, height=320)
                char_table = gr.Dataframe(
                    headers=["id", "name", "height_cm", "description"],
                    row_count=(0, "dynamic"),
                    interactive=False,
                )
                with gr.Row():
                    char_delete_id = gr.Number(label="Delete id", precision=0)
                    char_delete_btn = gr.Button("Delete")
                char_status = gr.Markdown()
                char_delete_btn.click(_delete_character, inputs=char_delete_id, outputs=char_status)

            with gr.Tab("Outfits"):
                outfit_gallery = gr.Gallery(label="Saved outfits", columns=4, height=320)
                outfit_table = gr.Dataframe(
                    headers=["id", "name", "tags", "description"],
                    row_count=(0, "dynamic"),
                    interactive=False,
                )
                with gr.Row():
                    outfit_delete_id = gr.Number(label="Delete id", precision=0)
                    outfit_delete_btn = gr.Button("Delete")
                outfit_status = gr.Markdown()
                outfit_delete_btn.click(_delete_outfit, inputs=outfit_delete_id, outputs=outfit_status)

            with gr.Tab("Scenes"):
                scene_gallery = gr.Gallery(label="Saved scenes", columns=4, height=320)
                scene_table = gr.Dataframe(
                    headers=["id", "name", "description"],
                    row_count=(0, "dynamic"),
                    interactive=False,
                )
                with gr.Row():
                    scene_delete_id = gr.Number(label="Delete id", precision=0)
                    scene_delete_btn = gr.Button("Delete")
                scene_status = gr.Markdown()
                scene_delete_btn.click(_delete_scene, inputs=scene_delete_id, outputs=scene_status)

            with gr.Tab("Panels"):
                panel_gallery = gr.Gallery(label="Saved panels", columns=3, height=320)

        refresh_btn.click(
            _refresh_all,
            outputs=[
                char_gallery,
                outfit_gallery,
                scene_gallery,
                panel_gallery,
                char_table,
                outfit_table,
                scene_table,
            ],
        )
