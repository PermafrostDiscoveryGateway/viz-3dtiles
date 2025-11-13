function start(){// Your access token can be found at: https://cesium.com/ion/tokens.

Cesium.Ion.defaultAccessToken = "YOUR-TOKEN-HERE";

// Initialize the Cesium Viewer in the HTML element with the `cesiumContainer` ID.
var Cartesian3 = Cesium.Cartesian3;
var cesiumTerrainProvider = Cesium.createWorldTerrain();
var ellipsoidTerrainProvider = new Cesium.EllipsoidTerrainProvider();

const viewer = new Cesium.Viewer('cesiumContainer', {});
const scene = viewer.scene;

var layers = scene.imageryLayers;

scene.imageryLayers._layers[0].alpha=1
scene.backgroundColor.alpha = 0
scene.globe.depthTestAgainstTerrain = true;

// The tileset created by the build-3d-tile.py script
var tileset = new Cesium.Cesium3DTileset({
  url: "tilesets/test/tileset.json",
  debugShowBoundingVolume: false,
  debugShowContentBoundingVolume: false,
  debugShowGeometricError: false,
  debugWireframe: false
});

tileset.style = new Cesium.Cesium3DTileStyle({
  color: {
    conditions: [
      ["true", "color('blue')"],
    ],
  },
  show: true,
});

// The tileset created by FME
var tilesetFME = new Cesium.Cesium3DTileset({
  url: "tilesets/from-FME/tileset.json",
  debugShowBoundingVolume: false,
  debugShowContentBoundingVolume: false,
  debugShowGeometricError: true,
  debugWireframe: false
});

tilesetFME.style = new Cesium.Cesium3DTileStyle({
  color: {
    conditions: [
      ["true", "color('red')"],
    ],
  },
  show: true,
});

//viewer.scene.primitives.add(tilesetFME);
viewer.scene.primitives.add(tileset);


window.zoom_to_me = function(){
  viewer.zoomTo(tileset);
}

tileset.readyPromise.then(zoom_to_me).otherwise(error => { console.log(error) });

}

start()
