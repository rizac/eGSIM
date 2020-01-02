Vue.component('trmap', {
    props: {'initurl': {type:String}, 'url': {type:String}, 'eventbus':{default:null}, 'avalgsims': Map, 'selectedgsims': Array},
    data: function(){
        return {
            'id': 'tr_map_id',
            'selectedModel': undefined, //name of selected tecttonic region model (e.g. SHARE)
            'models': {},  //object of model names name mapped to geojson data
            'map': undefined,
            'layersControl': undefined,
            'overlays': {},  // object of layer name (tectonic region) => leaflet layer
            'clicked': false,
            'colorMap': Vue.colorMap() // defined in vueutil.js
        }
    },
    template:`<div class='d-flex flex-column'>
        <select v-model='selectedModel' class='form-control mb-2'>
            <option v-for='mod in modelNames' :key='mod'>
                {{ mod }}
            </option>
        </select>
        <div :id='id' class='flexible'></div>
        </div>`,
    created: function(){
         if(this.eventbus){
             this.eventbus.$on('postresponse', (response, isError) => {
                 if ((response.config.url == this.initurl) && !isError){
                     this.$set(this, 'models', response.data.models);
                     this.$set(this, 'selectedModel', response.data.selected_model || Object.keys(response.data.models)[0]);
                 }
             });
             this.eventbus.$emit('postrequest', this.initurl);
         }
    },
    watch:{
        selectedModel: function(oldVal, newVal){
            if(newVal != oldVal){
                this.$nextTick(this.updateDOM);  // executed after every part of the DOM has rendered, inlcuding mounted() below
            }
        }
    },
    mounted: function(){
        // models: object of names (string) mapped to the geojson featurecollection object:
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
        var map = L.map(this.id, {center: [48, 7], zoom: 4});
        L.tileLayer('https://api.tiles.mapbox.com/v4/{id}/{z}/{x}/{y}.png?access_token=pk.eyJ1IjoibWFwYm94IiwiYSI6ImNpejY4NXVycTA2emYycXBndHRqcmZ3N3gifQ.rJcFIG214AriISLbB6B5aw', {
            maxZoom: 18,
            id: 'mapbox.streets'
          }).addTo(map);
        
        // https://esri.github.io/esri-leaflet/examples/switching-basemaps.html:
//        var layerName = 'ShadedRelief';
//        var layer = L.esri.basemapLayer(layerName).addTo(map);
//        var layerLabels = L.esri.basemapLayer(layerName + 'Labels');
//        map.addLayer(layerLabels);

        // instantiate a layer control (the button on the top-right corner for showing/hiding overlays
        // overlays will be added when setting the tr model
        this.$set(this, 'layersControl', L.control.layers({}, {}, {collapsed:false}).addTo(map));  // https://gis.stackexchange.com/a/68243
        // note above: collapsed:false makes the legend control visible. This does not work though in 100% of the cases,
        // so see in updateDom a hack for solving this problem (remove control height, if set)
        this.$set(this, 'map', map);
        map.on("click", this.clickHandler);
    },
    methods:{
        clickHandler: function(event) {
            if(!this.eventbus){
                return;
            }
            this.eventbus.$once('postresponse', (response, isError) => {
                if ((response.config.url == this.url) && !isError){
                    this.openPopup(event, response.data);
                }
            });
            var data = {'model': this.selectedModel, 'latitude': event.latlng.lat,
                        'longitude': event.latlng.lng};
            // get visible layers:
            var overlays = this.overlays;
            data['trt'] = Object.keys(overlays).filter(layerName => {
               return overlays[layerName]._map ? true : false;
            });
            this.eventbus.$emit('postrequest', this.url, data);
        },
        openPopup: function(event, responseData){
            // dynamically create vue 'gsimselect' component:
            // https://css-tricks.com/creating-vue-js-component-instances-programmatically/
            // (the only difference with the link above is the use of Vue.options['components']['gsimselect']
            // to retrieve globally defined components):
            var ComponentClass = Vue.extend(Vue.options['components']['gsimselect'])
            // build avalgsims as Map, because our <gsimselect> expects a Map.
            // we can populate the map values as nulls AS LONG AS WE DO NOT USE the <gsimselect> filter options
            // (and we don't)
            avalgsims = new Map();
            for(var gsim of responseData){
                avalgsims.set(gsim, null);
            }
            var instance = new ComponentClass({
                propsData: {avalgsims: avalgsims, selectedgsims: this.selectedgsims}
            })
            // forward the gsim selection fired by the <gsimselect> to the listeners of this component (if provided):
            instance.$on('update:selectedgsims', newValue => {
                this.$emit('update:selectedgsims', newValue);
            });
            // Set the value of the label, wich is implemented as a (single) slot in the gsimselect
            // (unfortunately, only plain text allowed for the moment):
            instance.$slots.default = ['Gsims defined for the selected Tectonic Region(s):'];
            // mount the instance:
            instance.$mount() // pass nothing
            // add custom classes (must be done after mount):
            instance.$el.style.maxWidth = '50vw';
            instance.$el.style.maxHeight = '50vh';
            instance.$el.style.height = `${avalgsims.size}em`;
            this.map.openPopup(instance.$el, event.latlng, {
                offset: L.point(0, -5)
            });
        },
        updateDOM: function() {
            /**
             * Sets the overlays mapped to the given key which is a string denoting a model name
             * key must be stored in this class models (with relative associated shape files. See class constructor)
             */
            var map = this.map;
            var layersControl = this.layersControl;
            var overlays = this.overlays;
    
            Object.keys(overlays).forEach(layerName => {
                var layer = overlays[layerName];
                map.removeLayer(layer);
                layersControl.removeLayer(layer);
            });
    
            overlays = this.overlays = {};
            var geojson = this.models[this.selectedModel] || {};
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
                // create layer(s) from the geojson FeatureCollections.
                // For info see:
                // http://leafletjs.com/examples/geojson/ and (add css class, not used but if needed):
                // https://stackoverflow.com/questions/17086195/leaflet-path-how-can-i-set-a-css-class (2nd post)
                var style = this.getStyle(key);
                var layer = L.geoJson(featureCollections[key],
                        {style: style, onEachFeature: this.onEachFeature}).addTo(map); //, style: style, onEachFeature: eachFeature })
                layersControl.addOverlay(layer, `<span style='color:${style.color}'>${key}</span>`);
                overlays[key] = layer;
            });
            // hack for removing the height attribute on the control. Seems that {collapsed:false}} does not
            // work only if we are loading the page and the latter is visible (activated):
            var form = document.querySelector('form.leaflet-control-layers-list');
            if (form){
                form.style.height = "";
            }
            
         },
         getStyle: function(trName){
             return {
                     color: this.colorMap.get(trName),
                     weight: 1
             };
         },
         onEachFeature: function(feature, layer) {
             return; // no-op (for the moment)
         }
    },
    computed:{
        modelNames: function(){
            return Object.keys(this.models);
        }
    }
});