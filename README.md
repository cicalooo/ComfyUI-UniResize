# ComfyUI-UniResize

Three focused ComfyUI utilities for loading and resizing media and controlling generation dimensions.

## Nodes

### UniResize (Image/Mask)

An extension of ComfyUI's native Resize Image/Mask node that also outputs the actual resulting width and height. It supports images and masks, every native resize mode, and the native interpolation methods. Optionally, its final output can be center-cropped to dimensions divisible by 8, 16, 32, or 64.

Outputs: resized image/mask, width, and height.

Defaults: `scale_method` is **bicubic** and `adhere_to_multiple` is **32**. Dimension fields default to 1024.

### UniLoad (Load + Resize)

Load Image and UniResize combined into one node, so the common "load a reference, then fit it to the target resolution" step costs one node instead of two.

It carries the same image picker and upload button as the native Load Image node, followed by the full UniResize control set:

- **resize_type** — `disabled` (default) plus every UniResize mode: custom width/height, scale by multiplier, longer/shorter edge, width only, height only, total megapixels, match another image's size, and scale to multiple.
- **crop** — `disabled` stretches, `center` crops to preserve aspect ratio. Shown for the modes where both dimensions are pinned (custom w/h and match size).
- **scale_method** — interpolation algorithm, default **bicubic**.
- **adhere_to_multiple** — center-crop the result to dimensions divisible by 8, 16, 32, or 64, default **32**.

Outputs: image, mask, width, and height.

The mask goes through the exact same geometry as the image, so it stays aligned after any resize. When the source file has no alpha channel, Load Image returns a 64×64 placeholder mask; UniLoad expands that to the image's size before resizing so the two never drift apart. With `resize_type` set to `disabled` and `adhere_to_multiple` set to `disabled`, the node returns exactly what the native Load Image node would.

### UniRatio (Width/Height)

A compact, model-aware ratio and resolution controller with exactly two outputs: width and height.

The node shows a short resolution summary, a visible **upscale** multiplier, and a single **Change resolution** button. The button opens a searchable, nested browser grouped into General, Image, and Video profiles, so adding presets does not make the graph node or a dropdown menu enormous. Manual width and height entry lives at the top of this browser.

Included profile families:

- General 512 and 1-megapixel translation
- Stable Diffusion 1.x/2.x, SDXL, and SD3/3.5
- FLUX and Qwen Image
- Wan 480p and 720p
- HunyuanVideo
- LTX-Video
- CogVideoX
- Mochi

Known/native pairs are returned exactly. Other available ratios are calculated from the profile's target pixel area and snapped to its required spatial multiple. The optional 0.01–8.0 upscale multiplier is applied afterward and preset results remain aligned to the selected model profile. Manual dimensions remain pixel-exact. The Python backend performs and validates the calculation; JavaScript only supplies the compact browser.

The saved workflow stores a stable key such as `wan_720:16-9`, rather than a display label. If the frontend extension cannot load, the standard selection widget remains a functional fallback.

## Install

Clone or copy this folder into `ComfyUI/custom_nodes/` and restart ComfyUI. There are no dependencies beyond ComfyUI itself.

UniResize and UniLoad reuse the core resize helpers from `comfy_extras/nodes_post_processing.py`, and UniLoad reuses the native `LoadImage` loader, so their results stay identical to the native nodes.
