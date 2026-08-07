# ComfyUI-UniResize

Three focused ComfyUI utilities for loading and resizing images and controlling
generation dimensions. All three share one control set and one implementation;
the resize maths is ComfyUI's own, from `comfy_extras/nodes_post_processing.py`.

No dependencies, no custom JavaScript, no catalog files.

## The shared control set

`UniLoad` and `UniResize` take the same three controls:

- **resize_type** — custom width/height, scale by multiplier, longer/shorter
  edge, width only, height only, total megapixels, match another image's size,
  and scale to multiple. `UniLoad` adds `disabled` (its default), because
  loading is the point of that node and resizing is opt-in.
- **crop** — `disabled` stretches, `center` crops to preserve aspect ratio.
  Shown only for the modes that pin both dimensions.
- **scale_method** — interpolation, default **bicubic**.
- **adhere_to_multiple** — center-crop the result to dimensions divisible by
  8, 16, 32, or 64. Default **32**.

## Nodes

### UniLoad (Load + Resize)

Load Image and UniResize in one node, so "load a reference, fit it to the target
resolution" costs one node instead of two. Same picker and upload button as the
native Load Image.

Outputs: **image, mask, width, height**.

The mask goes through the exact same geometry as the image, so it stays aligned
after any resize. When the source has no alpha channel, `LoadImage` returns a
64×64 placeholder mask; UniLoad expands it to the image's size first so the two
cannot drift apart. With `resize_type` and `adhere_to_multiple` both `disabled`,
the node returns exactly what native Load Image would.

### UniResize (Image)

The same controls without the loading, for an image already in the graph.

Outputs: **image, width, height**.

Images only. To resize a mask, convert with the native `MaskToImage` /
`ImageToMask`, or run it through `UniLoad`.

### UniRatio (Width/Height)

A resolution source with no image attached. It offers the **same sizing rules**
as the resize nodes — a pixel budget is one option among eight, not the only way
in.

| Widget | Meaning |
|---|---|
| `aspect_ratio` | `1:1`, `4:3`, `3:4`, `3:2`, `2:3`, `16:9`, `9:16`, `21:9`, `9:21` |
| `size_by` | which rule fixes the size (below) |
| `multiple` | grid both edges land on: 8, 16, 32, 64, or `disabled` for exact pixels |

Portrait ratios are listed separately, so there is no orientation switch.

`size_by` uses core's own `ResizeType` names, so the dropdown reads the same as
in UniResize and UniLoad:

| Rule | You give | Aspect ratio supplies |
|---|---|---|
| `scale total pixels` | megapixels | both edges |
| `scale longer dimension` | longer_size | the shorter edge |
| `scale shorter dimension` | shorter_size | the longer edge |
| `scale width` | width | the height |
| `scale height` | height | the width |
| `scale dimensions` | width + height | nothing — ignored |
| `match size` | a reference image/mask | nothing — ignored |
| `scale by multiplier` | a reference + multiplier | nothing — ignored |

`scale to multiple` is not in this list because here it is the always-on
`multiple` widget rather than a way to choose a size.

**Edge-pinned rules keep your number.** `scale width 1344` at `16:9` gives
exactly 1344×768. Only `scale total pixels` trades both edges off against each
other, because only there is the target a product rather than a length —
rounding each edge independently lets one direction dominate on cinematic
formats, so the neighbourhood around the naive pair is scored on combined area
and aspect error. `16:9` at 1.0 MP on a 32px grid gives 1312×736: 0.97 MP,
aspect error under 0.3%.

There are no model profiles, because a model profile was only ever a target
area or a target edge:

| Target | rule |
|---|---|
| SD 1.5 era | `scale total pixels` 0.26, grid 8 |
| SDXL, SD3, FLUX, Qwen Image | `scale total pixels` 1.0, grid 8 or 64 |
| Wan / video 480p | `scale shorter dimension` 480, grid 32 |
| Wan / video 720p | `scale shorter dimension` 720, grid 32 |
| MiniMax H3 | `scale width` 1344 at 16:9, grid 32 |

### Driving a generator's resolution

`UniRatio` is meant to be wired into whatever sizes your generation. For
MiniMax H3, `ComfyUI-EZ-H3`'s `EZ H3 Prompt` and `EZ H3 Shape` expose link-only
`width`/`height` inputs that override their `aspect_ratio` widget:

```
UniRatio ──width──►  EZ H3 Prompt  ──prompt/width/height/length──► MiniMax H3
         └─height──►
```

## Install

Copy this folder into `ComfyUI/custom_nodes/` and restart ComfyUI.
