Vue.component('trmap', {
    props: {'initurl': {type:String}, 'url': {type:String}, 'eventbus':{default:null}, 'avalgsims': Map, 'selectedgsims': Array},
    data: function(){
        return {
            'id': 'tr_map_id',
            'selectedProject': undefined, //name of selected project
            'projects': {},  //object of project name mapped to geojson data
            'map': undefined,
            'layersControl': undefined,
            'overlays': [],
            'clicked': false,
            'colorMap': Vue.colorMap() // defined in vueutil.js
        }
    },
    template:`<div class='flex-direction-col'>
        <select v-model='selectedProject' class='form-control mb-2'>
            <option v-for='project in projectNames' :key='project' v-bind:value="project">
                {{ project }}
            </option>
        </select>
        <div :id='id' class='flexible'></div>
        </div>`,
    created: function(){
         if(this.eventbus){
             this.eventbus.$on('postresponse', (response, isError) => {
                 if ((response.config.url == this.initurl) && !isError){
                     this.$set(this, 'projects', response.data.projects);
                     this.$set(this, 'selectedProject', response.data.selected_project || Object.keys(response.data.projects)[0]);
                 }
             });
             this.eventbus.$emit('postrequest', this.initurl);
         }
    },
    watch:{
        selectedProject: function(oldVal, newVal){
            if(newVal != oldVal){
                this.$nextTick(this.updateDOM);  // executed after every part of the DOM has rendered, inlcuding mounted() below
            }
        }
    },
    mounted: function(){
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

        // instanitate a layer control (the button on the top-right corner for showing/hiding overlays
        // overlays will be added when setting the project
        this.$set(this, 'layersControl', L.control.layers({}, {}, {collapsed:false}).addTo(map));
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
            var data = {'project': this.selectedProject, 'latitude': event.latlng.lat,
                    'longitude': event.latlng.lng}
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
            instance.$slots.default = ['Gsims defined for the selected Tectnotic Region(s):'];
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
             * Sets the overlays mapped to the given key which is a string denoting a project name
             * key must be stored in this class projects (with relative associated shape files. See class constructor)
             */
            var map = this.map;
            var layersControl = this.layersControl;
            var overlays = this.overlays;
    
            overlays.forEach(layer => {
                map.removeLayer(layer);
                layersControl.removeLayer(layer);
            });
    
            overlays = this.overlays = [];
            var geojson = this.projects[this.selectedProject] || {};
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
                overlays.push(layer);
            });
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
        projectNames: function(){
            return Object.keys(this.projects);
        }
    }
});