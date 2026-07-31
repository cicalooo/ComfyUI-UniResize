from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from nodes import MAX_RESOLUTION


CATALOG_PATH = Path(__file__).with_name("web") / "resolution_catalog.json"


def load_catalog() -> dict[str, Any]:
    with CATALOG_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


CATALOG = load_catalog()
PROFILES = {profile["id"]: profile for profile in CATALOG["profiles"]}
RATIOS = {ratio["id"]: ratio for ratio in CATALOG["ratios"]}


def selection_ids() -> list[str]:
    return ["manual"] + [
        f'{profile["id"]}:{ratio_id}'
        for profile in CATALOG["profiles"]
        for ratio_id in profile["ratios"]
    ]


def _snap(value: float, multiple: int) -> int:
    return max(multiple, int(round(value / multiple)) * multiple)


def _translated_dimensions(profile: dict[str, Any], ratio_id: str) -> tuple[int, int]:
    ratio = RATIOS[ratio_id]["width"] / RATIOS[ratio_id]["height"]
    area = int(profile["target_area"])
    multiple = int(profile["multiple"])
    ideal_width = math.sqrt(area * ratio)
    ideal_height = math.sqrt(area / ratio)

    # Search around the independently rounded pair. This keeps both pixel-area
    # and aspect-ratio error low instead of allowing one rounding direction to
    # dominate narrow or cinematic formats.
    base_width = _snap(ideal_width, multiple)
    base_height = _snap(ideal_height, multiple)
    candidates: list[tuple[float, int, int]] = []
    for width_step in range(-2, 3):
        for height_step in range(-2, 3):
            width = base_width + width_step * multiple
            height = base_height + height_step * multiple
            if width < multiple or height < multiple:
                continue
            area_error = abs((width * height) - area) / area
            ratio_error = abs((width / height) - ratio) / ratio
            candidates.append((area_error + ratio_error, width, height))
    _, width, height = min(candidates)
    return width, height


def resolve_selection(selection: str) -> tuple[int, int]:
    try:
        profile_id, ratio_id = selection.split(":", 1)
        profile = PROFILES[profile_id]
    except (ValueError, KeyError) as error:
        raise ValueError(f"Unknown UniRatio selection: {selection!r}") from error

    if ratio_id not in profile["ratios"] or ratio_id not in RATIOS:
        raise ValueError(f"Ratio {ratio_id!r} is not available for {profile['name']}")

    exact = profile.get("exact", {}).get(ratio_id)
    if exact:
        width, height = map(int, exact)
    else:
        width, height = _translated_dimensions(profile, ratio_id)

    multiple = int(profile["multiple"])
    if width % multiple or height % multiple:
        raise ValueError(f"Resolved dimensions must be divisible by {multiple}")
    if width > MAX_RESOLUTION or height > MAX_RESOLUTION:
        raise ValueError(f"Resolved dimensions exceed ComfyUI MAX_RESOLUTION ({MAX_RESOLUTION})")
    return width, height


def resolve_dimensions(
    selection: str,
    upscale: float = 1.0,
    manual_width: int = 1024,
    manual_height: int = 1024,
) -> tuple[int, int]:
    if not 0.01 <= upscale <= 8.0:
        raise ValueError("Upscale must be between 0.01 and 8.0")

    if selection == "manual":
        base_width, base_height = int(manual_width), int(manual_height)
        multiple = 1
    else:
        base_width, base_height = resolve_selection(selection)
        profile_id, _ = selection.split(":", 1)
        multiple = int(PROFILES[profile_id]["multiple"])

    width = _snap(base_width * upscale, multiple)
    height = _snap(base_height * upscale, multiple)
    if width > MAX_RESOLUTION or height > MAX_RESOLUTION:
        raise ValueError(f"Scaled dimensions exceed ComfyUI MAX_RESOLUTION ({MAX_RESOLUTION})")
    return width, height


def selection_summary(selection: str) -> str:
    profile_id, ratio_id = selection.split(":", 1)
    width, height = resolve_selection(selection)
    return f"{PROFILES[profile_id]['name']} · {RATIOS[ratio_id]['label']} · {width}×{height}"
