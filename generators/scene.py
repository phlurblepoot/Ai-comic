"""Generate a background scene and cache its depth map for later reuse."""

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
class SceneResult:
    image: Image.Image
    depth_map: Image.Image | None
    image_path: Path
    depth_path: Path | None
    seed: int


def generate(
    description: str,
    *,
    width: int = 1536,
    height: int = 1024,
    seed: int | None = None,
    settings: Settings | None = None,
    client: ComfyUIClient | None = None,
    progress_cb: Callable | None = None,
) -> SceneResult:
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
        workflows.load("scene"),
        {
            "CHECKPOINT": checkpoint,
            "CLIP_L": "clip_l.safetensors",
            "T5": "t5xxl_fp8_e4m3fn.safetensors",
            "VAE": "ae.safetensors",
            "POSITIVE_PROMPT": description.strip(),
            "SEED": seed,
            "WIDTH": int(width),
            "HEIGHT": int(height),
            "OUTPUT_PREFIX": "ai-comic/scene",
        },
    )

    results = client.run(workflow, progress_cb=progress_cb)
    if not results:
        raise RuntimeError("ComfyUI returned no images for the scene request.")

    # The workflow emits the base image first, then its depth map.
    image = results[0].image
    depth = results[1].image if len(results) > 1 else None

    out_dir = settings.assets_path / "scenes"
    out_dir.mkdir(parents=True, exist_ok=True)
    image_path = out_dir / f"scene_{seed}.png"
    image.save(image_path, format="PNG")

    depth_path: Path | None = None
    if depth is not None:
        depth_path = out_dir / f"scene_{seed}_depth.png"
        depth.save(depth_path, format="PNG")

    return SceneResult(
        image=image,
        depth_map=depth,
        image_path=image_path,
        depth_path=depth_path,
        seed=seed,
    )
