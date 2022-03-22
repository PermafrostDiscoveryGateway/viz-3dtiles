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
  url: "tilesets/build-output/tileset.json",
  debugShowBoundingVolume: true,
  debugShowContentBoundingVolume: true,
  debugShowGeometricError: true,
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

// Below code is experiemental and not executed currently
var center = new Cesium.Cartesian3.fromDegrees(-762889.979147543, -1335791.868934655, 6169085.401505229);
var posMat = Cesium.Transforms.eastNorthUpToFixedFrame(center);

function updateTile (tile) {
    var boundingVolume = tile.boundingVolume;
    if (Cesium.defined(tile.contentBoundingVolume)) {
        boundingVolume = tile.contentBoundingVolume;
    }
    var content = tile.content;
    var model = content._model;
    var height = boundingVolume.minimumHeight || 0;
    var center = model._rtcCenter || new Cesium.Cartesian3(-762889.9791526495,
                -1335791.8689435967,
                6169085.401505229);
    var normal = scene.globe.ellipsoid.geodeticSurfaceNormal(center, new Cartesian3());
    var offset = Cartesian3.multiplyByScalar(normal, height, new Cartesian3());
    var carto = Cesium.Cartographic.fromCartesian(center);
    var promise = Cesium.when.defer();
    if (scene.terrainProvider === ellipsoidTerrainProvider) {
        var result = carto;
        result.height = 0;
        promise.resolve(result);
    } else {
        promise = Cesium.sampleTerrainMostDetailed(scene.terrainProvider, [carto]).then(function(results) {
            var result = results[0];
            if (!Cesium.defined(result)) {
                return carto;
            }
            return result;
        });
    }

    promise.then(function(result) {
        result = Cesium.Cartographic.toCartesian(result);
        var position = Cartesian3.subtract(result, offset, new Cartesian3());
        model._rtcCenter = Cartesian3.clone(position, model._rtcCenter);
    });
}

function updateTileset(root) {
    if (root.contentReady) {
        updateTile(root);
    } else {
        var listener = tileset.tileLoad.addEventListener(function(tile) {
            if (tile === root) {
                updateTile(tile);
                listener();
            }
        });
    }

    var children = root.children;
    var length = children.length;
    for (var i = 0; i < length; ++i) {
        updateTileset(children[i]);
    }
}

}

start()
