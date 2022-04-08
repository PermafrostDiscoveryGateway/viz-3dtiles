# viz-3dtiles

A Python library for creating Cesium 3D Tilesets. This library uses a forked version of the py3dtiles Python library to convert `.shp` files to `.b3dm` files and creates a `tileset.json` to load into Cesium.

## Install
1. Create a Python 3 virtual environment:
```
python3 -m venv .3dtilesenv
source .3dtilesenv/bin/activate
```

2. Install the requirements using `pip`:
```
pip install -r requirements.txt
```

## Usage
1. Create an instance of the `Cesium3DTile` class. Use `Cesium3DTile.from_file()` to process a `.shp` file into a `.b3dm` 3D model:

```python
tile = Cesium3DTile()
tile.save_to="~/my-tilesets/lakes/"
tile.from_file(filepath="~/my-data/lakes.shp")
```

2. Create an instance of the `Cesium3DTileset` class to contain that tile:

```python
tileset = Cesium3DTileset(tiles=[tile])
tileset.save_to="~/my-tilesets/lakes/"
tileset.write_file()
```

See [/test/test.py](test/test.py) which creates an example tileset.