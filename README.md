# AI Comic

A local UI for building comics with AI image generation. The UI runs as a small
Docker container (installable on Unraid) and talks to a **remote ComfyUI**
instance running on a GPU host. The UI itself is CPU-only and holds no models.

## Features

- **Character sheets** — generate a multi-angle turnaround a diffusion model
  can reuse.
- **Outfits** — build reusable outfits and apply them to any saved character.
- **Scenes** — generate and reuse locations with their depth maps for
  consistency.
- **Library** — save and browse characters, outfits, and scenes.
- **Compose** — combine a character + outfit + scene into a panel, with
  multi-character scale enforced by a programmatically-built OpenPose skeleton.
- **Speech bubbles** — draw bubbles on top of a rendered panel.
- **Settings** — point the UI at any remote ComfyUI URL; persisted to disk.

## Deployment

### Unraid (recommended)

1. **Apps** → **Add Container** → **Template URL** and paste the raw URL of
   `unraid/ai-comic.xml`.
2. Fill in `AICOMIC_COMFY_URL` with your ComfyUI host, e.g.
   `http://10.0.0.5:8188`.
3. Leave `/config` mapped to `/mnt/user/appdata/ai-comic`.
4. Apply, then open the WebUI. The **Settings** tab will show the URL you
   entered and let you test the connection.

### Plain Docker

```bash
docker run --rm -p 7860:7860 \
    -v "$PWD/data:/config" \
    -e AICOMIC_COMFY_URL=http://<gpu-host>:8188 \
    ghcr.io/phlurblepoot/ai-comic:latest
```

### Local dev

```bash
uv sync
uv run python app.py
```

Then open <http://localhost:7860> and set the ComfyUI URL in the Settings tab.

## Remote ComfyUI prerequisites

The GPU host running ComfyUI needs the following models installed:

- **Flux.1 dev** (fp8 is fine) — base text-to-image.
- **PuLID-Flux** — identity-preserving character consistency.
- **Flux IP-Adapter** — style/reference conditioning.
- **Flux Kontext** — image-to-image editing (outfit swap, turnaround sheets).
- **Flux Kontext Character Turnaround Sheet LoRA**.
- **ControlNet OpenPose** — pose and scale control.
- **ControlNet Depth** — scene structure reuse.

Start ComfyUI with `python main.py --listen 0.0.0.0 --port 8188` so the UI
container can reach it over the LAN.

## Environment variables

All optional; the UI will prompt for missing values on first run.

| Variable | Default | Purpose |
|---|---|---|
| `AICOMIC_COMFY_URL` | — | Remote ComfyUI base URL. |
| `AICOMIC_COMFY_TOKEN` | — | Bearer token if ComfyUI is behind a reverse proxy with auth. |
| `AICOMIC_BIND_HOST` | `0.0.0.0` | |
| `AICOMIC_BIND_PORT` | `7860` | |
| `AICOMIC_CONFIG_DIR` | `/config` | Where settings + DB live. |
| `AICOMIC_ASSETS_DIR` | `/config/assets` | Where generated images are saved. |
