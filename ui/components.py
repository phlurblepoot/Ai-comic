"""Shared UI widgets used across tabs."""

from __future__ import annotations

import gradio as gr

from config import get_settings


def connection_banner() -> gr.Markdown:
    """Render a warning at the top of a tab when ComfyUI is not configured."""
    settings = get_settings()
    if settings.is_configured():
        return gr.Markdown(visible=False)
    return gr.Markdown(
        "> **ComfyUI is not configured.** Open the **Settings** tab and enter "
        "your remote ComfyUI URL before generating anything.",
    )
