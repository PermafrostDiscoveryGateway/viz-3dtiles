from __future__ import annotations

from pathlib import Path

from py3dtiles.tileset.content.tile_content import TileContent as UpstreamTileContent


class TileContent(UpstreamTileContent):
    def save_as(self, path):
        if isinstance(path, str):
            path = Path(path)

        path.parent.mkdir(parents=True, exist_ok=True)
        super().save_as(path)