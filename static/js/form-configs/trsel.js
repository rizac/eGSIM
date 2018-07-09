class TRSelMap {
    /**
     * Class managing the trs (tectonic region selection) leaflet map.
     * Just call map.init(), map.projectName(name)
     */
    constructor(mapId, projects, selProject) {
        // projects: object of names (string) mapped to the geojson featurecollection object:
        // { "type": 'FeatureCollection',
        //   "features": [
        //        {
        //          "type": "Feature",
        //          "geometry": {
        //            "type": "Point",
        //            "coordinates": [125.6, 10.1]
        //          },
        //          "properties": {
        //            "OQ_TRT": "Active shallow crust"  // THIS PROPERTY IS MANDATORY!
        //          }
        //        }, ...
        //       ]
        // }
        this._overlays = [];
        this._layersControl = undefined;
        this._projects = projects

        this._map = L.map(mapId, {center: [48, 7], zoom: 4});
        // https://esri.github.io/esri-leaflet/examples/switching-basemaps.html:
        var layerName = 'ShadedRelief';
        var layer = L.esri.basemapLayer(layerName).addTo(this._map);
        var layerLabels = L.esri.basemapLayer(layerName + 'Labels');
        this._map.addLayer(layerLabels);
        // instanitate a layer control (the button on the top-right corner for showing/hiding overlays
        // overlays will be added when setting the project
        this._layersControl = L.control.layers({}, {}).addTo(this._map);

        this.project = selProject || Object.keys(projects)[0]; // default project name on startup:        
    }

    get projects(){
        /**
         * returns the available project names, as array
         */
        return Array.from(this._projects.keys()); // as array so that angularjs does not complain
    }

    get project(){
        return this._selProject;
    }

    set project(key) {
        /**
         * Sets the overlays mapped to the given key which is a string denoting a project name
         * key must be stored in this class projects (with relative associated shape files. See class constructor)
         */

        if (this._selProject === key){
            return;
        }
        this._selProject = key;

        var map = this._map;
        var layersControl = this._layersControl;
        var overlays = this._overlays || [];

        overlays.forEach(layer => {
            map.removeLayer(layer);
            layersControl.removeLayer(layer);
        });
        // restore:
        this._overlays = overlays = [];

        var geojson = this._projects[key] || {};
        var features = ((geojson.features || geojson) || []);
        // group features by their feature.property.OQ_TRT (openquake tectonic region type),
        // the Object featureCollections maps a OQ_TRT to a geojson featureCollection: 
        var featureCollections = {};
        features.forEach(feature => {
            var t = feature.properties.OQ_TRT;
            // create feature collection if not already set:
            if (!featureCollections[t]){
                featureCollections[t] = {type: "FeatureCollection", features: []};
            }
            // add out feature:
            featureCollections[t].features.push(feature);
        });

        // update the map:
        Object.keys(featureCollections).forEach(key => {
            // create layer(s) from the geojson FeatureCollections we created.
            // Add a class for css styling. The class is the tectonic region type name
            // (one of the values of the Object `trt`, defined in the class constructor) where spaces are replaced with "_"
            // and the whole string is converted to lower case.
            // For adding future features, the line below is what we need. For info see:
            // http://leafletjs.com/examples/geojson/ and
            // https://stackoverflow.com/questions/17086195/leaflet-path-how-can-i-set-a-css-class (2nd post)
            var layer = L.geoJson(featureCollections[key], {'className': key.replace(/\s/g, "_").toLowerCase()}).addTo(map); //, style: style, onEachFeature: eachFeature })
            layersControl.addOverlay(layer, key);
            overlays.push(layer);
        });
    }
}