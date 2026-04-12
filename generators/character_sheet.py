"""Generate a multi-angle turnaround sheet for a new character."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import yaml
from PIL import Image

from comfy import workflows
from comfy.client import ComfyUIClient, client_from_settings
from config import Settings, get_settings

_MODELS_FILE = Path(__file__).resolve().parent.parent / "config" / "models.yaml"


@dataclass
class CharacterSheetResult:
    image: Image.Image
    saved_path: Path
    seed: int


def _load_model_registry() -> dict:
    with _MODELS_FILE.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def generate(
    description: str,
    *,
    width: int = 1536,
    height: int = 1024,
    seed: int | None = None,
    settings: Settings | None = None,
    client: ComfyUIClient | None = None,
    progress_cb: Callable[[int, int, str | None], None] | None = None,
) -> CharacterSheetResult:
    """Generate a turnaround sheet and save it under ``<assets>/characters/``.

    Raises ``ComfyUIError`` on any backend failure.
    """
    settings = settings or get_settings()
    if not settings.is_configured():
        raise RuntimeError("ComfyUI is not configured; open the Settings tab first.")

    client = client or client_from_settings(settings)
    registry = _load_model_registry()
    checkpoint = (
        settings.default_checkpoint
        or registry.get("checkpoints", {}).get("flux_dev")
        or "flux1-dev-fp8.safetensors"
    )
    seed = seed if seed is not None else workflows.random_seed()

    workflow = workflows.substitute(
        workflows.load("character_sheet"),
        {
            "CHECKPOINT": checkpoint,
            "CLIP_L": "clip_l.safetensors",
            "T5": "t5xxl_fp8_e4m3fn.safetensors",
            "VAE": "ae.safetensors",
            "TURNAROUND_LORA": registry.get("loras", {}).get(
                "turnaround_sheet", "flux-kontext-turnaround-sheet.safetensors"
            ),
            "POSITIVE_PROMPT": description.strip(),
            "SEED": seed,
            "WIDTH": int(width),
            "HEIGHT": int(height),
            "OUTPUT_PREFIX": "ai-comic/character_sheet",
        },
    )

    results = client.run(workflow, progress_cb=progress_cb)
    if not results:
        raise RuntimeError("ComfyUI returned no images for the character sheet.")

    image = results[0].image
    out_dir = settings.assets_path / "characters"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"sheet_{seed}.png"
    image.save(out_path, format="PNG")
    return CharacterSheetResult(image=image, saved_path=out_path, seed=seed)
