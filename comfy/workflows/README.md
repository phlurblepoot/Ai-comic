# ComfyUI workflow templates

Each `*.json` file is a ComfyUI **API-format** workflow (not the UI save
format) with `{{PLACEHOLDER}}` tokens that Python replaces at run time via
`comfy.workflows.substitute(...)`.

To regenerate or tweak any of these:

1. Open ComfyUI, build the graph visually.
2. Enable *Dev mode* in ComfyUI settings.
3. `Save (API Format)` → copy the JSON here.
4. Replace the user-varying values with `{{UPPER_SNAKE}}` tokens. The
   placeholders expected by each workflow are listed below.

## Placeholders per workflow

### `character_sheet.json`
- `CHECKPOINT` — Flux UNET filename (e.g. `flux1-dev-fp8.safetensors`).
- `CLIP_L` / `T5` — dual CLIP filenames for Flux.
- `VAE` — `ae.safetensors` for Flux.
- `TURNAROUND_LORA` — Kontext turnaround LoRA filename.
- `POSITIVE_PROMPT` — character description.
- `SEED` — integer sampler seed.
- `WIDTH`, `HEIGHT` — output size; typically 1536×1024 for a 4-view sheet.
- `OUTPUT_PREFIX` — filename prefix ComfyUI uses when writing to `output/`.

### `character_pose.json`
Uses PuLID for identity + OpenPose for pose.
- `CHECKPOINT`, `CLIP_L`, `T5`, `VAE`.
- `PULID_MODEL` — PuLID-Flux weights filename.
- `POSITIVE_PROMPT`, `SEED`, `WIDTH`, `HEIGHT`, `OUTPUT_PREFIX`.
- `REFERENCE_IMAGE` — previously-uploaded character sheet filename.
- `OPENPOSE_IMAGE` — optional uploaded skeleton (may be `""` for no pose
  control).
- `OPENPOSE_STRENGTH` — 0.0–1.0.

### `outfit_swap.json`
Flux Kontext image-to-image.
- `CHECKPOINT`, `CLIP_L`, `T5`, `VAE`, `KONTEXT_MODEL`.
- `POSITIVE_PROMPT` — e.g. `"dress this character in the outfit shown in the second reference"`.
- `CHARACTER_IMAGE`, `OUTFIT_IMAGE` — uploaded filenames.
- `SEED`, `OUTPUT_PREFIX`.

### `scene.json`
- `CHECKPOINT`, `CLIP_L`, `T5`, `VAE`.
- `POSITIVE_PROMPT`, `SEED`, `WIDTH`, `HEIGHT`, `OUTPUT_PREFIX`.
Emits both the scene image and a depth map (via MiDaS / Depth-Anything).

### `compose_panel.json`
Multi-character panel with scaled OpenPose skeleton + scene depth map.
- All the character/pose placeholders, plus:
- `SCENE_DEPTH_IMAGE` — uploaded scene depth map.
- `DEPTH_STRENGTH` — 0.0–1.0.
