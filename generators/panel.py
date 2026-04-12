"""Compose a full panel — one or more characters in a scene at correct scale."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

import yaml
from PIL import Image

from comfy import workflows
from comfy.client import ComfyUIClient, client_from_settings
from config import Settings, get_settings
from generators.composition import CharacterSlot, build_skeleton

_MODELS_FILE = Path(__file__).resolve().parent.parent / "config" / "models.yaml"


def _registry() -> dict:
    with _MODELS_FILE.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


@dataclass
class PanelResult:
    image: Image.Image
    skeleton: Image.Image
    image_path: Path
    skeleton_path: Path
    seed: int


def compose(
    *,
    prompt: str,
    primary_reference_path: Path | str,
    scene_image_path: Path | str | None,
    scene_depth_path: Path | str | None,
    characters: Sequence[CharacterSlot],
    width: int = 1536,
    height: int = 1024,
    openpose_strength: float = 0.85,
    depth_strength: float = 0.55,
    seed: int | None = None,
    settings: Settings | None = None,
    client: ComfyUIClient | None = None,
    progress_cb: Callable | None = None,
) -> PanelResult:
    """Generate a panel.

    - ``primary_reference_path``: sheet image of the main character used for
      PuLID identity. Multi-character identity still needs further work; for
      now we lock the main character and rely on prompt for others.
    - ``characters``: one slot per visible character, with ``height_cm`` so the
      scaled OpenPose skeleton enforces correct relative heights.
    - ``scene_depth_path``: optional. When provided, the ControlNet Depth
      branch uses the cached scene depth map to keep the layout stable.
    """
    settings = settings or get_settings()
    if not settings.is_configured():
        raise RuntimeError("ComfyUI is not configured; open the Settings tab first.")
    client = client or client_from_settings(settings)
    registry = _registry()

    # Build the skeleton locally, then upload it.
    skeleton_img = build_skeleton(characters, width=width, height=height)

    primary_path = Path(primary_reference_path)
    if not primary_path.exists():
        raise FileNotFoundError(primary_path)
    ref_upload = client.upload_image(Image.open(primary_path), primary_path.name)
    pose_upload = client.upload_image(skeleton_img, "openpose_composed.png")

    # Depth: use the scene's cached map if present, otherwise a neutral grey
    # image with strength 0 so the graph still resolves.
    if scene_depth_path and Path(scene_depth_path).exists():
        depth_upload = client.upload_image(Image.open(scene_depth_path), Path(scene_depth_path).name)
        depth_name = depth_upload.get("name") or Path(scene_depth_path).name
        effective_depth_strength = float(depth_strength)
    else:
        blank = Image.new("RGB", (width, height), (128, 128, 128))
        depth_upload = client.upload_image(blank, "depth_blank.png")
        depth_name = depth_upload.get("name") or "depth_blank.png"
        effective_depth_strength = 0.0

    checkpoint = settings.default_checkpoint or registry.get("checkpoints", {}).get(
        "flux_dev", "flux1-dev-fp8.safetensors"
    )
    seed = seed if seed is not None else workflows.random_seed()

    workflow = workflows.substitute(
        workflows.load("compose_panel"),
        {
            "CHECKPOINT": checkpoint,
            "CLIP_L": "clip_l.safetensors",
            "T5": "t5xxl_fp8_e4m3fn.safetensors",
            "VAE": "ae.safetensors",
            "PULID_MODEL": registry.get("identity", {}).get("pulid", "pulid-flux-v0.9.1.safetensors"),
            "OPENPOSE_CONTROLNET": registry.get("controlnets", {}).get(
                "openpose", "flux-controlnet-openpose.safetensors"
            ),
            "DEPTH_CONTROLNET": registry.get("controlnets", {}).get(
                "depth", "flux-controlnet-depth.safetensors"
            ),
            "REFERENCE_IMAGE": ref_upload.get("name") or primary_path.name,
            "OPENPOSE_IMAGE": pose_upload.get("name") or "openpose_composed.png",
            "OPENPOSE_STRENGTH": float(openpose_strength),
            "DEPTH_IMAGE": depth_name,
            "DEPTH_STRENGTH": effective_depth_strength,
            "POSITIVE_PROMPT": prompt.strip(),
            "SEED": seed,
            "WIDTH": int(width),
            "HEIGHT": int(height),
            "OUTPUT_PREFIX": "ai-comic/panel",
        },
    )

    results = client.run(workflow, progress_cb=progress_cb)
    if not results:
        raise RuntimeError("ComfyUI returned no images for the panel.")

    image = results[0].image
    out_dir = settings.assets_path / "panels"
    out_dir.mkdir(parents=True, exist_ok=True)
    image_path = out_dir / f"panel_{seed}.png"
    image.save(image_path, format="PNG")
    skeleton_path = out_dir / f"panel_{seed}_skeleton.png"
    skeleton_img.save(skeleton_path, format="PNG")

    return PanelResult(
        image=image,
        skeleton=skeleton_img,
        image_path=image_path,
        skeleton_path=skeleton_path,
        seed=seed,
    )
