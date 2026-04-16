# ComfyUI Workflow Recipes

Ready-to-use workflow templates. Copy the workflow dict and modify parameters as needed.

## SDXL Text-to-Image

High-quality 1024x1024 generation with SDXL.

```python
workflow = {
    "1": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"},
    },
    "2": {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "text": "POSITIVE PROMPT HERE",
            "clip": ["1", 1],
        },
    },
    "3": {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "text": "ugly, blurry, low quality, deformed",
            "clip": ["1", 1],
        },
    },
    "4": {
        "class_type": "EmptyLatentImage",
        "inputs": {"width": 1024, "height": 1024, "batch_size": 1},
    },
    "5": {
        "class_type": "KSampler",
        "inputs": {
            "seed": 0,
            "steps": 25,
            "cfg": 7.0,
            "sampler_name": "euler_ancestral",
            "scheduler": "normal",
            "denoise": 1.0,
            "model": ["1", 0],
            "positive": ["2", 0],
            "negative": ["3", 0],
            "latent_image": ["4", 0],
        },
    },
    "6": {
        "class_type": "VAEDecode",
        "inputs": {"samples": ["5", 0], "vae": ["1", 2]},
    },
    "7": {
        "class_type": "SaveImage",
        "inputs": {"filename_prefix": "hermes_sdxl", "images": ["6", 0]},
    },
}
```

Parameters to customize:
- Node "2" text → positive prompt
- Node "3" text → negative prompt
- Node "1" ckpt_name → model (use `list_models("checkpoints")`)
- Node "4" width/height → image dimensions (SDXL: 1024x1024, 1152x896, 896x1152)
- Node "5" seed → 0 for random, fixed int for reproducible
- Node "5" steps → 20-30 typical, higher = slower + more detail
- Node "5" cfg → 5-9 typical, higher = stronger prompt adherence

## Image-to-Image (img2img)

Load an input image and generate a variation.

```python
workflow = {
    "1": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"},
    },
    "2": {
        "class_type": "LoadImage",
        "inputs": {"image": "input_image.png"},
    },
    "3": {
        "class_type": "VAEEncode",
        "inputs": {"pixels": ["2", 0], "vae": ["1", 2]},
    },
    "4": {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": "POSITIVE PROMPT", "clip": ["1", 1]},
    },
    "5": {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": "ugly, blurry", "clip": ["1", 1]},
    },
    "6": {
        "class_type": "KSampler",
        "inputs": {
            "seed": 0,
            "steps": 20,
            "cfg": 7.0,
            "sampler_name": "euler",
            "scheduler": "normal",
            "denoise": 0.6,
            "model": ["1", 0],
            "positive": ["4", 0],
            "negative": ["5", 0],
            "latent_image": ["3", 0],
        },
    },
    "7": {
        "class_type": "VAEDecode",
        "inputs": {"samples": ["6", 0], "vae": ["1", 2]},
    },
    "8": {
        "class_type": "SaveImage",
        "inputs": {"filename_prefix": "hermes_img2img", "images": ["7", 0]},
    },
}

# Upload the input image first
upload_image("/path/to/input_image.png")
```

Key parameter: **denoise** (node "6", 0.0-1.0)
- 0.3 = subtle changes, preserve most of input
- 0.6 = moderate changes, good balance
- 0.9 = heavy changes, almost txt2img

## Upscale (2x with model)

```python
workflow = {
    "1": {
        "class_type": "LoadImage",
        "inputs": {"image": "image_to_upscale.png"},
    },
    "2": {
        "class_type": "UpscaleModelLoader",
        "inputs": {"model_name": "RealESRGAN_x4plus.pth"},
    },
    "3": {
        "class_type": "ImageUpscaleWithModel",
        "inputs": {"upscale_model": ["2", 0], "image": ["1", 0]},
    },
    "4": {
        "class_type": "ImageScale",
        "inputs": {
            "image": ["3", 0],
            "upscale_method": "lanczos",
            "width": 2048,
            "height": 2048,
            "crop": "disabled",
        },
    },
    "5": {
        "class_type": "SaveImage",
        "inputs": {"filename_prefix": "hermes_upscaled", "images": ["4", 0]},
    },
}
```

Upscale models: `list_models("upscale_models")`. Common: RealESRGAN_x4plus, 4x-UltraSharp.

## Flux Text-to-Image

For Flux models (requires Flux-compatible checkpoint).

```python
workflow = {
    "1": {
        "class_type": "UNETLoader",
        "inputs": {
            "unet_name": "flux1-dev.safetensors",
            "weight_dtype": "default",
        },
    },
    "2": {
        "class_type": "DualCLIPLoader",
        "inputs": {
            "clip_name1": "t5xxl_fp16.safetensors",
            "clip_name2": "clip_l.safetensors",
            "type": "flux",
        },
    },
    "3": {
        "class_type": "VAELoader",
        "inputs": {"vae_name": "ae.safetensors"},
    },
    "4": {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": "PROMPT HERE", "clip": ["2", 0]},
    },
    "5": {
        "class_type": "EmptySD3LatentImage",
        "inputs": {"width": 1024, "height": 1024, "batch_size": 1},
    },
    "6": {
        "class_type": "KSampler",
        "inputs": {
            "seed": 0,
            "steps": 20,
            "cfg": 1.0,
            "sampler_name": "euler",
            "scheduler": "simple",
            "denoise": 1.0,
            "model": ["1", 0],
            "positive": ["4", 0],
            "negative": ["4", 0],
            "latent_image": ["5", 0],
        },
    },
    "7": {
        "class_type": "VAEDecode",
        "inputs": {"samples": ["6", 0], "vae": ["3", 0]},
    },
    "8": {
        "class_type": "SaveImage",
        "inputs": {"filename_prefix": "hermes_flux", "images": ["7", 0]},
    },
}
```

Flux notes:
- Uses UNETLoader + DualCLIPLoader + VAELoader (not CheckpointLoaderSimple)
- CFG is typically 1.0 (Flux uses guidance differently)
- Negative prompt has minimal effect — link to same CLIP output as positive
- Requires: flux1-dev.safetensors, t5xxl_fp16.safetensors, clip_l.safetensors, ae.safetensors

## ControlNet (Canny Edge)

```python
workflow = {
    "1": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"},
    },
    "2": {
        "class_type": "LoadImage",
        "inputs": {"image": "control_input.png"},
    },
    "3": {
        "class_type": "CannyEdgePreprocessor",
        "inputs": {
            "image": ["2", 0],
            "low_threshold": 100,
            "high_threshold": 200,
            "resolution": 1024,
        },
    },
    "4": {
        "class_type": "ControlNetLoader",
        "inputs": {"control_net_name": "diffusers_xl_canny_full.safetensors"},
    },
    "5": {
        "class_type": "ControlNetApplyAdvanced",
        "inputs": {
            "strength": 0.8,
            "start_percent": 0.0,
            "end_percent": 1.0,
            "positive": ["6", 0],
            "negative": ["7", 0],
            "control_net": ["4", 0],
            "image": ["3", 0],
        },
    },
    "6": {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": "POSITIVE PROMPT", "clip": ["1", 1]},
    },
    "7": {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": "ugly, blurry", "clip": ["1", 1]},
    },
    "8": {
        "class_type": "EmptyLatentImage",
        "inputs": {"width": 1024, "height": 1024, "batch_size": 1},
    },
    "9": {
        "class_type": "KSampler",
        "inputs": {
            "seed": 0, "steps": 25, "cfg": 7.0,
            "sampler_name": "euler_ancestral", "scheduler": "normal",
            "denoise": 1.0,
            "model": ["1", 0],
            "positive": ["5", 0],
            "negative": ["5", 1],
            "latent_image": ["8", 0],
        },
    },
    "10": {
        "class_type": "VAEDecode",
        "inputs": {"samples": ["9", 0], "vae": ["1", 2]},
    },
    "11": {
        "class_type": "SaveImage",
        "inputs": {"filename_prefix": "hermes_canny", "images": ["10", 0]},
    },
}
```

Requires custom node: `comfyui_controlnet_aux` for CannyEdgePreprocessor.
Strength 0.5-0.9 typical. Higher = stricter adherence to control image.

## Workflow Execution Pattern

All recipes follow the same execution pattern:

```python
pid = queue_prompt(workflow)
print(f"Queued: {pid}")

result = wait_for_completion(pid, timeout=300)

# Download all output images
for node_id, node_output in result["outputs"].items():
    if "images" in node_output:
        for img_info in node_output["images"]:
            data = get_image(img_info["filename"], img_info["subfolder"], img_info["type"])
            local_path = f"/tmp/{img_info['filename']}"
            with open(local_path, "wb") as f:
                f.write(data)
            print(f"Saved: {local_path} ({len(data)} bytes)")
```
