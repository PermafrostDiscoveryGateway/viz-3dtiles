from __future__ import annotations

from py3dtiles.tileset.content.b3dm import B3dm as UpstreamB3dm
from py3dtiles.tileset.content.b3dm import B3dmHeader


def _sync_legacy_header(tile: UpstreamB3dm) -> None:
    """
    Recompute B3DM header lengths using split JSON/BIN lengths
    for feature table and batch table.
    """
    gltf_arr = tile.body.gltf.to_array()

    tile.header.tile_byte_length = B3dmHeader.BYTE_LENGTH + len(gltf_arr)
    tile.header.ft_json_byte_length = 0
    tile.header.ft_bin_byte_length = 0
    tile.header.bt_json_byte_length = 0
    tile.header.bt_bin_byte_length = 0

    if tile.body.feature_table is not None:
        ft_json = tile.body.feature_table.header.to_array()
        ft_bin = tile.body.feature_table.body.to_array()

        tile.header.tile_byte_length += len(ft_json) + len(ft_bin)
        tile.header.ft_json_byte_length = len(ft_json)
        tile.header.ft_bin_byte_length = len(ft_bin)

    if tile.body.batch_table is not None:
        bt_json = tile.body.batch_table.header.to_array()
        bt_bin = tile.body.batch_table.body.to_array()

        tile.header.tile_byte_length += len(bt_json) + len(bt_bin)
        tile.header.bt_json_byte_length = len(bt_json)
        tile.header.bt_bin_byte_length = len(bt_bin)


class B3dm(UpstreamB3dm):
    """
    Compatibility wrapper restoring old viz-3dtiles expectations around
    B3DM header length calculation.
    """

    @classmethod
    def from_glTF(cls, gltf, ft=None, bt=None) -> "B3dm":
        tile = super().from_glTF(gltf, ft=ft, bt=bt)
        _sync_legacy_header(tile)
        return tile