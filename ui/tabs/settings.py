"""Settings tab — configure the remote ComfyUI connection."""

from __future__ import annotations

import gradio as gr

from comfy.client import ComfyUIClient, ComfyUIError
from config import get_settings, save_settings


def _test_connection(base_url: str, token: str, verify_tls: bool) -> str:
    base_url = (base_url or "").strip()
    if not base_url:
        return "Enter a ComfyUI URL first."
    client = ComfyUIClient(
        base_url=base_url,
        auth_token=(token or "").strip() or None,
        verify_tls=verify_tls,
    )
    try:
        info = client.health_check()
    except ComfyUIError as exc:
        return f"Connection failed: {exc}"
    version = info.get("system", {}).get("comfyui_version") or info.get("version") or "unknown"
    vram = info.get("devices", [{}])[0].get("vram_total") if info.get("devices") else None
    vram_txt = f", VRAM {int(vram) // (1024**3)} GB" if vram else ""
    return f"Connected. ComfyUI version {version}{vram_txt}."


def _save(base_url: str, token: str, verify_tls: bool, checkpoint: str, seed_mode: str) -> str:
    save_settings(
        comfy_base_url=(base_url or "").strip(),
        comfy_auth_token=(token or "").strip(),
        comfy_verify_tls=bool(verify_tls),
        default_checkpoint=(checkpoint or "").strip(),
        default_seed_mode=seed_mode,
    )
    return "Settings saved."


def render() -> None:
    settings = get_settings()
    with gr.Column():
        gr.Markdown("### Settings")
        gr.Markdown(
            "Configure the remote ComfyUI the UI should drive. Values are saved "
            "to `settings.json` in the mounted `/config` volume so they persist "
            "across container restarts."
        )

        base_url = gr.Textbox(
            label="ComfyUI base URL",
            value=settings.comfy_base_url,
            placeholder="http://10.0.0.5:8188",
        )
        token = gr.Textbox(
            label="Auth token (optional)",
            value=settings.comfy_auth_token,
            type="password",
            placeholder="Only needed if ComfyUI is behind a reverse proxy with auth",
        )
        verify_tls = gr.Checkbox(label="Verify TLS certificate", value=settings.comfy_verify_tls)
        checkpoint = gr.Textbox(
            label="Default checkpoint filename",
            value=settings.default_checkpoint,
            placeholder="flux1-dev-fp8.safetensors",
        )
        seed_mode = gr.Radio(
            label="Default seed behaviour",
            choices=["random", "fixed"],
            value=settings.default_seed_mode,
        )

        with gr.Row():
            save_btn = gr.Button("Save settings", variant="primary")
            test_btn = gr.Button("Test connection")

        status = gr.Markdown()

        save_btn.click(
            _save,
            inputs=[base_url, token, verify_tls, checkpoint, seed_mode],
            outputs=status,
        )
        test_btn.click(
            _test_connection,
            inputs=[base_url, token, verify_tls],
            outputs=status,
        )
