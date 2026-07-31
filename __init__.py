from typing_extensions import override

from comfy_api.latest import ComfyExtension, io

from .nodes import UniResizeNode, UniRatioNode


WEB_DIRECTORY = "./web"


class UniResizeExtension(ComfyExtension):
    @override
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [UniResizeNode, UniRatioNode]


async def comfy_entrypoint() -> UniResizeExtension:
    return UniResizeExtension()
