"""Client for a remote ComfyUI instance.

ComfyUI's REST + WebSocket API is well-documented but slightly quirky: you
``POST /prompt`` with an API-format workflow JSON, get back a ``prompt_id``,
then subscribe to ``ws://.../ws`` to watch execution events. When a node
produces an image it lands in ComfyUI's output folder and is fetched via
``GET /view?filename=...&subfolder=...&type=output``.

This module hides all of that behind a small, typed surface.
"""

from __future__ import annotations

import io
import json
import time
import uuid
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import urlencode, urlparse

import requests
from PIL import Image
from websocket import WebSocket, WebSocketException, create_connection


class ComfyUIError(RuntimeError):
    """Raised for any failure talking to ComfyUI — network, HTTP, or workflow."""


@dataclass
class GeneratedImage:
    filename: str
    subfolder: str
    type: str  # "output" | "temp" | "input"
    image: Image.Image


def _ws_url_for(base_url: str) -> str:
    parsed = urlparse(base_url.rstrip("/"))
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return f"{scheme}://{parsed.netloc}/ws"


class ComfyUIClient:
    """Thin wrapper around the ComfyUI REST + WebSocket API."""

    def __init__(
        self,
        base_url: str,
        *,
        auth_token: str | None = None,
        verify_tls: bool = True,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        self.verify_tls = verify_tls
        self.timeout = timeout
        self.client_id = uuid.uuid4().hex

    # ---------- HTTP helpers ----------
    @property
    def _headers(self) -> dict[str, str]:
        h = {"Accept": "application/json"}
        if self.auth_token:
            h["Authorization"] = f"Bearer {self.auth_token}"
        return h

    def _get(self, path: str, *, params: dict | None = None, stream: bool = False) -> requests.Response:
        url = f"{self.base_url}{path}"
        try:
            resp = requests.get(
                url,
                params=params,
                headers=self._headers,
                verify=self.verify_tls,
                timeout=self.timeout,
                stream=stream,
            )
        except requests.RequestException as exc:
            raise ComfyUIError(f"GET {path} failed: {exc}") from exc
        if resp.status_code >= 400:
            raise ComfyUIError(f"GET {path} returned {resp.status_code}: {resp.text[:300]}")
        return resp

    def _post(self, path: str, *, json_body: dict | None = None, files: dict | None = None, data: dict | None = None) -> requests.Response:
        url = f"{self.base_url}{path}"
        try:
            resp = requests.post(
                url,
                json=json_body if files is None else None,
                files=files,
                data=data,
                headers=self._headers,
                verify=self.verify_tls,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise ComfyUIError(f"POST {path} failed: {exc}") from exc
        if resp.status_code >= 400:
            raise ComfyUIError(f"POST {path} returned {resp.status_code}: {resp.text[:300]}")
        return resp

    # ---------- Public API ----------
    def health_check(self) -> dict[str, Any]:
        """Hit ``/system_stats``. Raises ComfyUIError on failure."""
        return self._get("/system_stats").json()

    def object_info(self) -> dict[str, Any]:
        """Return the node/model catalogue exposed by ComfyUI."""
        return self._get("/object_info").json()

    def list_checkpoints(self) -> list[str]:
        """Checkpoint filenames known to the remote host."""
        info = self.object_info()
        try:
            return list(info["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0])
        except (KeyError, IndexError, TypeError):
            return []

    def list_models(self, kind: str) -> list[str]:
        """Return filenames available on the remote host for a given model kind.

        ``kind`` is one of: ``unet``, ``checkpoint``, ``clip``, ``vae``,
        ``lora``, ``controlnet``, ``pulid``, ``ipadapter``. The function maps
        each kind to a ComfyUI loader node and introspects its input options.
        Unknown kinds return ``[]``.
        """
        lookups: dict[str, tuple[str, list[str]]] = {
            # kind -> (node class_type, [keypath...] into input.required)
            "unet":       ("UNETLoader",              ["unet_name"]),
            "checkpoint": ("CheckpointLoaderSimple",  ["ckpt_name"]),
            "clip":       ("DualCLIPLoader",          ["clip_name1", "clip_name2"]),
            "vae":        ("VAELoader",               ["vae_name"]),
            "lora":       ("LoraLoaderModelOnly",     ["lora_name"]),
            "controlnet": ("ControlNetLoader",        ["control_net_name"]),
            "pulid":      ("PulidFluxModelLoader",    ["pulid_file"]),
            "ipadapter":  ("IPAdapterModelLoader",    ["ipadapter_file"]),
        }
        entry = lookups.get(kind)
        if entry is None:
            return []
        node_type, input_keys = entry
        try:
            info = self.object_info()
            node = info.get(node_type)
            if not node:
                return []
            required = node["input"]["required"]
            names: set[str] = set()
            for key in input_keys:
                if key in required:
                    opts = required[key][0]
                    if isinstance(opts, list):
                        names.update(opts)
            return sorted(names)
        except (KeyError, IndexError, TypeError):
            return []

    def upload_image(self, image: Image.Image | bytes, filename: str, *, image_type: str = "input", overwrite: bool = True) -> dict[str, Any]:
        """Upload an image to ComfyUI's input/temp folder. Returns the JSON
        response which includes the filename/subfolder/type the workflow should
        reference."""
        if isinstance(image, Image.Image):
            buf = io.BytesIO()
            image.save(buf, format="PNG")
            buf.seek(0)
            payload: Any = buf
        else:
            payload = io.BytesIO(image)
        files = {"image": (filename, payload, "image/png")}
        data = {"type": image_type, "overwrite": "true" if overwrite else "false"}
        return self._post("/upload/image", files=files, data=data).json()

    def queue_prompt(self, workflow: dict[str, Any]) -> str:
        """Enqueue a workflow. Returns the ``prompt_id``."""
        body = {"prompt": workflow, "client_id": self.client_id}
        resp = self._post("/prompt", json_body=body).json()
        if "prompt_id" not in resp:
            raise ComfyUIError(f"ComfyUI rejected workflow: {resp}")
        return resp["prompt_id"]

    def history(self, prompt_id: str) -> dict[str, Any]:
        data = self._get(f"/history/{prompt_id}").json()
        return data.get(prompt_id, {})

    def view_image(self, filename: str, subfolder: str = "", image_type: str = "output") -> Image.Image:
        params = {"filename": filename, "subfolder": subfolder, "type": image_type}
        resp = self._get("/view", params=params, stream=True)
        return Image.open(io.BytesIO(resp.content)).copy()

    # ---------- WebSocket-driven execution ----------
    def _open_ws(self) -> WebSocket:
        ws_url = _ws_url_for(self.base_url) + f"?clientId={self.client_id}"
        header = [f"Authorization: Bearer {self.auth_token}"] if self.auth_token else None
        try:
            return create_connection(
                ws_url,
                header=header,
                sslopt={"cert_reqs": 0} if not self.verify_tls else None,
                timeout=self.timeout,
            )
        except (WebSocketException, OSError) as exc:
            raise ComfyUIError(f"WebSocket connect failed: {exc}") from exc

    def run(
        self,
        workflow: dict[str, Any],
        *,
        progress_cb=None,
        wait_timeout: float = 600.0,
    ) -> list[GeneratedImage]:
        """Queue a workflow and block until it finishes. Returns every image
        produced by the run, in node-execution order.

        ``progress_cb`` is called with ``(step, total, node_id)`` on each
        reported progress event — used to update the Gradio UI.
        """
        prompt_id = self.queue_prompt(workflow)
        ws = self._open_ws()
        deadline = time.monotonic() + wait_timeout
        try:
            while True:
                if time.monotonic() > deadline:
                    raise ComfyUIError(f"Timed out waiting for prompt {prompt_id}")
                try:
                    ws.settimeout(min(5.0, deadline - time.monotonic()))
                    msg = ws.recv()
                except WebSocketException as exc:
                    raise ComfyUIError(f"WebSocket error: {exc}") from exc
                if not isinstance(msg, str):
                    # Binary preview frames — ignore.
                    continue
                try:
                    event = json.loads(msg)
                except json.JSONDecodeError:
                    continue
                ev_type = event.get("type")
                data = event.get("data", {})
                if ev_type == "progress" and progress_cb is not None:
                    progress_cb(data.get("value", 0), data.get("max", 0), data.get("node"))
                elif ev_type == "executing" and data.get("prompt_id") == prompt_id and data.get("node") is None:
                    # null node == done
                    break
                elif ev_type == "execution_error" and data.get("prompt_id") == prompt_id:
                    raise ComfyUIError(f"ComfyUI execution error: {data}")
        finally:
            try:
                ws.close()
            except Exception:
                pass
        return list(self._collect_outputs(prompt_id))

    def _collect_outputs(self, prompt_id: str) -> Iterable[GeneratedImage]:
        hist = self.history(prompt_id)
        outputs = hist.get("outputs", {})
        # outputs is keyed by node id; preserve numeric order when possible.
        for node_id in sorted(outputs.keys(), key=lambda k: (len(k), k)):
            node_output = outputs[node_id]
            for img in node_output.get("images", []):
                yield GeneratedImage(
                    filename=img["filename"],
                    subfolder=img.get("subfolder", ""),
                    type=img.get("type", "output"),
                    image=self.view_image(img["filename"], img.get("subfolder", ""), img.get("type", "output")),
                )


def client_from_settings(settings) -> ComfyUIClient:
    """Convenience factory used by tabs."""
    return ComfyUIClient(
        base_url=settings.comfy_base_url,
        auth_token=settings.comfy_auth_token or None,
        verify_tls=settings.comfy_verify_tls,
    )
