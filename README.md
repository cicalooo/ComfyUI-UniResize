# ComfyUI-UniResize

Two focused ComfyUI utilities for resizing media and controlling generation dimensions.

## Nodes

### UniResize (Image/Mask)

An extension of ComfyUI's native Resize Image/Mask node that also outputs the actual resulting width and height. It supports images and masks, every native resize mode, and the native interpolation methods. Optionally, its final output can be center-cropped to dimensions divisible by 8, 16, 32, or 64.

Outputs: resized image/mask, width, and height.

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

UniResize reuses the core resize helpers from `comfy_extras/nodes_post_processing.py`, so its results stay identical to the native node.
