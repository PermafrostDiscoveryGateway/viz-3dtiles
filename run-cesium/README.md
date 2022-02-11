This directory contains basic JS and HTML files for running Cesium in your browser in order to run the 3D Tilesets generated from `viz-3dtiles/build-3d-tile.py`.

You will need to update `cesium.js` with your Cesium Ion access token, retrieved from your Cesium account at https://cesium.com/ion/tokens

```js
Cesium.Ion.defaultAccessToken = "'eyJhbGciOiJ..."
```

Run the Cesium.js file by starting the local node server:

```shell
node server.js
```

and then visit `localhost:3003` to view Cesium.