This directory contains basic JS and HTML files for running Cesium in your browser in order to preview the 3D Tilesets generated from this Python package (`3dtiles`). You can preview the generated tilesets in any Cesium setup of your choosing - this is only included here as a convenience for quickly previewing the test output.

## Usage
1. You will need to update `cesium.js` with your Cesium Ion access token, retrieved from your Cesium account at https://cesium.com/ion/tokens. This will render a satelite imagery layer from Cesium Ion.

```js
Cesium.Ion.defaultAccessToken = "'eyJhbGciOiJ..."
```

2. Run the Cesium.js file by starting the local node server:

```shell
node server.js
```

3. and then visit `localhost:3003` in your web browser to view Cesium.