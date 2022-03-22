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
1. Change the input file path (`file`) in `3dtiles/build.py` to the file path of your .shp file (or any other vector geometry file that can be read by `geopandas`)
2. Run `build.py`:
```
python3 build.py
```
3. The output will be saved as `tileset.json` and `model.b3dm` in `test/run-cesium/tilesets/build-output`