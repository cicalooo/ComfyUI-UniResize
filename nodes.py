import os

import torch
from typing import TypedDict, Literal

import folder_paths
from comfy_api.latest import io
from nodes import MAX_RESOLUTION, LoadImage

from comfy_extras.nodes_post_processing import (
    ResizeType,
    is_image,
    scale_by,
    scale_dimensions,
    scale_longer_dimension,
    scale_shorter_dimension,
    scale_total_pixels,
    scale_match_size,
    scale_to_multiple_cover,
)

from .resolutions import EXPLICIT_MODES, MULTIPLES, RATIO_NAMES, solve


SCALE_METHODS = ["nearest-exact", "bilinear", "area", "bicubic", "lanczos"]
CROP_METHODS = ["disabled", "center"]
OUTPUT_MULTIPLES = ["disabled", "8", "16", "32", "64"]

# Extra "no-op" key for nodes where resizing is opt-in rather than the point of the node.
RESIZE_DISABLED = "disabled"


class ResizeTypedDict(TypedDict):
    resize_type: ResizeType
    scale_method: Literal["nearest-exact", "bilinear", "area", "bicubic", "lanczos"]
    crop: Literal["disabled", "center"]
    multiplier: float
    width: int
    height: int
    longer_size: int
    shorter_size: int
    megapixels: float
    multiple: int


def resize_options(include_disabled: bool = False, include_match: bool = True) -> list[io.DynamicCombo.Option]:
    """Build the shared resize_type option set. The first option is what the widget defaults to."""
    crop_combo = io.Combo.Input(
        "crop",
        options=CROP_METHODS,
        default="center",
        tooltip="How to handle aspect ratio mismatch: 'disabled' stretches to fit, 'center' crops to maintain aspect ratio.",
    )
    options = []
    if include_disabled:
        options.append(io.DynamicCombo.Option(RESIZE_DISABLED, []))
    options.extend([
        io.DynamicCombo.Option(ResizeType.SCALE_DIMENSIONS, [
            io.Int.Input("width", default=1024, min=0, max=MAX_RESOLUTION, step=1, tooltip="Target width in pixels. Set to 0 to auto-calculate from height while preserving aspect ratio."),
            io.Int.Input("height", default=1024, min=0, max=MAX_RESOLUTION, step=1, tooltip="Target height in pixels. Set to 0 to auto-calculate from width while preserving aspect ratio."),
            crop_combo,
        ]),
        io.DynamicCombo.Option(ResizeType.SCALE_BY, [
            io.Float.Input("multiplier", default=1.00, min=0.01, max=8.0, step=0.01, tooltip="Scale factor (e.g., 2.0 doubles size, 0.5 halves size)."),
        ]),
        io.DynamicCombo.Option(ResizeType.SCALE_LONGER_DIMENSION, [
            io.Int.Input("longer_size", default=1024, min=0, max=MAX_RESOLUTION, step=1, tooltip="The longer edge will be resized to this value. Aspect ratio is preserved."),
        ]),
        io.DynamicCombo.Option(ResizeType.SCALE_SHORTER_DIMENSION, [
            io.Int.Input("shorter_size", default=1024, min=0, max=MAX_RESOLUTION, step=1, tooltip="The shorter edge will be resized to this value. Aspect ratio is preserved."),
        ]),
        io.DynamicCombo.Option(ResizeType.SCALE_WIDTH, [
            io.Int.Input("width", default=1024, min=0, max=MAX_RESOLUTION, step=1, tooltip="Target width in pixels. Height auto-adjusts to preserve aspect ratio."),
        ]),
        io.DynamicCombo.Option(ResizeType.SCALE_HEIGHT, [
            io.Int.Input("height", default=1024, min=0, max=MAX_RESOLUTION, step=1, tooltip="Target height in pixels. Width auto-adjusts to preserve aspect ratio."),
        ]),
        io.DynamicCombo.Option(ResizeType.SCALE_TOTAL_PIXELS, [
            io.Float.Input("megapixels", default=1.0, min=0.01, max=16.0, step=0.01, tooltip="Target total megapixels (e.g., 1.0 ≈ 1024×1024). Aspect ratio is preserved."),
        ]),
    ])
    if include_match:
        options.append(io.DynamicCombo.Option(ResizeType.MATCH_SIZE, [
            io.MultiType.Input("match", [io.Image, io.Mask], tooltip="Resize input to match the dimensions of this reference image or mask."),
            crop_combo,
        ]))
    options.append(io.DynamicCombo.Option(ResizeType.SCALE_TO_MULTIPLE, [
        io.Int.Input("multiple", default=32, min=1, max=MAX_RESOLUTION, step=1, tooltip="Resize so width and height are divisible by this number. Useful for latent alignment (e.g., 8 or 64)."),
    ]))
    return options


def size_by_options() -> list[io.DynamicCombo.Option]:
    """UniRatio's sizing rules: the same vocabulary, minus the input image.

    Every entry is a ``ResizeType`` value so the dropdown reads identically to
    UniResize and UniLoad. ``scale to multiple`` is absent because it is the
    always-on ``multiple`` widget here rather than a way to choose a size.
    """
    match_input = io.MultiType.Input(
        "match", [io.Image, io.Mask],
        tooltip="Reference to take dimensions from. Aspect ratio is ignored.",
    )
    return [
        io.DynamicCombo.Option(ResizeType.SCALE_TOTAL_PIXELS, [
            io.Float.Input("megapixels", default=1.0, min=0.01, max=16.0, step=0.01, tooltip="Total pixel budget. 1.0 is roughly 1024x1024; 0.26 is roughly 512x512."),
        ]),
        io.DynamicCombo.Option(ResizeType.SCALE_LONGER_DIMENSION, [
            io.Int.Input("longer_size", default=1024, min=1, max=MAX_RESOLUTION, step=1, tooltip="The longer edge lands on exactly this (after grid snapping); the shorter edge follows the aspect ratio."),
        ]),
        io.DynamicCombo.Option(ResizeType.SCALE_SHORTER_DIMENSION, [
            io.Int.Input("shorter_size", default=768, min=1, max=MAX_RESOLUTION, step=1, tooltip="The shorter edge lands on exactly this (after grid snapping); the longer edge follows the aspect ratio."),
        ]),
        io.DynamicCombo.Option(ResizeType.SCALE_WIDTH, [
            io.Int.Input("width", default=1024, min=1, max=MAX_RESOLUTION, step=1, tooltip="Width is pinned; height follows the aspect ratio."),
        ]),
        io.DynamicCombo.Option(ResizeType.SCALE_HEIGHT, [
            io.Int.Input("height", default=1024, min=1, max=MAX_RESOLUTION, step=1, tooltip="Height is pinned; width follows the aspect ratio."),
        ]),
        io.DynamicCombo.Option(ResizeType.SCALE_DIMENSIONS, [
            io.Int.Input("width", default=1344, min=1, max=MAX_RESOLUTION, step=1, tooltip="Exact width. Aspect ratio is ignored."),
            io.Int.Input("height", default=768, min=1, max=MAX_RESOLUTION, step=1, tooltip="Exact height. Aspect ratio is ignored."),
        ]),
        io.DynamicCombo.Option(ResizeType.MATCH_SIZE, [match_input]),
        io.DynamicCombo.Option(ResizeType.SCALE_BY, [
            match_input,
            io.Float.Input("multiplier", default=1.0, min=0.01, max=8.0, step=0.01, tooltip="Scale factor applied to the reference's size."),
        ]),
    ]


def scale_method_input() -> io.Combo.Input:
    return io.Combo.Input(
        "scale_method",
        options=SCALE_METHODS,
        default="bicubic",
        tooltip="Interpolation algorithm. 'area' is best for downscaling, 'lanczos' for upscaling, 'nearest-exact' for pixel art.",
    )


def adhere_to_multiple_input() -> io.Combo.Input:
    return io.Combo.Input(
        "adhere_to_multiple",
        options=OUTPUT_MULTIPLES,
        default="32",
        tooltip="After resizing, center-crop to dimensions divisible by 8, 16, 32, or 64. Disabled preserves the exact requested size.",
    )


def is_resize_requested(resize_type: ResizeTypedDict, adhere_to_multiple: str) -> bool:
    return resize_type["resize_type"] != RESIZE_DISABLED or adhere_to_multiple != "disabled"


def apply_resize(
    input: torch.Tensor,
    resize_type: ResizeTypedDict,
    scale_method: str,
    adhere_to_multiple: str,
) -> torch.Tensor:
    """Run the selected resize op followed by the optional multiple-alignment pass."""
    selected_type = resize_type["resize_type"]
    if selected_type == RESIZE_DISABLED:
        result = input
    elif selected_type == ResizeType.SCALE_BY:
        result = scale_by(input, resize_type["multiplier"], scale_method)
    elif selected_type == ResizeType.SCALE_DIMENSIONS:
        result = scale_dimensions(input, resize_type["width"], resize_type["height"], scale_method, resize_type["crop"])
    elif selected_type == ResizeType.SCALE_LONGER_DIMENSION:
        result = scale_longer_dimension(input, resize_type["longer_size"], scale_method)
    elif selected_type == ResizeType.SCALE_SHORTER_DIMENSION:
        result = scale_shorter_dimension(input, resize_type["shorter_size"], scale_method)
    elif selected_type == ResizeType.SCALE_WIDTH:
        result = scale_dimensions(input, resize_type["width"], 0, scale_method)
    elif selected_type == ResizeType.SCALE_HEIGHT:
        result = scale_dimensions(input, 0, resize_type["height"], scale_method)
    elif selected_type == ResizeType.SCALE_TOTAL_PIXELS:
        result = scale_total_pixels(input, resize_type["megapixels"], scale_method)
    elif selected_type == ResizeType.MATCH_SIZE:
        result = scale_match_size(input, resize_type["match"], scale_method, resize_type["crop"])
    elif selected_type == ResizeType.SCALE_TO_MULTIPLE:
        result = scale_to_multiple_cover(input, resize_type["multiple"], scale_method)
    else:
        raise ValueError(f"Unsupported resize type: {selected_type}")

    if adhere_to_multiple != "disabled":
        result = scale_to_multiple_cover(result, int(adhere_to_multiple), scale_method)

    return result


def get_dimensions(output: torch.Tensor) -> tuple[int, int]:
    # images are [batch, height, width, channels], masks are [batch, height, width]
    if is_image(output):
        height, width = output.shape[1], output.shape[2]
    else:
        height, width = output.shape[-2], output.shape[-1]
    return int(width), int(height)


class UniResizeNode(io.ComfyNode):
    """Resize an image. Same controls as UniLoad, without the loading."""

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="UniResizeNode",
            display_name="UniResize (Image)",
            description="Resize an image using various scaling methods, and output the resulting width and height.",
            category="image/transform",
            essentials_category="Basics",
            search_aliases=[
                "uniresize", "resize", "resize image", "scale", "scale image",
                "image resize", "change size", "dimensions", "shrink", "enlarge",
            ],
            inputs=[
                io.Image.Input("image", tooltip="Image to resize."),
                io.DynamicCombo.Input(
                    "resize_type",
                    tooltip="Select how to resize: by exact dimensions, scale factor, matching another image, etc.",
                    options=resize_options(),
                ),
                scale_method_input(),
                adhere_to_multiple_input(),
            ],
            outputs=[
                io.Image.Output(display_name="image"),
                io.Int.Output(display_name="width"),
                io.Int.Output(display_name="height"),
            ],
        )

    @classmethod
    def execute(
        cls,
        image: io.Image.Type,
        scale_method: io.Combo.Type,
        adhere_to_multiple: io.Combo.Type,
        resize_type: ResizeTypedDict,
    ) -> io.NodeOutput:
        result = apply_resize(image, resize_type, scale_method, adhere_to_multiple)
        width, height = get_dimensions(result)
        return io.NodeOutput(result, width, height)


class UniLoadNode(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        input_dir = folder_paths.get_input_directory()
        files = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]
        files = folder_paths.filter_files_content_types(files, ["image"])
        return io.Schema(
            node_id="UniLoadNode",
            display_name="UniLoad (Load + Resize)",
            description="Load an image from the input folder and optionally resize it in the same node. The mask follows the image through every resize step.",
            category="image",
            essentials_category="Basics",
            search_aliases=[
                "uniload", "load image", "open image", "import image", "image input",
                "upload image", "read image", "image loader", "load and resize",
                "load image resize",
            ],
            inputs=[
                io.Combo.Input(
                    "image",
                    options=sorted(files),
                    upload=io.UploadType.image,
                    tooltip="Image file from the input folder. Use the upload button to add a new one.",
                ),
                io.DynamicCombo.Input(
                    "resize_type",
                    tooltip="How to resize after loading. 'disabled' returns the image at its original size.",
                    options=resize_options(include_disabled=True),
                ),
                scale_method_input(),
                adhere_to_multiple_input(),
            ],
            outputs=[
                io.Image.Output(display_name="image"),
                io.Mask.Output(display_name="mask"),
                io.Int.Output(display_name="width"),
                io.Int.Output(display_name="height"),
            ],
        )

    @classmethod
    def execute(
        cls,
        image: io.Combo.Type,
        scale_method: io.Combo.Type,
        adhere_to_multiple: io.Combo.Type,
        resize_type: ResizeTypedDict,
    ) -> io.NodeOutput:
        loaded_image, loaded_mask = LoadImage().load_image(image)

        if not is_resize_requested(resize_type, adhere_to_multiple):
            width, height = get_dimensions(loaded_image)
            return io.NodeOutput(loaded_image, loaded_mask, width, height)

        # LoadImage returns a 64x64 placeholder mask when the file has no alpha channel.
        # Expand it so the mask goes through the exact same geometry as the image.
        img_width, img_height = get_dimensions(loaded_image)
        if get_dimensions(loaded_mask) != (img_width, img_height):
            loaded_mask = torch.zeros(
                (loaded_image.shape[0], img_height, img_width),
                dtype=loaded_mask.dtype,
                device=loaded_mask.device,
            )

        result_image = apply_resize(loaded_image, resize_type, scale_method, adhere_to_multiple)
        result_mask = apply_resize(loaded_mask, resize_type, scale_method, adhere_to_multiple)

        width, height = get_dimensions(result_image)
        return io.NodeOutput(result_image, result_mask, width, height)

    @classmethod
    def fingerprint_inputs(cls, image, **kwargs):
        return LoadImage.IS_CHANGED(image)

    @classmethod
    def validate_inputs(cls, image, **kwargs):
        return LoadImage.VALIDATE_INPUTS(image)


class UniRatioNode(io.ComfyNode):
    """Aspect ratio + one sizing rule -> width, height.

    The rules are ComfyUI's own ``ResizeType`` values, so this node offers the
    same sizing choices as UniResize and UniLoad rather than forcing a
    megapixel budget. The aspect ratio fills in whatever the chosen rule leaves
    undetermined, and is ignored by the rules that pin both edges.
    """

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="UniRatioNode",
            display_name="UniRatio (Width/Height)",
            description="Resolution source: pick an aspect ratio and a sizing rule, get width and height on a chosen grid.",
            category="image/transform",
            essentials_category="Basics",
            search_aliases=[
                "uniratio", "ratio", "resolution", "width height", "aspect ratio",
                "dimensions", "megapixels", "empty latent size",
            ],
            inputs=[
                io.Combo.Input(
                    "aspect_ratio",
                    options=RATIO_NAMES,
                    default="16:9",
                    tooltip="Target shape. Portrait variants are listed separately, so no orientation switch is needed. Ignored by 'scale dimensions', 'match size' and 'scale by multiplier'.",
                ),
                io.DynamicCombo.Input(
                    "size_by",
                    tooltip="How to fix the size: total pixels, one edge, both edges, or another image's size.",
                    options=size_by_options(),
                ),
                io.Combo.Input(
                    "multiple",
                    options=MULTIPLES,
                    default="32",
                    tooltip="Both edges land on this grid. 8 suits SD/SDXL latents, 32 suits most video models. 'disabled' returns exact pixels.",
                ),
            ],
            outputs=[
                io.Int.Output(display_name="width"),
                io.Int.Output(display_name="height"),
            ],
        )

    @classmethod
    def execute(
        cls,
        aspect_ratio: io.Combo.Type,
        multiple: io.Combo.Type,
        size_by: dict,
    ) -> io.NodeOutput:
        mode = size_by["size_by"]
        reference = None
        if mode in EXPLICIT_MODES and "match" in size_by:
            match = size_by.get("match")
            if match is not None:
                reference = get_dimensions(match)

        width, height = solve(
            mode,
            aspect_ratio,
            1 if multiple == "disabled" else int(multiple),
            megapixels=size_by.get("megapixels", 1.0),
            longer_size=size_by.get("longer_size", 1024),
            shorter_size=size_by.get("shorter_size", 768),
            width=size_by.get("width", 1024),
            height=size_by.get("height", 1024),
            multiplier=size_by.get("multiplier", 1.0),
            reference=reference,
        )
        return io.NodeOutput(width, height)
