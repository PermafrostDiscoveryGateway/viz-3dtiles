function start() {
  // Your access token can be found at: https://cesium.com/ion/tokens.
  Cesium.Ion.defaultAccessToken = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiJiZTMwNDg5Mi1mNzViLTQ2MTAtYTk4ZS1kMjYzZDMxMDExYmEiLCJpZCI6Mjg0MTAxLCJpYXQiOjE3NDE5MDE4ODF9.O9NRGNIsdWNykfRwJp_kaesei9wlcKni5cLynQCAV_g";

  // Initialize the Cesium Viewer in the HTML element with the `cesiumContainer` ID.
  var Cartesian3 = Cesium.Cartesian3;
  var cesiumTerrainProvider = Cesium.createWorldTerrain();
  var ellipsoidTerrainProvider = new Cesium.EllipsoidTerrainProvider();

  var viewer = new Cesium.Viewer('cesiumContainer', {
    terrainProvider: null
  });

  const scene = viewer.scene;

  var layers = scene.imageryLayers;

  scene.imageryLayers._layers[0].alpha = 1;
  scene.backgroundColor.alpha = 0;
  scene.globe.depthTestAgainstTerrain = true;

  // The tileset created by the build-3d-tile.py script
  var tileset = new Cesium.Cesium3DTileset({
    url: "https://demo.arcticdata.io/tiles/3dtt/ml/roads_tileset.json",
  });

  tileset.style = new Cesium.Cesium3DTileStyle({
    color: {
      conditions: [
        ["true", "color('red')"],
      ],
    },
    show: true,
  });

  // The tileset created by FME
  var tilesetFME = new Cesium.Cesium3DTileset({
    url: "https://demo.arcticdata.io/tiles/3dtt/ml/buildings_tileset.json",
  });

  tilesetFME.style = new Cesium.Cesium3DTileStyle({
    color: {
      conditions: [
        ["true", "color('blue')"],
      ],
    },
    show: true,
  });


  // The tileset created by FME
  var tilesetbuilding2 = new Cesium.Cesium3DTileset({
    url: "https://demo.arcticdata.io/tiles/3dtt/mltest/buildings_z0_tileset.json",
  });

  tilesetFME.style = new Cesium.Cesium3DTileStyle({
    color: {
      conditions: [
        ["true", "color('green')"],
      ],
    },
    show: true,
  });

  // var offsetTransform = Cesium.Matrix4.fromTranslation(
  //   new Cesium.Cartesian3(0, 0, -7)
  // );
  // tilesetFME.modelMatrix = offsetTransform;

  // tilesetFME.modelMatrix = offsetTransform1;
  // Uncomment one of these lines to add the desired tileset to the scene.
  //viewer.scene.primitives.add(tilesetFME);
  viewer.scene.primitives.add(tileset);
  viewer.scene.primitives.add(tilesetFME);
  viewer.scene.primitives.add(tilesetbuilding2);

  window.zoom_to_me = function () {
    viewer.zoomTo(tileset);
  }

  tileset.readyPromise.then(zoom_to_me).otherwise(error => { console.log(error) });
}

start();
