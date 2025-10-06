from setuptools import setup

setup(
    name="viz_3dtiles",
    version="1.0.0",
    description="A module that converts vector geometry files to Cesium 3D Tilesets",
    url="https://github.com/PermafrostDiscoveryGateway/viz-3dtiles",
    author=(
        "Robyn Thiessen-Bock; Juliet Cohen; Matthew B. Jones; "
        "Kastan Day; Lauren Walker; Rushiraj Nenuji; Alyona Kosobokova"
    ),
    license="Apache License Version 2.0",
    packages=["viz_3dtiles"],
    python_requires=">=3.5",
    install_requires=[
        "numpy >= 1.20, < 2.0",
        "pandas >= 1.4, < 2.0",
        "shapely >= 2, < 3.0",
        "geopandas >= 0.12.2, < 1.0",
        "pdgpy3dtiles @ git+https://github.com/PermafrostDiscoveryGateway/py3dtiles.git#egg=pdgpy3dtiles",
        "open3d >= 0.15, < 1.0",
    ],
    zip_safe=False,
)
