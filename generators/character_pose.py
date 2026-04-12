"""Render a saved character in a new pose using PuLID + OpenPose ControlNet."""

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
class PoseResult:
    image: Image.Image
    saved_path: Path
    seed: int


def generate(
    *,
    prompt: str,
    reference_image_path: Path | str,
    openpose_image: Image.Image | None = None,
    openpose_strength: float = 0.85,
    width: int = 1024,
    height: int = 1024,
    seed: int | None = None,
    output_subdir: str = "panels",
    output_prefix: str = "ai-comic/pose",
    settings: Settings | None = None,
    client: ComfyUIClient | None = None,
    progress_cb: Callable[[int, int, str | None], None] | None = None,
) -> PoseResult:
    settings = settings or get_settings()
    if not settings.is_configured():
        raise RuntimeError("ComfyUI is not configured; open the Settings tab first.")
    client = client or client_from_settings(settings)
    registry = _registry()
    checkpoint = (
        settings.default_checkpoint
        or registry.get("checkpoints", {}).get("flux_dev")
        or "flux1-dev-fp8.safetensors"
    )

    # Upload the character reference so the remote ComfyUI can load it.
    ref_path = Path(reference_image_path)
    if not ref_path.exists():
        raise FileNotFoundError(f"Reference image not found: {ref_path}")
    ref_upload = client.upload_image(Image.open(ref_path), ref_path.name)
    ref_name = ref_upload.get("name") or ref_path.name

    # Upload the OpenPose skeleton if provided; otherwise use a neutral blank
    # at zero strength so the node graph still resolves.
    if openpose_image is None:
        openpose_image = Image.new("RGB", (width, height), (0, 0, 0))
        openpose_strength = 0.0
    pose_upload = client.upload_image(openpose_image, "openpose.png")
    pose_name = pose_upload.get("name") or "openpose.png"

    seed = seed if seed is not None else workflows.random_seed()

    workflow = workflows.substitute(
        workflows.load("character_pose"),
        {
            "CHECKPOINT": checkpoint,
            "CLIP_L": "clip_l.safetensors",
            "T5": "t5xxl_fp8_e4m3fn.safetensors",
            "VAE": "ae.safetensors",
            "PULID_MODEL": registry.get("identity", {}).get("pulid", "pulid-flux-v0.9.1.safetensors"),
            "OPENPOSE_CONTROLNET": registry.get("controlnets", {}).get(
                "openpose", "flux-controlnet-openpose.safetensors"
            ),
            "REFERENCE_IMAGE": ref_name,
            "OPENPOSE_IMAGE": pose_name,
            "OPENPOSE_STRENGTH": float(openpose_strength),
            "POSITIVE_PROMPT": prompt.strip(),
            "SEED": seed,
            "WIDTH": int(width),
            "HEIGHT": int(height),
            "OUTPUT_PREFIX": output_prefix,
        },
    )

    results = client.run(workflow, progress_cb=progress_cb)
    if not results:
        raise RuntimeError("ComfyUI returned no images for the pose request.")

    image = results[0].image
    out_dir = settings.assets_path / output_subdir
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"pose_{seed}.png"
    image.save(out_path, format="PNG")
    return PoseResult(image=image, saved_path=out_path, seed=seed)
