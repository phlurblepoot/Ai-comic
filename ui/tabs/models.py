"""Models tab — checks what the remote ComfyUI has installed and flags gaps.

The UI container can't reach into the ComfyUI host's filesystem to download
anything itself, but it *can* query ``/object_info`` to see which model
filenames the remote host advertises. This tab compares that list against
the filenames the workflows expect and tells the user what's missing, with
the exact shell one-liner to run on the ComfyUI host to fix it.
"""

from __future__ import annotations

from pathlib import Path

import gradio as gr
import yaml

from comfy.client import ComfyUIError, client_from_settings
from config import get_settings
from ui.components import connection_banner

_MODELS_FILE = Path(__file__).resolve().parent.parent.parent / "config" / "models.yaml"


def _load_registry() -> dict:
    with _MODELS_FILE.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


# Maps (category, registry_key, kind_for_object_info, human_label, hint).
# `kind_for_object_info` matches ComfyUIClient.list_models().
_REQUIRED: list[tuple[str, str, str, str]] = [
    ("checkpoints",  "flux_dev",          "unet",       "Flux.1 dev base"),
    ("editing",      "kontext",           "unet",       "Flux Kontext dev (image editing)"),
    ("loras",        "turnaround_sheet",  "lora",       "Kontext turnaround sheet LoRA"),
    ("controlnets",  "openpose",          "controlnet", "ControlNet OpenPose (Flux)"),
    ("controlnets",  "depth",             "controlnet", "ControlNet Depth (Flux)"),
    ("identity",     "pulid",             "pulid",      "PuLID-Flux identity model"),
    ("identity",     "ip_adapter",        "ipadapter",  "Flux IP-Adapter"),
]

# Fixed filenames — not user-configurable via models.yaml.
_STATIC: list[tuple[str, str, str]] = [
    ("clip",  "clip_l.safetensors",              "CLIP-L text encoder"),
    ("clip",  "t5xxl_fp8_e4m3fn.safetensors",    "T5-XXL text encoder (fp8)"),
    ("vae",   "ae.safetensors",                  "Flux VAE (ae.safetensors)"),
]


def _check_status():
    settings = get_settings()
    if not settings.is_configured():
        return (
            "ComfyUI not configured — set the remote URL in the Settings tab first.",
            [],
        )
    try:
        client = client_from_settings(settings)
        client.health_check()
    except ComfyUIError as exc:
        return (f"Can't reach ComfyUI: {exc}", [])

    registry = _load_registry()
    rows = []

    # Dynamic entries from models.yaml.
    for category, key, kind, label in _REQUIRED:
        expected = registry.get(category, {}).get(key, "")
        present = set(client.list_models(kind))
        if not expected:
            rows.append([label, "(not in models.yaml)", "—", "⚠"])
            continue
        ok = expected in present
        rows.append([label, expected, kind, "✓" if ok else "✗"])

    # Static entries (text encoders + VAE).
    for kind, filename, label in _STATIC:
        present = set(client.list_models(kind))
        ok = filename in present
        rows.append([label, filename, kind, "✓" if ok else "✗"])

    # Aggregate message.
    missing = [r for r in rows if r[3] == "✗"]
    if not missing:
        summary = f"All {len(rows)} required models are installed on {settings.comfy_base_url}."
    else:
        lines = [f"{len(missing)} model(s) missing on {settings.comfy_base_url}:"]
        for r in missing:
            lines.append(f"  - {r[0]}  (expected filename: `{r[1]}`)")
        summary = "\n".join(lines)
    return summary, rows


_DOWNLOAD_SNIPPET = """\
# On your ComfyUI host (not inside the ai-comic container):

git clone https://github.com/phlurblepoot/ai-comic.git /tmp/ai-comic
export HF_TOKEN=hf_xxxxxxxxxxxxx    # required for Flux.1 dev + Kontext (gated)
bash /tmp/ai-comic/scripts/download_models.sh /path/to/your/ComfyUI

# Restart ComfyUI, then click "Re-check" on this tab.
"""

_CUSTOM_NODES_HINT = """\
You also need these custom nodes (install via *ComfyUI Manager* on the
GPU host, or `git clone` into `ComfyUI/custom_nodes/`):

- [ComfyUI-PuLID-Flux-Enhanced](https://github.com/sipie800/ComfyUI-PuLID-Flux-Enhanced) — PuLID nodes
- [comfyui_controlnet_aux](https://github.com/Fannovel16/comfyui_controlnet_aux) — Depth-Anything preprocessor
- [ComfyUI_IPAdapter_plus](https://github.com/cubiq/ComfyUI_IPAdapter_plus) — IP-Adapter nodes
"""


def render() -> None:
    with gr.Column():
        connection_banner()
        gr.Markdown(
            "### Models\n"
            "Compares the required model filenames against what your remote "
            "ComfyUI currently has installed. The *ai-comic* container itself "
            "cannot download models — the files live on the GPU host."
        )

        recheck_btn = gr.Button("Re-check remote ComfyUI", variant="primary")

        summary = gr.Markdown()
        table = gr.Dataframe(
            headers=["Purpose", "Expected filename", "Kind", "Status"],
            row_count=(0, "dynamic"),
            interactive=False,
            wrap=True,
        )

        with gr.Accordion("How to install missing models", open=True):
            gr.Markdown(
                "Run the bundled `scripts/download_models.sh` on your ComfyUI "
                "host. It's idempotent — re-running only fetches what's missing."
            )
            gr.Code(_DOWNLOAD_SNIPPET, language="shell")
            gr.Markdown(_CUSTOM_NODES_HINT)

        recheck_btn.click(_check_status, outputs=[summary, table])
