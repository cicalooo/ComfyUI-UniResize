import torch
from typing import TypedDict, Literal

from comfy_api.latest import io
from nodes import MAX_RESOLUTION

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

from .resolutions import selection_ids, resolve_dimensions


class UniResizeNode(io.ComfyNode):
    scale_methods = ["nearest-exact", "bilinear", "area", "bicubic", "lanczos"]
    crop_methods = ["disabled", "center"]
    output_multiples = ["disabled", "8", "16", "32", "64"]

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

    @classmethod
    def define_schema(cls):
        template = io.MatchType.Template("input_type", [io.Image, io.Mask])
        crop_combo = io.Combo.Input(
            "crop",
            options=cls.crop_methods,
            default="center",
            tooltip="How to handle aspect ratio mismatch: 'disabled' stretches to fit, 'center' crops to maintain aspect ratio.",
        )
        return io.Schema(
            node_id="UniResizeNode",
            display_name="UniResize (Image/Mask)",
            description="Resize an image or mask using various scaling methods, and output the resulting width and height.",
            category="image/transform",
            search_aliases=["uniresize", "resize", "resize image", "resize mask", "scale", "scale image", "scale mask", "image resize", "change size", "dimensions", "shrink", "enlarge"],
            inputs=[
                io.MatchType.Input("input", template=template),
                io.DynamicCombo.Input(
                    "resize_type",
                    tooltip="Select how to resize: by exact dimensions, scale factor, matching another image, etc.",
                    options=[
                        io.DynamicCombo.Option(ResizeType.SCALE_DIMENSIONS, [
                            io.Int.Input("width", default=512, min=0, max=MAX_RESOLUTION, step=1, tooltip="Target width in pixels. Set to 0 to auto-calculate from height while preserving aspect ratio."),
                            io.Int.Input("height", default=512, min=0, max=MAX_RESOLUTION, step=1, tooltip="Target height in pixels. Set to 0 to auto-calculate from width while preserving aspect ratio."),
                            crop_combo,
                        ]),
                        io.DynamicCombo.Option(ResizeType.SCALE_BY, [
                            io.Float.Input("multiplier", default=1.00, min=0.01, max=8.0, step=0.01, tooltip="Scale factor (e.g., 2.0 doubles size, 0.5 halves size)."),
                        ]),
                        io.DynamicCombo.Option(ResizeType.SCALE_LONGER_DIMENSION, [
                            io.Int.Input("longer_size", default=512, min=0, max=MAX_RESOLUTION, step=1, tooltip="The longer edge will be resized to this value. Aspect ratio is preserved."),
                        ]),
                        io.DynamicCombo.Option(ResizeType.SCALE_SHORTER_DIMENSION, [
                            io.Int.Input("shorter_size", default=512, min=0, max=MAX_RESOLUTION, step=1, tooltip="The shorter edge will be resized to this value. Aspect ratio is preserved."),
                        ]),
                        io.DynamicCombo.Option(ResizeType.SCALE_WIDTH, [
                            io.Int.Input("width", default=512, min=0, max=MAX_RESOLUTION, step=1, tooltip="Target width in pixels. Height auto-adjusts to preserve aspect ratio."),
                        ]),
                        io.DynamicCombo.Option(ResizeType.SCALE_HEIGHT, [
                            io.Int.Input("height", default=512, min=0, max=MAX_RESOLUTION, step=1, tooltip="Target height in pixels. Width auto-adjusts to preserve aspect ratio."),
                        ]),
                        io.DynamicCombo.Option(ResizeType.SCALE_TOTAL_PIXELS, [
                            io.Float.Input("megapixels", default=1.0, min=0.01, max=16.0, step=0.01, tooltip="Target total megapixels (e.g., 1.0 ≈ 1024×1024). Aspect ratio is preserved."),
                        ]),
                        io.DynamicCombo.Option(ResizeType.MATCH_SIZE, [
                            io.MultiType.Input("match", [io.Image, io.Mask], tooltip="Resize input to match the dimensions of this reference image or mask."),
                            crop_combo,
                        ]),
                        io.DynamicCombo.Option(ResizeType.SCALE_TO_MULTIPLE, [
                            io.Int.Input("multiple", default=8, min=1, max=MAX_RESOLUTION, step=1, tooltip="Resize so width and height are divisible by this number. Useful for latent alignment (e.g., 8 or 64)."),
                        ]),
                    ],
                ),
                io.Combo.Input(
                    "scale_method",
                    options=cls.scale_methods,
                    default="area",
                    tooltip="Interpolation algorithm. 'area' is best for downscaling, 'lanczos' for upscaling, 'nearest-exact' for pixel art.",
                ),
                io.Combo.Input(
                    "adhere_to_multiple",
                    options=cls.output_multiples,
                    default="disabled",
                    tooltip="After resizing, center-crop to dimensions divisible by 8, 16, 32, or 64. Disabled preserves the exact requested size.",
                ),
            ],
            outputs=[
                io.MatchType.Output(template=template, display_name="resized"),
                io.Int.Output(display_name="width"),
                io.Int.Output(display_name="height"),
            ],
        )

    @classmethod
    def execute(
        cls,
        input: io.Image.Type | io.Mask.Type,
        scale_method: io.Combo.Type,
        adhere_to_multiple: io.Combo.Type,
        resize_type: ResizeTypedDict,
    ) -> io.NodeOutput:
        selected_type = resize_type["resize_type"]
        if selected_type == ResizeType.SCALE_BY:
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

        width, height = cls.get_dimensions(result)
        return io.NodeOutput(result, width, height)

    @classmethod
    def get_dimensions(cls, output: torch.Tensor) -> tuple[int, int]:
        # images are [batch, height, width, channels], masks are [batch, height, width]
        if is_image(output):
            height, width = output.shape[1], output.shape[2]
        else:
            height, width = output.shape[-2], output.shape[-1]
        return int(width), int(height)


class UniRatioNode(io.ComfyNode):
    default_selection = "sdxl:1-1"

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="UniRatioNode",
            display_name="UniRatio (Width/Height)",
            description="Compact, model-aware aspect ratio and resolution controller.",
            category="image/transform",
            search_aliases=[
                "uniratio", "ratio", "resolution", "width height", "aspect ratio",
                "dimensions", "sdxl resolution", "flux resolution", "video resolution",
                "wan resolution",
            ],
            inputs=[
                io.Combo.Input(
                    "selection",
                    options=selection_ids(),
                    default=cls.default_selection,
                    tooltip="Choose a model profile and aspect ratio. The compact browser is supplied by UniResize's frontend extension.",
                ),
                io.Float.Input(
                    "upscale",
                    default=1.0,
                    min=0.01,
                    max=8.0,
                    step=0.01,
                    tooltip="Multiply the selected or manual resolution. Model presets remain aligned to their required spatial multiple.",
                ),
                io.Int.Input(
                    "manual_width",
                    default=1024,
                    min=1,
                    max=MAX_RESOLUTION,
                    step=1,
                    advanced=True,
                    tooltip="Manual base width. Normally edited through the compact resolution browser.",
                ),
                io.Int.Input(
                    "manual_height",
                    default=1024,
                    min=1,
                    max=MAX_RESOLUTION,
                    step=1,
                    advanced=True,
                    tooltip="Manual base height. Normally edited through the compact resolution browser.",
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
        selection: io.Combo.Type,
        upscale: io.Float.Type,
        manual_width: io.Int.Type,
        manual_height: io.Int.Type,
    ) -> io.NodeOutput:
        width, height = resolve_dimensions(selection, upscale, manual_width, manual_height)
        return io.NodeOutput(width, height)
