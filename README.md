# viz-3dtiles

A Python package for creating Cesium 3D Tilesets. This package uses a forked version of the py3dtiles Python library to convert a `.shp` file to a `.b3dm` file and creates a `tileset.json` to load into Cesium.

This package was developed for the [Permafrost Discovery Gateway](https://permafrost.arcticdata.io), an NSF-funded research project whose mission is to create an online platform for analysis and visualization of permafrost big imagery products to enable discovery and knowledge-generation.

## Install via Conda or pip

### Conda

```bash
conda env create
conda activate viz_3d
```

### Pip install

1. Create a Python 3 virtual environment:

```bash
python3 -m venv .3dtilesenv
source .3dtilesenv/bin/activate
```

2. Install the requirements using `pip`:

```bash
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

## Demo

See [/test/test.py](test/test.py) which creates an example tileset.

Usage: from the base directory (`./viz-3dtiles`) run `python test/test.py`
