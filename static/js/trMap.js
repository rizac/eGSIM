class MapManager {
    /**
     * Class managing the trs (tectonic region selection) leaflet map.
     * Just call map.init(), map.projectName(name)
     */
    constructor(mapId) {
        this._mapId = mapId;
        this._map = undefined;
        this._overlays = [];
        this._layersControl = undefined;
        // defined an object of project(s) mapped to the relative zip files (add new here, if any in the future):
        // maybe not elegant, in any case defining everything here makes life easier when debugging and maintaining
        var p = '/static/data/asmodal/';
        this._projects = new SelMap([
            ['SHARE', {
                'Area Source Model': p+'ASModelVer6.1.zip',
                'Subduction': p+'Subduction.zip',
                'Vrancea': p+'VRANCEAv6.1.zip'
                }
            ]
            ]);
        this._projects.selection = 'SHARE'; // default project name on startup:
        // this is used to check which geoJson features belong to which tectonic region (see this._setOverlay)
        // map any lower case name to a valid openquacke name defined in the object below's values
        // For info: https://docs.openquake.org/oq-hazardlib/0.12/_modules/openquake/hazardlib/const.html#TRT
        this.str2trt = {
                'active shallow crust': 'Active Shallow Crust',
                'stable shallow crust': 'Stable Shallow Crust',
                'subduction interface': 'Subduction Interface',
                'subduction intraslab': 'Subduction IntraSlab',
                "upper mantle": "Upper Mantle",
                'volcanic': 'Volcanic',
                'geothermal': 'Geothermal',
                'induced': 'Induced',
                "subduction inslab": "Subduction IntraSlab",  // FIXME: is this true?
                "stable continental crust": 'Stable Shallow Crust',  // FIXME: is this true?
                "Inslab": "Subduction IntraSlab"
        };
        // the tectonic region types, as str2trt values (use a Set to avoid duplicates):
        this.trt = new Set(Object.values(this.str2trt));
    }

    get projectNames(){
        /**
         * returns the available project names, as array
         */
        return Array.from(Object.keys(this._projects)); // as array so that angularjs does not complain
    }

    get ready(){
        /**
         * returns true if the leaflet map is ready and visible on the page
         */
        return this._map !== undefined ? true : false;
    }

    init() {
        /**
         * initializes the leaflet container and returns this object. If already initialized,
         * does nothing
         */
        if (this.ready){
            return;
        }
        this._map = L.map(this._mapId, {center: [48, 7], zoom: 4});
        // https://esri.github.io/esri-leaflet/examples/switching-basemaps.html:
        var layerName = 'ShadedRelief';
        var layer = L.esri.basemapLayer(layerName).addTo(this._map);
        var layerLabels = L.esri.basemapLayer(layerName + 'Labels');
        this._map.addLayer(layerLabels);
        // instanitate a layer control (the button on the top-right corner for showing/hiding overlays
        // overlays will be added below in this.projectName(this._projects.selKey);
        this._layersControl = L.control.layers({}, {}).addTo(this._map);
        // set the project name and its layers loaded from files:
        this.projectName(this._projects.selection);
        return this;
    }

    projectName(newName){
        /**
         * Without arguments, returns the currently selected project name. With an argument (string)
         * sets the relative project name, if stored in this class projects (with relative associated shape files)
         */
        //make angularjs happy with getter-setter (https://docs.angularjs.org/api/ng/directive/ngModel)
        // Note that newName can be undefined for two reasons:
        // 1. Because it is called as a getter and thus called with no arguments
        // 2. Because the property should actually be set to undefined. This happens e.g. if the
        //    input is invalid
        if (arguments.length){
            this._projects.selection = newName;
            this._setOverlay(newName);
        }else{
            return this._projects.selection;
        }
    }

    _setOverlay(key){
        /**
         * Sets the overlays mapped to the given key which is a string denoting a project name
         * key must be stored in this class projects (with relative associated shape files. See class constructor)
         */
        // first remove old overlays:
        if(this._overlays){
            this._overlays.forEach(function(layer){
                this._map.removeLayer(layer);
                this._layersControl.removeLayer(layer);
            });
        }
        // restore internal method:
        this._overlays = [];

        var newOverlays = this._projects.get(key);
        if (!newOverlays){
            return;
        }

        // newOverlays is an object of keys (names) mapped to a shape file.
        // names are actually not used anymore and we will use the object values (shape file),
        // but we leave this functionality

        var layersControl = this._layersControl;
        var overlays = this._overlays;
        var map = this._map;
        
        var keys = Object.keys(newOverlays);
        let i = 0;
        let total = keys.length;
        // make visible inside forEach below:
        // 1. our dict of tectonic region types strings -> tectonic region type name
        var str2trt = this.str2trt;
        // 2. our set of distinct tectonic region type names (from hazardlib)
        var trt = this.trt;
        // 3. our dict of tectonic region type names mapped to a geoJson FeatureCollection (which will create a leaflet layer on the map)
        var featureCollections = {};

        keys.forEach(function(key){
            var shpFile = newOverlays[key];
            shp(shpFile).then(function(geojson){
                // geojson is already a FeatureCollection object. We might then simply use:
                // L.geoJson(geojson, ...) but we want to split feature collections (and relative leaflet Layers)
                // according to their tectonic region type. Thus, for each feature of geojson,
                // we inspect two properties: feature.properties.TECTONICS and feature.properties.TECREG.
                // The tectonic region type name T of the given feature is the value of `str2trt` mapped
                // to any of those properties: if T is found, the feature will be added
                // to the FeatureCollection object which is mapped to T: `featureCollections[T]`
                geojson.features.forEach(function(feature){
                    var t = str2trt[(feature.properties.TECTONICS+"").toLowerCase()] || 
                        str2trt[(feature.properties.TECREG+"").toLowerCase()];
                    if(t){
                        // create feature collection if not already set:
                        if (!featureCollections[t]){
                            featureCollections[t] = {type: "FeatureCollection", features: []};
                        }
                        // add out feature:
                        featureCollections[t].features.push(feature);
                    }else{
                        // log when feature not found:
                        console.log("TRT not found in '" + shpFile + "': " + feature.properties.TECREG + " " + feature.properties.TECTONICS);
                    }
                });
                i+=1; // i with the let keyword is kinda global (need to read more about this)
                if(i == total){ // last loop, let's populate the leaflet map:
                    Object.keys(featureCollections).forEach(function(key){
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
            });
        });
    }
}