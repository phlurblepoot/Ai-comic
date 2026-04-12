"""Gradio entrypoint. Mounts the seven tabs and binds to the configured host."""

from __future__ import annotations

import gradio as gr

from config import get_settings
from ui.tabs import bubble, characters, compose, library, outfits, scenes, settings as settings_tab


def build_app() -> gr.Blocks:
    settings = get_settings()
    # Make sure the mounted /config paths exist — Docker volume creates the
    # mountpoint but nothing inside.
    settings.config_path.mkdir(parents=True, exist_ok=True)
    settings.assets_path.mkdir(parents=True, exist_ok=True)

    with gr.Blocks(title="AI Comic") as app:
        gr.Markdown("# AI Comic")
        with gr.Tabs():
            with gr.Tab("Characters"):
                characters.render()
            with gr.Tab("Outfits"):
                outfits.render()
            with gr.Tab("Scenes"):
                scenes.render()
            with gr.Tab("Compose"):
                compose.render()
            with gr.Tab("Bubbles"):
                bubble.render()
            with gr.Tab("Library"):
                library.render()
            with gr.Tab("Settings"):
                settings_tab.render()
    return app


def main() -> None:
    s = get_settings()
    build_app().launch(
        server_name=s.bind_host,
        server_port=s.bind_port,
        show_error=True,
    )


if __name__ == "__main__":
    main()
