/**
 * Registers globally a Vue component. The name of the component
 * (first argument of 'Vue.component' below must be equal to this file's name 
 * (without extension)
 */
Vue.component('gsims', {
    props: {
        form: Object,
        url: String,
        // Additional urls Object (string key mapped to urls).
        // Note: use a function for the 'default' key to prevent sharing the same object (https://github.com/vuejs/vue/issues/1032#issuecomment-120212888)
        urls: {type: Object, default: () => {return {}}}
    },
    data: function(){
        return {
            id: 'tr_map_id',
            trUrl: this.urls.getTectonicRegionalisations,  // this props is passed from backend
            vuePopupComponent: null,
            models: {},  //object of model names name mapped to geojson data
            map: undefined,
            layersControl: undefined,
            overlays: {},  // object of layer name (tectonic region) => leaflet layer
            // clicked: false,
            colorMap: Vue.colorMap() // defined in vueutil.js
        }
    },
    watch:{
        selectedModel: function(oldVal, newVal){
            if(newVal != oldVal){
                this.$nextTick(this.updateDOM);  // executed after every part of the DOM has rendered, inlcuding mounted() below
            }
        }
    },
    computed:{
        modelNames: function(){
            return Object.keys(this.models);
        },
        selectedModel:{
            get: function(){
                return this.form.model.val;
            },
            set: function(oldval, newval){
                this.form.model.val = newval;
                if(newVal != oldVal){
                    this.$nextTick(this.updateDOM);  // executed after every part of the DOM has rendered, inlcuding mounted() below
                }
            }
        }
    },
    template:`<div class='flexible d-flex flex-column'>
    	<div class='d-flex flex-row align-items-baseline m-2'>
	        <span class='mr-2 text-nowrap'>Tectonic regionalisation model</span>
	        <select v-model='selectedModel' class='form-control flexible'>
	            <option v-for='mod in modelNames' :key='mod'>
	                {{ mod }}
	            </option>
	        </select>
        </div>
        <div :id='id' class='flexible border' style='font: inherit !important'></div>
        </div>`,
    created: function(){
        Vue.post(this.trUrl).then(response => {  // defined in `vueutil.js`
            if (response && response.data){
                this.models = response.data.models;
                this.form.model.val = response.data.selected_model || Object.keys(response.data.models)[0];
            } 
        });
    },
    mounted: function(){
        var map = L.map(this.id, {center: [48, 7], zoom: 4});
        
        // provide two base layers. Keep it simple as many base layers are just to shof off
        // and they do not need to be the main map concern
        // 1 MapBox Outdorrs (if you want more, sign in to mapbox. FIXME: why is it working with the token then?) 
        var bl2 = L.tileLayer('https://api.tiles.mapbox.com/v4/{id}/{z}/{x}/{y}.png?access_token=pk.eyJ1IjoibWFwYm94IiwiYSI6ImNpejY4NXVycTA2emYycXBndHRqcmZ3N3gifQ.rJcFIG214AriISLbB6B5aw', {
            attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://www.mapbox.com/about/maps/">MapBox</a> <a href="https://www.mapbox.com/map-feedback/#/-74.5/40/10">Improve this Map</a>' ,
            maxZoom: 18,
            id: 'mapbox.outdoors'  //  'mapbox.streets'
          });
        // 2 CartoDB gray scale map (very good with overlays, as in our case) 
        // the added base layer added is set selected by default (do not add the others then)
        var bl1 = L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
            subdomains: 'abcd',
            maxZoom: 19
        }).addTo(map);

        // instantiate a layer control (the button on the top-right corner for showing/hiding overlays
        // overlays will be added when setting the tr model
        this.layersControl = L.control.layers({'base layer 1': bl1, 'base layer 2': bl2}, {}, {collapsed:false}).addTo(map);  // https://gis.stackexchange.com/a/68243
        // note above: collapsed:false makes the legend control visible. This does not work though in 100% of the cases,
        // so see in updateDom a hack for solving this problem (remove control height, if set)
        this.map = map;
        map.on("click", this.clickHandler);
    },
    activated: function(){
        // Called when a kept-alive component is activated to fix leaflet problems on resize.
        // See https://vuejs.org/v2/api/#activated
        // https://github.com/Leaflet/Leaflet/issues/4835#issuecomment-241445225
        var map = this.map;
        setTimeout(function(){ map.invalidateSize()}, 100);
    },
    methods:{
        clickHandler: function(event) {
            // destroy current vue popup component to free memory and all bound props which
            // might throw useless errors when changed afterwards:
            if(this.vuePopupComponent){
                this.vuePopupComponent.$destroy();
            }
            // build a new one:
            this.form.latitude.val = event.latlng.lat;
            this.form.longitude.val = event.latlng.lng;
            // this.form.gsim.val = []; // force server to take all gsims by default
            // this.form.imt.val = []; // force server to take all gsims by default
            var overlays = this.overlays;
            // perform query only on visible layers selected. Get visible layers:
            this.form.trt.val = Object.keys(overlays).filter(layerName => {
               return overlays[layerName]._map ? true : false;
            });
            // make imt and gsim hidden, this will NOT send the parameter to the
            // client (=> do not filter by IMTs)
            this.form.imt.is_hidden = true;
            this.form.gsim.is_hidden = true;
            // send request:
            Vue.post(this.url, this.form).then(response => {  // defined in `vueutil.js`
                if(response.data && response.data.length){
                    this.openPopup(event, response.data);
                }
            });
        },
        openPopup: function(event, gsims){
            // dynamically create vue 'gsimselect' component:
            // https://css-tricks.com/creating-vue-js-component-instances-programmatically/
            // (the only difference with the link above is the use of Vue.options['components']['gsimselect']
            // to retrieve globally defined components):
            var ComponentClass = Vue.extend(Vue.options['components']['gsimselect'])
            
            // modify the current form gsim field:
            this.form.gsim.choices = Array.from(gsims);
            this.form.gsim.val = [];
            propsData = {
            	form: this.form,
            	selectbutton: {
            		html: 'Select globally for comparison and testing',
            		attrs: {
            			'data-balloon-pos': "up",
            			'data-balloon-length': "medium",
            			'aria-label': "After choosing one or more GSIMs from the list above, clicking this button will automatically select the chosen GSIMs in: Model-to-Model Comparison, Model-to-Data Comparison and Model-to-Data Testing"
            		}
            	},
            	showfilter: true
            }

            var instance = new ComponentClass({
                propsData: propsData
            })

            // forward the gsim selection fired by the <gsimselect> to the listeners of this component (if provided):
            instance.$on('selection-fired', gsims => {
                this.$emit('gsim-selected', gsims);
            });

            // mount the instance:
            instance.$mount() // pass nothing
            // add custom classes (must be done after mount):
            // Note that we need to style also .leaflet-popup-content in `base.css`
            // for this to work:
            instance.$el.style.maxWidth = '60vw';
            instance.$el.style.maxHeight = '50vh';
            instance.$el.style.height = `${gsims.length > 0 ? gsims.length : 10}em`;
            instance.$el.style.width = '25em';
            this.vuePopupComponent = instance;

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
            // this.models is a dict of model (string) mapped to a dict representing the model
            // data (see below)
            var featureCollections = this.models[this.selectedModel] || {};
            // featureCollections is a dict of TRT (string) mapped to a Geojson
            // feature collection of the form:
            // { "type": 'FeatureCollection',
            //   "features": [
            //        {
            //          "type": "Feature",
            //          "geometry": {
            //             "type": "Point",
            //             "coordinates": [125.6, 10.1]
            //          },
            //          "properties": {}  // empty for perf. reasons
            //        }, ...
            //   ]
            // }
    
            // update the map:
            Object.keys(featureCollections).forEach(key => {
                // create layer(s) from the geojson FeatureCollections.
                // For info see:
                // http://leafletjs.com/examples/geojson/ and (add css class, not used but if needed):
                // https://stackoverflow.com/questions/17086195/leaflet-path-how-can-i-set-a-css-class (2nd post)
                var style = this.getStyle(key);
                var layer = L.geoJson(featureCollections[key],{
                    style: style,
                    onEachFeature: this.onEachFeature}
                ).addTo(map);
                // add a span label with the data-tr-color attribute (why? see later for details)
                var k = layersControl.addOverlay(layer, `<span data-tr-color='${style.color}'>${key}</span>`);
                overlays[key] = layer;
            });
            
            // hack for styling the control <label> and its <input type=checkbox ... :
            // we get all span Use that data attribute to retreive
            // all the span[data-tr-color] elements and we style the parent label.
            // See custom css for details:
            for (var spanElm of document.querySelectorAll('span[data-tr-color]')){
            	this._customizeOverlayCheckbox(spanElm, spanElm.getAttribute('data-tr-color'));
            };
            
            // hack for removing the height attribute on the control. Seems that {collapsed:false}} does not
            // work only if we are loading the page and the latter is visible (activated):
            var leafLegend = document.querySelector('form.leaflet-control-layers-list');
            if (leafLegend){
                leafLegend.style.height = "";
            }
            
            // also style differently the leaflet controls
            var leafControls = document.querySelectorAll('div.leaflet-control');
            for (var ctrl of leafControls){
                ctrl.style.borderWidth = "1px";
                ctrl.classList.add("shadow");
            }
            
         },
         _customizeOverlayCheckbox: function(spanElement, color){
         	var label = spanElement.parentNode;
		    while (label && label.tagName.toLowerCase() != 'label'){
		    	label = label.parentNode;
		    }
         	// this customizes the <label> tag of the checkbox and wrapping <label> for each
         	// Tectonic Region. Yes, hacky, but Leaflet forces us to do so: 
         	label.classList.add('customcheckbox', 'checked');
         	label.style.display = 'flex';  // customcheckbox it is inline-flex by default
         	label.style.color = color;
        	label.querySelector('input[type=checkbox]').addEventListener('change', function() {
        		// on checkbox change, add checked class to the wrapping label. See css for styled checkbox
			    if(this.checked) {
			        label.classList.add('checked');
			    } else {
			        label.classList.remove('checked');
			    }
			});
         },
         getStyle: function(trName){
             // FIXME: is there any *EASILY accessible* documentation about the styling properties????!!!!:
             return {
                 fillColor: this.colorMap.get(trName),
                 fillOpacity: 0.2,  // if you remove this, it defaults to 0.2 (checked on the map)
                 color: this.colorMap.get(trName),
                 opacity: .5,
                 weight: .25,  // areas border width (found out by playing around + visual check)
             };
         },
         onEachFeature: function(feature, layer) {
             layer.on('mouseover', function () {
                 this.setStyle({
                     weight: 2,
                     fillOpacity: 0.5,
                 });
             });
             layer.on('mouseout', function () {
                 this.setStyle({
                     weight: .25,
                     fillOpacity: 0.2,
                 });
             });
         }
    }
});