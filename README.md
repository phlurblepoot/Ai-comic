# AI Comic

A local UI for building comics with AI image generation. The UI runs as a
small Docker container on your Unraid server and talks to a **remote ComfyUI**
instance over the LAN. The container is CPU-only and holds no models.

## Features

- **Character sheets** — multi-angle turnaround a diffusion model can reuse.
- **Outfits** — build reusable outfits and apply them to any saved character.
- **Scenes** — generate consistent locations; depth maps are cached so the
  same spatial layout can be reused across panels.
- **Library** — save and browse characters, outfits, scenes, and panels.
- **Compose** — combine a character + outfit + scene into a panel with
  multi-character scale enforced via a programmatic OpenPose skeleton.
- **Speech bubbles** — draw bubbles over rendered panels.
- **Settings** — configure the remote ComfyUI URL; settings persist across restarts.

---

## Unraid installation

### Step 1 — get the Docker image

You need the image available before Unraid can pull it. Choose one option:

#### Option A: push to GHCR (then Unraid pulls it automatically)

1. Clone this repo on any machine that has Docker.
2. Log in to GitHub Container Registry:
   ```bash
   echo YOUR_GITHUB_TOKEN | docker login ghcr.io -u YOUR_GITHUB_USER --password-stdin
   ```
3. Build and push:
   ```bash
   chmod +x build.sh
   ./build.sh          # amd64 only — faster
   ./build.sh --multiarch  # amd64 + arm64
   ```
   The image is pushed to `ghcr.io/phlurblepoot/ai-comic:latest`.
4. Make the package **public** in your GitHub account under
   *Packages → ai-comic → Package settings → Change visibility → Public*,
   or add your Unraid server's GitHub credentials so it can pull a private package.

#### Option B: build directly on the Unraid host

SSH into Unraid and run:

```bash
git clone https://github.com/phlurblepoot/ai-comic.git /tmp/ai-comic
cd /tmp/ai-comic
docker build -t ghcr.io/phlurblepoot/ai-comic:latest .
```

Unraid will find the image locally and won't need to pull it.

---

### Step 2 — add the container in Unraid

**Quickest way — paste the template URL:**

1. Unraid → **Docker** tab → **Add Container** → click the template icon →
   **Template Repositories** → add:
   ```
   https://raw.githubusercontent.com/phlurblepoot/ai-comic/main/unraid/ai-comic.xml
   ```
   Then refresh and search for **ai-comic**.

**Manual way (no GitHub required):**

1. Unraid → **Docker** → **Add Container**.
2. Fill in the fields below, then click **Apply**.

| Field | Value |
|---|---|
| Name | `ai-comic` |
| Repository | `ghcr.io/phlurblepoot/ai-comic:latest` |
| Network | `bridge` |
| WebUI | `http://[IP]:[PORT:7860]` |
| **Port** — Container `7860` → Host `7860` (TCP) | |
| **Path** — Container `/config` → Host `/mnt/user/appdata/ai-comic` (RW) | |
| **Variable** `AICOMIC_COMFY_URL` | `http://10.0.0.5:8188` *(your ComfyUI IP)* |
| **Variable** `AICOMIC_COMFY_TOKEN` | *(leave blank unless using a reverse proxy with auth)* |

3. Start the container. Open `http://UNRAID-IP:7860`.
4. Go to the **Settings** tab, confirm the ComfyUI URL, click **Test connection**.

---

## Remote ComfyUI requirements

The GPU host running ComfyUI needs Flux.1 dev plus a handful of supporting
models. You have two ways to install them:

### Easy: run the bundled download script on the ComfyUI host

```bash
git clone https://github.com/phlurblepoot/ai-comic.git /tmp/ai-comic
export HF_TOKEN=hf_xxxxxxxxxxxxx   # from https://huggingface.co/settings/tokens
                                   # accept the Flux.1-dev + Flux.1-Kontext-dev
                                   # licenses first
bash /tmp/ai-comic/scripts/download_models.sh /path/to/your/ComfyUI
```

The script is idempotent (safe to re-run — it skips files already present)
and writes each weight into the correct `ComfyUI/models/<subfolder>/`. Start
ComfyUI with `python main.py --listen 0.0.0.0 --port 8188` afterwards.

### Then: verify from the UI

Inside the app, open the **Models** tab and click **Re-check remote ComfyUI**.
It'll query `/object_info` on your ComfyUI host and show a ✓/✗ for every
required file, with copy-paste commands to fix anything missing.

### Full model list

| Purpose | Model |
|---|---|
| Base text-to-image | **Flux.1 dev** (fp8) |
| Character consistency | **PuLID-Flux** |
| Style/reference conditioning | **Flux IP-Adapter** |
| Image editing / outfit swap | **Flux Kontext dev** |
| Character sheet turnarounds | **Flux Kontext Turnaround Sheet LoRA** |
| Pose + scale control | **ControlNet OpenPose** (Flux, XLabs-AI) |
| Scene depth reuse | **ControlNet Depth** (Flux, XLabs-AI) |
| Depth extraction | **Depth-Anything V2** (large) |
| Text encoders | **T5-XXL fp8 + CLIP-L** |
| VAE | **FLUX.1 ae.safetensors** |
| PuLID face features | **InsightFace antelopev2** |

### Custom nodes (not downloaded by the script)

Install these via **ComfyUI Manager** on the GPU host, or `git clone` into
`ComfyUI/custom_nodes/`:

- `ComfyUI-PuLID-Flux-Enhanced` — PuLID nodes for Flux
- `comfyui_controlnet_aux` — Depth-Anything preprocessor
- `ComfyUI_IPAdapter_plus` — IP-Adapter nodes

If any model filenames differ on your host, edit `config/models.yaml` or
override the default checkpoint from the **Settings** tab.

---

## Local dev / plain Docker

```bash
# Copy and edit the example env file:
cp .env.example .env   # edit AICOMIC_COMFY_URL at minimum

# Build and run locally:
./build.sh --local
docker run --rm -p 7860:7860 \
    -v "$PWD/data:/config" \
    -e AICOMIC_COMFY_URL=http://10.0.0.5:8188 \
    ghcr.io/phlurblepoot/ai-comic:latest
```

Or with docker compose:
```bash
AICOMIC_COMFY_URL=http://10.0.0.5:8188 docker compose up
```

Open <http://localhost:7860>.

---

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `AICOMIC_COMFY_URL` | — | Remote ComfyUI base URL |
| `AICOMIC_COMFY_TOKEN` | — | Bearer token for auth-proxy setups |
| `AICOMIC_BIND_HOST` | `0.0.0.0` | |
| `AICOMIC_BIND_PORT` | `7860` | |
| `AICOMIC_CONFIG_DIR` | `/config` | DB + settings.json location |
| `AICOMIC_ASSETS_DIR` | `/config/assets` | Generated images location |
| `PUID` | `99` | File ownership uid (Unraid default) |
| `PGID` | `100` | File ownership gid (Unraid default) |

All settings can also be changed from the **Settings** tab inside the UI
and are persisted to `/config/settings.json` so they survive restarts.
