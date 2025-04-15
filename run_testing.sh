#!/bin/bash

CESIUM_DIR="./test/run-cesium"
config="${CESIUM_DIR}/testing_config.js"
if [[ !  -e "$config" ]]
then 
    cp "${CESIUM_DIR}/testing_config_tmpl.js" "${CESIUM_DIR}/testing_config.js"
fi

rm "$CESIUM_DIR/cesium.js" 
touch "$CESIUM_DIR/cesium.js"
cat > "$CESIUM_DIR/cesium.js" <<EOF 
token = my_config.MY_TOKEN
data_dir = my_config.data_dir

Cesium.Ion.defaultAccessToken = token 

const viewer = new Cesium.Viewer('cesiumContainer');

const imageryLayers = viewer.imageryLayers;

const myNewProvider = new Cesium.WebMapTileServiceImageryProvider({

  "url": data_dir + "/iwp_coverage/WGS1984Quad/{TileMatrix}/{TileCol}/{TileRow}.png",
  "tilingScheme": new Cesium.GeographicTilingScheme()
})
const myNewLayer = new Cesium.ImageryLayer(myNewProvider)
imageryLayers.add(myNewLayer)
EOF

rm "$CESIUM_DIR/index.html"
touch "$CESIUM_DIR/index.html"
cat  > "$CESIUM_DIR/index.html" <<EOF
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <!-- Include the CesiumJS JavaScript and CSS files -->
  <script src="https://cesium.com/downloads/cesiumjs/releases/1.77/Build/Cesium/Cesium.js"></script>
  <link href="https://cesium.com/downloads/cesiumjs/releases/1.77/Build/Cesium/Widgets/widgets.css" rel="stylesheet">
</head>
<body>
  <div id="cesiumContainer"></div>
  <script src="testing_config.js" type="text/javascript"></script>
  <script src="cesium.js" type="text/javascript"></script>

</body>
</html>
EOF

cd $CESIUM_DIR

if [[ -e "yarn.lock" ]]
then
    yarn start
else 
    node server.js
fi




