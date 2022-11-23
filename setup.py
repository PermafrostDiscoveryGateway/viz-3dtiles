from setuptools import setup

setup(name='viz_3dtiles',
      version='0.0.1',
      description='A module that converts vector geometry files to Cesium 3D Tilesets',
      url='https://github.com/PermafrostDiscoveryGateway/viz-3dtiles',
      author='Lauren Walker',
      author_email='walker@nceas.ucsb.edu',
      license='Apache License Version 2.0',
      packages=['viz_3dtiles'],
      python_requires='>=3.5',
      install_requires=[
        'numpy >= 1.20, < 2.0',
        'pandas >= 1.4, < 2.0',
        'shapely >= 2.0b2',
        'geopandas >= 0.12, < 1.0',
        'pdgpy3dtiles @ git+https://github.com/PermafrostDiscoveryGateway/py3dtiles.git#egg=pdgpy3dtiles',
        'open3d >= 0.15, < 1.0'
      ],
      zip_safe=False)
