class MapManager {

	constructor(mapId) {
		this._mapId = mapId;
		this._map = undefined;
		this._overlays = [];
		this._layersControl = undefined;
		var p = '/static/data/asmodal/'
		this._projects = {
				'SHARE': {
					'Area Source Model': p+'ASModelVer6.1.zip',
					'Subduction': p+'Subduction.zip',
					'Vrancea': p+'VRANCEAv6.1.zip'
				}
		};
		this._projectName = 'SHARE';
		this.str2trt = {'active shallow crust': 'Active Shallow Crust',
				    'stable shallow crust': 'Stable Shallow Crust',
				    'subduction interface': 'Subduction Interface',
				    'subduction intraslab': 'Subduction IntraSlab',
				    "upper mantle": "Upper Mantle",
				    'volcanic': 'Volcanic',
				    'geothermal': 'Geothermal',
				    'induced': 'Induced',
				    	"subduction inslab": "Subduction IntraSlab",
				    	"stable continental crust": 'Stable Shallow Crust'
					};
		this.trt = new Set(Object.values(this.str2trt));
	}
	
	get projectNames(){
		return Array.from(Object.keys(this._projects));
	}

	projectName(newName){ //make angularjs happy with getter-setter (https://docs.angularjs.org/api/ng/directive/ngModel)
		// Note that newName can be undefined for two reasons:
	     // 1. Because it is called as a getter and thus called with no arguments
	     // 2. Because the property should actually be set to undefined. This happens e.g. if the
	     //    input is invalid
		if (arguments.length){
			this._projectName = newName;
			this.setOverlay(newName);
		}else{
			return this._projectName;
		}
	}
	get ready(){
		return this._map !== undefined ? true : false;
	}
	init() {
		if (this.ready){
			return;
		}
		this._map = L.map(this._mapId, {center: [48, 7], zoom: 4});
		// https://esri.github.io/esri-leaflet/examples/switching-basemaps.html:
		var layerName = 'ShadedRelief';
		var layer = L.esri.basemapLayer(layerName).addTo(this._map);
		var layerLabels = L.esri.basemapLayer(layerName + 'Labels');
		this._map.addLayer(layerLabels);
		var baseLayers = {};
		baseLayers[layerName] = layer;
		this._layersControl = L.control.layers({}, {}).addTo(this._map);
		this.projectName(this._projectName);
		return this;
	}
	
	setOverlay(key){
		if(this._overlays){
			this._overlays.forEach(function(layer){
				this._map.removeLayer(layer);
				this._layersControl.removeLayer(layer);
	    		});
		}

		this._overlays = [];
		
		var newOverlays = this._projects[key];
		if (!newOverlays){
			return;
		}

		var layersControl = this._layersControl;
		var overlays = this._overlays;
		var map = this._map;
		
		var keys = Object.keys(newOverlays);
		let i =0;
		let total = keys.length;
		var str2trt = this.str2trt;
		var trt = this.trt;
		var featureCollections = {};

		keys.forEach(function(key){
	    		var shpFile = newOverlays[key];
	    		shp(shpFile).then(function(geojson){
	    			geojson.features.forEach(function(feature){
	    				var t = str2trt[(feature.properties.TECTONICS+"").toLowerCase()] || 
	    						str2trt[(feature.properties.TECREG+"").toLowerCase()];
	    				if(t){
	    					if (!featureCollections[t]){
	    						featureCollections[t] = {type: "FeatureCollection", features: []};
	    					}
	    					featureCollections[t].features.push(feature);
	    				}else{
	    					console.log("TRT not found in '" + shpFile + "': " + feature.properties.TECREG + " " + feature.properties.TECTONICS);
	    				}
	    			});
	    			i+=1;
	    			if(i == total){
	    				// add to the map
	    				Object.keys(featureCollections).forEach(function(key){
	    					var layer = L.geoJson(featureCollections[key], {'className': key.replace(/\s/g, "_").toLowerCase()}).addTo(map); //, style: style, onEachFeature: eachFeature })
	    					layersControl.addOverlay(layer, key);
	    					overlays.push(layer);
	    				});
	    			}
	    			
//	    			var layer = L.shapefile(geojson).addTo(map); //More info: https://github.com/calvinmetcalf/leaflet.shapefile
//	    			geojson.features.forEach(function(feature){
//	    				console.log(feature.properties.TECREG+" "+feature.properties.TECTONICS);
//	    			});
//	    			layersControl.addOverlay(layer, key);
//	    			overlays.push(layer);
	    		});
	    	});
	}
}