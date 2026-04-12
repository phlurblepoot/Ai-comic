"""Generate a reusable outfit reference and apply it to a character."""

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


def _registry() -> dict:
    with _MODELS_FILE.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


@dataclass
class OutfitResult:
    image: Image.Image
    saved_path: Path
    seed: int


def generate_reference(
    description: str,
    *,
    width: int = 768,
    height: int = 1152,
    seed: int | None = None,
    settings: Settings | None = None,
    client: ComfyUIClient | None = None,
    progress_cb: Callable | None = None,
) -> OutfitResult:
    """Produce a neutral-mannequin outfit reference image."""
    settings = settings or get_settings()
    if not settings.is_configured():
        raise RuntimeError("ComfyUI is not configured; open the Settings tab first.")
    client = client or client_from_settings(settings)
    registry = _registry()
    checkpoint = settings.default_checkpoint or registry.get("checkpoints", {}).get(
        "flux_dev", "flux1-dev-fp8.safetensors"
    )
    seed = seed if seed is not None else workflows.random_seed()

    workflow = workflows.substitute(
        workflows.load("outfit_reference"),
        {
            "CHECKPOINT": checkpoint,
            "CLIP_L": "clip_l.safetensors",
            "T5": "t5xxl_fp8_e4m3fn.safetensors",
            "VAE": "ae.safetensors",
            "POSITIVE_PROMPT": description.strip(),
            "SEED": seed,
            "WIDTH": int(width),
            "HEIGHT": int(height),
            "OUTPUT_PREFIX": "ai-comic/outfit",
        },
    )

    results = client.run(workflow, progress_cb=progress_cb)
    if not results:
        raise RuntimeError("ComfyUI returned no images for the outfit request.")

    image = results[0].image
    out_dir = settings.assets_path / "outfits"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"outfit_{seed}.png"
    image.save(out_path, format="PNG")
    return OutfitResult(image=image, saved_path=out_path, seed=seed)


def apply_to_character(
    *,
    character_image_path: Path | str,
    outfit_image_path: Path | str,
    extra_prompt: str = "",
    seed: int | None = None,
    settings: Settings | None = None,
    client: ComfyUIClient | None = None,
    progress_cb: Callable | None = None,
) -> OutfitResult:
    """Use Flux Kontext to redress the character in the given outfit."""
    settings = settings or get_settings()
    if not settings.is_configured():
        raise RuntimeError("ComfyUI is not configured; open the Settings tab first.")
    client = client or client_from_settings(settings)
    registry = _registry()

    char_path = Path(character_image_path)
    outfit_path = Path(outfit_image_path)
    if not char_path.exists():
        raise FileNotFoundError(char_path)
    if not outfit_path.exists():
        raise FileNotFoundError(outfit_path)

    char_upload = client.upload_image(Image.open(char_path), char_path.name)
    outfit_upload = client.upload_image(Image.open(outfit_path), outfit_path.name)
    seed = seed if seed is not None else workflows.random_seed()

    workflow = workflows.substitute(
        workflows.load("outfit_swap"),
        {
            "KONTEXT_MODEL": registry.get("editing", {}).get(
                "kontext", "flux-kontext-dev.safetensors"
            ),
            "CLIP_L": "clip_l.safetensors",
            "T5": "t5xxl_fp8_e4m3fn.safetensors",
            "VAE": "ae.safetensors",
            "CHARACTER_IMAGE": char_upload.get("name") or char_path.name,
            "OUTFIT_IMAGE": outfit_upload.get("name") or outfit_path.name,
            "POSITIVE_PROMPT": (extra_prompt or "").strip(),
            "SEED": seed,
            "OUTPUT_PREFIX": "ai-comic/outfit_applied",
        },
    )

    results = client.run(workflow, progress_cb=progress_cb)
    if not results:
        raise RuntimeError("ComfyUI returned no images for the outfit swap.")

    image = results[0].image
    out_dir = settings.assets_path / "outfits" / "applied"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"applied_{seed}.png"
    image.save(out_path, format="PNG")
    return OutfitResult(image=image, saved_path=out_path, seed=seed)
