---
name: comfyui
description: Control ComfyUI via REST API — queue workflows, generate images/video, manage models.
version: 1.0.0
requires: ComfyUI running locally or remotely (default http://127.0.0.1:8188)
author: kshitijk4poor
license: MIT
metadata:
  hermes:
    tags: [comfyui, image-generation, stable-diffusion, flux, creative, generative-ai]
    related_skills: [blender-mcp, stable-diffusion, image_gen]
    category: creative
---

# ComfyUI

Control a running ComfyUI instance from Hermes via its REST API. Queue workflow prompts, generate images and video, upload inputs, check progress, and retrieve outputs — all through `execute_code`.

## When to Use

- User asks to generate images with Stable Diffusion, SDXL, Flux, or other diffusion models
- User wants to run a specific ComfyUI workflow
- User wants to chain generative steps (txt2img → upscale → face restore)
- User needs ControlNet, inpainting, img2img, or other advanced pipelines
- User asks to manage ComfyUI queue or check generation progress

## Setup (one-time)

### 1. Install ComfyUI

    git clone https://github.com/comfyanonymous/ComfyUI.git
    cd ComfyUI
    pip install -r requirements.txt

### 2. Start the server

    python main.py --listen 127.0.0.1 --port 8188

For GPU acceleration add `--cuda-device 0` or let it auto-detect.

### 3. Verify connection

```python
from hermes_tools import terminal
r = terminal("curl -s http://127.0.0.1:8188/system_stats | python3 -m json.tool | head -5")
print(r["output"])
```

You should see system info with OS, Python version, VRAM, etc.

## Core Pattern — ComfyUI Helper

Use this helper inside `execute_code` for all ComfyUI interactions:

```python
import json, time, urllib.request, urllib.error, urllib.parse, uuid, os

COMFY_URL = os.getenv("COMFYUI_URL", "http://127.0.0.1:8188")

def comfy_api(method, path, data=None, timeout=30):
    """Send a request to the ComfyUI API."""
    url = f"{COMFY_URL}{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    if body:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())

def queue_prompt(workflow, client_id=None):
    """Queue a workflow for execution. Returns prompt_id."""
    client_id = client_id or str(uuid.uuid4())
    result = comfy_api("POST", "/prompt", {
        "prompt": workflow,
        "client_id": client_id,
    })
    return result["prompt_id"]

def wait_for_completion(prompt_id, timeout=300, poll_interval=2):
    """Poll /history until the prompt completes. Returns output dict."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        history = comfy_api("GET", f"/history/{prompt_id}")
        if prompt_id in history:
            return history[prompt_id]
        time.sleep(poll_interval)
    raise TimeoutError(f"Prompt {prompt_id} did not complete in {timeout}s")

def get_image(filename, subfolder="", img_type="output"):
    """Download a generated image. Returns bytes."""
    params = urllib.parse.urlencode({
        "filename": filename, "subfolder": subfolder, "type": img_type
    })
    url = f"{COMFY_URL}/view?{params}"
    with urllib.request.urlopen(url) as resp:
        return resp.read()

def upload_image(filepath, img_type="input", overwrite=True):
    """Upload an image to ComfyUI. Returns server-side filename."""
    import mimetypes
    boundary = uuid.uuid4().hex
    filename = os.path.basename(filepath)
    mime = mimetypes.guess_type(filepath)[0] or "image/png"

    with open(filepath, "rb") as f:
        file_data = f.read()

    parts = []
    parts.append(f"--{boundary}\r\n"
                 f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
                 f"Content-Type: {mime}\r\n\r\n".encode())
    parts.append(file_data)
    parts.append(f"\r\n--{boundary}\r\n"
                 f'Content-Disposition: form-data; name="type"\r\n\r\n'
                 f"{img_type}\r\n"
                 f"--{boundary}\r\n"
                 f'Content-Disposition: form-data; name="overwrite"\r\n\r\n'
                 f"{'true' if overwrite else 'false'}\r\n"
                 f"--{boundary}--\r\n".encode())
    body = b"".join(parts)

    req = urllib.request.Request(
        f"{COMFY_URL}/upload/image", data=body, method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

def list_models(folder="checkpoints"):
    """List available models in a folder (checkpoints, loras, vae, etc.)."""
    return comfy_api("GET", f"/models/{folder}")

def get_queue_status():
    """Get current queue (running + pending)."""
    return comfy_api("GET", "/queue")

def interrupt():
    """Interrupt the currently running generation."""
    return comfy_api("POST", "/interrupt")
```

## Common Workflows

### Text-to-Image (Minimal)

```python
workflow = {
    "3": {
        "class_type": "KSampler",
        "inputs": {
            "seed": 42,
            "steps": 20,
            "cfg": 7.5,
            "sampler_name": "euler",
            "scheduler": "normal",
            "denoise": 1.0,
            "model": ["4", 0],
            "positive": ["6", 0],
            "negative": ["7", 0],
            "latent_image": ["5", 0],
        },
    },
    "4": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {"ckpt_name": "v1-5-pruned-emaonly.safetensors"},
    },
    "5": {
        "class_type": "EmptyLatentImage",
        "inputs": {"width": 512, "height": 512, "batch_size": 1},
    },
    "6": {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "text": "a beautiful sunset over mountains, photorealistic",
            "clip": ["4", 1],
        },
    },
    "7": {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "text": "ugly, blurry, low quality",
            "clip": ["4", 1],
        },
    },
    "8": {
        "class_type": "VAEDecode",
        "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
    },
    "9": {
        "class_type": "SaveImage",
        "inputs": {"filename_prefix": "hermes", "images": ["8", 0]},
    },
}

pid = queue_prompt(workflow)
result = wait_for_completion(pid)

# Extract output image filename
outputs = result["outputs"]
for node_id, node_output in outputs.items():
    if "images" in node_output:
        for img in node_output["images"]:
            img_data = get_image(img["filename"], img["subfolder"], img["type"])
            with open(f"/tmp/{img['filename']}", "wb") as f:
                f.write(img_data)
            print(f"Saved: /tmp/{img['filename']}")
```

### Parameterized Generation

When the user asks to generate an image, build the workflow by modifying the template:
- **Prompt**: Set node "6" inputs.text to the user's positive prompt
- **Negative**: Set node "7" inputs.text (default: "ugly, blurry, low quality")
- **Model**: Set node "4" inputs.ckpt_name (use `list_models()` to find available ones)
- **Size**: Set node "5" inputs.width/height
- **Steps/CFG**: Set node "3" inputs.steps and inputs.cfg
- **Seed**: Set node "3" inputs.seed (random for variation, fixed for reproducibility)

### Loading User Workflows

Users often have saved workflow JSON files. Two formats exist:

1. **API format** — flat node dict, directly usable with `queue_prompt()`:
   ```python
   with open("workflow_api.json") as f:
       workflow = json.load(f)
   pid = queue_prompt(workflow)
   ```

2. **UI format** — includes visual layout, NOT directly usable. Look for the
   `"prompt"` key inside the exported data, or ask the user to export as API format
   from ComfyUI's menu: Save (API Format).

### Checking Available Nodes

```python
# List all available node types
info = comfy_api("GET", "/object_info")
print(f"Total node types: {len(info)}")

# Get info for a specific node
ksampler_info = comfy_api("GET", "/object_info/KSampler")
print(json.dumps(ksampler_info, indent=2)[:500])
```

## Queue Management

```python
# Check what's running/pending
status = get_queue_status()
running = status.get("queue_running", [])
pending = status.get("queue_pending", [])
print(f"Running: {len(running)}, Pending: {len(pending)}")

# Cancel everything
if pending:
    comfy_api("POST", "/queue", {"clear": True})

# Interrupt current generation
interrupt()
```

## Advanced: Native MCP Server Integration

For deeper integration with dedicated MCP tools, configure an external ComfyUI
MCP server in `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  comfyui:
    command: "npx"
    args: ["-y", "comfyui-mcp-server"]
    env:
      COMFYUI_URL: "http://127.0.0.1:8188"
```

This registers ComfyUI operations as native Hermes tools (prefixed `mcp_comfyui_*`).
See the `native-mcp` skill for MCP server configuration details.

Recommended MCP servers:
- `comfyui-mcp-server` (joenorton, 281★) — workflow-file driven, asset management
- `comfy-pilot` (169★) — node-level graph editing, requires ComfyUI plugin

## Pitfalls

See `references/pitfalls.md` for 10 common pitfalls with solutions. Key ones:

- **API vs UI format** — only API format works with POST /prompt
- **Node IDs are strings** — `"3"` not `3`
- **Model names must be exact** — use `list_models()` first
- **VRAM exhaustion** — use `--lowvram` or free models between generations
- **Custom node not found** — install missing pack via ComfyUI Manager
