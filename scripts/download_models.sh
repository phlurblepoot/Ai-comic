#!/usr/bin/env bash
# download_models.sh — fetches every model the AI Comic UI needs into a
# ComfyUI installation.
#
# RUN THIS ON YOUR COMFYUI HOST (the GPU box), not inside the ai-comic
# container. It writes files into <COMFYUI>/models/<subfolder>/.
#
# Usage:
#   ./download_models.sh /path/to/ComfyUI
#   COMFYUI_DIR=/path/to/ComfyUI ./download_models.sh
#
# Environment variables:
#   HF_TOKEN       HuggingFace token (required for gated repos: Flux.1 dev
#                  and Flux Kontext dev). Get one at
#                  https://huggingface.co/settings/tokens and accept the
#                  licenses on each gated model page first.
#   SKIP_FLUX_DEV  Set to 1 to skip the ~12 GB base Flux.1 dev weights
#                  (use if you already have them).
#
# The script skips files that are already present with the expected name,
# so it's safe to re-run.

set -euo pipefail

COMFYUI_DIR="${1:-${COMFYUI_DIR:-}}"
if [ -z "$COMFYUI_DIR" ]; then
    echo "Usage: $0 /path/to/ComfyUI"
    echo "   or: COMFYUI_DIR=/path/to/ComfyUI $0"
    exit 2
fi
if [ ! -d "$COMFYUI_DIR" ]; then
    echo "Not a directory: $COMFYUI_DIR"
    exit 2
fi

MODELS="$COMFYUI_DIR/models"
mkdir -p "$MODELS"/{unet,clip,vae,loras,controlnet,pulid,ipadapter,insightface,depthanything}

have() { command -v "$1" >/dev/null 2>&1; }

if ! have wget && ! have curl; then
    echo "Need wget or curl installed."
    exit 2
fi

download() {
    # download <url> <dest_path> [auth]
    local url="$1"
    local dest="$2"
    local auth="${3:-}"
    local name
    name=$(basename "$dest")

    if [ -f "$dest" ] && [ -s "$dest" ]; then
        echo "  ✓ $name (already present)"
        return 0
    fi
    echo "  ⤓ $name"
    mkdir -p "$(dirname "$dest")"

    local hdr=()
    if [ -n "$auth" ]; then
        hdr=(-H "Authorization: Bearer $auth")
    fi

    if have wget; then
        local wget_auth=()
        if [ -n "$auth" ]; then
            wget_auth=(--header="Authorization: Bearer $auth")
        fi
        wget --show-progress -O "$dest.part" "${wget_auth[@]}" "$url"
    else
        curl -L --fail --progress-bar "${hdr[@]}" -o "$dest.part" "$url"
    fi
    mv "$dest.part" "$dest"
}

section() {
    echo
    echo "=== $1 ==="
}

# ---------- Base Flux ----------
section "Flux.1 dev base (gated — needs HF_TOKEN if not already downloaded)"
if [ "${SKIP_FLUX_DEV:-0}" != "1" ]; then
    if [ -z "${HF_TOKEN:-}" ]; then
        echo "HF_TOKEN not set — skipping gated Flux.1 dev. Export HF_TOKEN"
        echo "and re-run, or set SKIP_FLUX_DEV=1 to silence this warning."
    else
        download \
            "https://huggingface.co/Comfy-Org/flux1-dev/resolve/main/flux1-dev-fp8.safetensors" \
            "$MODELS/unet/flux1-dev-fp8.safetensors" \
            "$HF_TOKEN"
        download \
            "https://huggingface.co/black-forest-labs/FLUX.1-dev/resolve/main/ae.safetensors" \
            "$MODELS/vae/ae.safetensors" \
            "$HF_TOKEN"
    fi
fi

# ---------- Text encoders ----------
section "Text encoders (T5 + CLIP-L, public)"
download \
    "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp8_e4m3fn.safetensors" \
    "$MODELS/clip/t5xxl_fp8_e4m3fn.safetensors"
download \
    "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors" \
    "$MODELS/clip/clip_l.safetensors"

# ---------- Flux Kontext (image editing, gated) ----------
section "Flux Kontext dev (gated — HF_TOKEN required)"
if [ -n "${HF_TOKEN:-}" ]; then
    download \
        "https://huggingface.co/black-forest-labs/FLUX.1-Kontext-dev/resolve/main/flux1-kontext-dev.safetensors" \
        "$MODELS/unet/flux-kontext-dev.safetensors" \
        "$HF_TOKEN"
else
    echo "Skipped (no HF_TOKEN). Accept the license at"
    echo "https://huggingface.co/black-forest-labs/FLUX.1-Kontext-dev"
    echo "then re-run with HF_TOKEN set."
fi

# ---------- Character turnaround LoRA ----------
section "Kontext Character Turnaround Sheet LoRA"
download \
    "https://huggingface.co/comfyanonymous/flux_turnaround_loras/resolve/main/flux-kontext-turnaround-sheet.safetensors" \
    "$MODELS/loras/flux-kontext-turnaround-sheet.safetensors" \
    "${HF_TOKEN:-}"

# ---------- PuLID-Flux (identity) ----------
section "PuLID-Flux"
download \
    "https://huggingface.co/guozinan/PuLID/resolve/main/pulid_flux_v0.9.1.safetensors" \
    "$MODELS/pulid/pulid-flux-v0.9.1.safetensors"

# EVA-CLIP + InsightFace assets that PuLID-Flux loads at runtime.
section "PuLID auxiliary models (InsightFace antelopev2 + EVA-CLIP)"
download \
    "https://huggingface.co/MonsterMMORPG/tools/resolve/main/antelopev2.zip" \
    "$MODELS/insightface/antelopev2.zip"
if [ -f "$MODELS/insightface/antelopev2.zip" ] && [ ! -d "$MODELS/insightface/models/antelopev2" ]; then
    echo "  ⤓ extracting antelopev2"
    mkdir -p "$MODELS/insightface/models"
    (cd "$MODELS/insightface/models" && unzip -oq "$MODELS/insightface/antelopev2.zip")
fi

# ---------- Flux IP-Adapter ----------
section "Flux IP-Adapter"
download \
    "https://huggingface.co/XLabs-AI/flux-ip-adapter-v2/resolve/main/ip_adapter.safetensors" \
    "$MODELS/ipadapter/flux-ip-adapter.safetensors"

# ---------- ControlNet OpenPose + Depth ----------
section "Flux ControlNets (OpenPose + Depth, from XLabs-AI)"
download \
    "https://huggingface.co/XLabs-AI/flux-controlnet-collections/resolve/main/flux-openpose-controlnet-v3.safetensors" \
    "$MODELS/controlnet/flux-controlnet-openpose.safetensors"
download \
    "https://huggingface.co/XLabs-AI/flux-controlnet-collections/resolve/main/flux-depth-controlnet-v3.safetensors" \
    "$MODELS/controlnet/flux-controlnet-depth.safetensors"

# ---------- Depth-Anything V2 (for the depth preprocessor node) ----------
section "Depth-Anything V2 (large)"
download \
    "https://huggingface.co/depth-anything/Depth-Anything-V2-Large/resolve/main/depth_anything_v2_vitl.pth" \
    "$MODELS/depthanything/depth_anything_v2_vitl.pth"

echo
echo "Done. Restart ComfyUI so it picks up the new files."
echo
echo "Custom nodes still needed (install via ComfyUI Manager):"
echo "  - ComfyUI-PuLID-Flux-Enhanced   (PuLID nodes)"
echo "  - comfyui_controlnet_aux         (Depth-Anything preprocessor)"
echo "  - ComfyUI_IPAdapter_plus         (IP-Adapter nodes)"
echo "  - ComfyUI-KJNodes (or equivalent) for FluxKontextImageScale / ImageStitch, if not in core"
