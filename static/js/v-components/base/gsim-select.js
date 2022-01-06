/**
 * Implements a component representing the form element of GSIMs
 */
Vue.component('gsim-select', {
    //https://vuejs.org/v2/guide/components-props.html#Prop-Types:
    props: {
        field: {type: Object}, // see field-input
        imtField: {type: Object, default: null}, // field of IMTs (can be null)
        regionalizations: {type: Array, default: () => {[]}},
        regionalizationQueryURL: {type: String}
    },
    data: function () {
    	return {
            filterBy: {  // DO NOT CHANGE KEYS!
                name: "",
                imt: false,
                geolocation: null
            },
            choices: Array.from(this.field.choices),  // copy Array to preserve order
            warnings: [] //list of strings of warnings (updated also in watchers below)
        }
    },
    watch: { // https://siongui.github.io/2017/02/03/vuejs-input-change-event/
        filterBy: {
            deep: true,
        	handler: function(newVal, oldVal){
        		this.filterUpdated();
        	}
        },
        // listen for changes in the selected imts:
        'imtField.value': {  // even if it should not happen: if we change the imt param name, change it also here ...
        	// immediate: true,
        	handler: function(newVal, oldVal){
        	    if (this.filterBy.imt){
        	        this.filterUpdated();
        	    }
        	}
        },
        'field.value': {
            immediate: true,
            handler: function(newVal, oldVal){
                this.updateWarnings();
            }
        }
    },
    computed: {
    },
    template: `<div class='d-flex flex-column'>

        <div class='d-flex flex-row'>
            <div class="flexible">
                <field-input :field="field" size="15"></field-input>
            </div>
            <div v-show='warnings.length' style='position:relative;width:10rem;overflow:auto'>
                <div class='small position-absolute ps-3' style='left:0;right:0;word-break: break-word;'>
                    <div v-for='warn in warnings'>
                        <span class='text-warning'><i class="fa fa-exclamation-triangle"></i></span> {{ warn }}
                    </div>
                </div>
            </div>
        </div>
    
        <!-- GSIM FILTER CONTROLS: -->
        <div class="mt-1 d-flex flex-column" style='flex: 1 1 auto'>
            <div class="d-flex flex-column" style='flex: 1 1 auto'>
                <div><i class="fa fa-filter mb-1"></i> Filter GSIMs &hellip;</div>
                <table class='mb-1'>
                    <tr>
                    <td class='text-nowrap'>
                    <input v-model="filterBy.name" :id="this.field.id + '_name'"
                           placeholder="... by name (ignoring case and spaces)"
                           style='min-width:15rem;display:inline-block;width:initial'
                           type="text" class="form-control form-control-sm">
                    </td>
                    <td v-if="imtField" class='text-nowrap ps-3'>
                        <input v-model="filterBy.imt" :id="this.field.id + '_imt'" type="checkbox" class='me-1'>
                        <label :for="this.field.id + '_imt'" class='small'>&hellip; defined for selected IMTs</label>
                    </td>
                    <td class='text-nowrap ps-3' style='text-align: right;'>
                    <span class='small'>&hellip; selected for a specific location (click on map):</span>
                    </td>
                    </tr>
                </table>
                <div :id="this.field.id + '_geolocation'" style='flex: 1 1 auto'></div>
           </div>
        </div>
    </div>`,
    mounted: function(){
        this.createLeafletMap();
    },
    activated: function(){
        // Called when a kept-alive component is activated to fix leaflet problems on resize.
        // See https://vuejs.org/v2/api/#activated
        // https://github.com/Leaflet/Leaflet/issues/4835#issuecomment-241445225
        var map = this.map;
        setTimeout(function(){ map.invalidateSize()}, 100);
    },
    methods: {
        createLeafletMap(){
            var id = this.field.id + '_geolocation'
            var map = L.map(id, {center: [48, 7], zoom: 4});

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
            this.layersControl = L.control.layers({
                'base layer 1': bl1,
                'base layer 2': bl2
            }, {}, {collapsed: false}).addTo(map);  // https://gis.stackexchange.com/a/68243
            this.map = map;
            map.on("click", this.mapClicked);
        },
        mapClicked: function(event) {
            // destroy current vue popup component to free memory and all bound props
            // which might throw useless errors when changed afterwards:
            if(this.mapMarker){
                this.mapMarker.$destroy();
            }
            // build a new one:
            this.filterBy.geolocation = [event.latlng.lat, event.latlng.lng];
            // Add marker
            this.mapMarker = L.marker(this.filterBy.geolocation).addTo(this.map);
            this.filterUpdated();
        },
        filterUpdated(){
            var defFilterFunc = elm => true;
            var filterFuncs = [];
            if (this.filterBy.name){
                var val = this.filterBy.name;
                var regexp = new RegExp(val.replace(/([^\w\*\?])/g, '\\$1').replace(/\*/g, '.*').replace(/\?/g, '.'), 'i');
                filterFuncs.push(gsim => gsim.value.search(regexp) > -1);
            }
            if (this.filterBy.imt && this.imtField.value && this.imtField.value.length){
                var imtClassNames = new Set(this.imtField.value.map(elm => elm.startsWith('SA') ? 'SA' : elm));
                filterFuncs.push(gsim => gsim.imts.some(imt => imtClassNames.has(imt)));
            }
            if (this.filterBy.geolocation){
                Vue.post(this.regionalizationQueryURL, this.filterBy.geolocation, this.regionalizations).then(response => {  // defined in `vueutil.js`
                    if(response.data && response.data.length){
                        var regionGsims = new Set(response.data);
                        // create filterFunc from list og Gsims:
                        filterFuncs.push(elm => regionGsims.has(elm));
                        this.field.choices = this.filterChoices(filterFuncs);
                        this.updateWarnings();
                    }
                });
            }else{
                this.field.choices = this.filterChoices(filterFuncs);
                this.updateWarnings();
            }
        },
        filterChoices(filterFuncs){  // filters => callable, Set, Array
            var okGsims = new Array();
            var noGsims = new Array();

            for (var gsim of this.choices){
                // Provide strikethrough for filtered out <option>s but note that
                // styling does not work in Safari. As such , set also those options
                // disabled for cross browser compatibility:
                if (filterFuncs.every(filterFunc => filterFunc(gsim))){
                    // Note: if no filterFuncs provided we land here (`[].every` => true)
                    gsim.disabled = false;
                    gsim.style = '';
                    okGsims.push(gsim);
                }else{
                    gsim.disabled = true;
                    gsim.style = 'text-decoration: line-through;';
                    noGsims.push(gsim);
                }
            }

            if (!noGsims.length){
                return this.choices;
            }

            var separator = {
                value: '',
                disabled: true,
                innerHTML: ""
            };

            if(!okGsims.length){
                return noGsims;
            }else{
                return okGsims.concat([separator]).concat(noGsims);
            }
        },
        updateWarnings(){
            var selGsimNames = new Set(this.field.value);
            var selFilteredOut = [];
            var warnings = [];
            this.choices.forEach(elm => {
                if (selGsimNames.has(elm.value)){
                    if (elm.disabled){
                        selFilteredOut.push(elm.value);
                    }
                    if(elm.warning){
                        warnings.push(elm.warning);
                    }
                }
            });
            selFilteredOut = selFilteredOut.map(elm => `${elm} is selected but filtered out`);
            this.warnings = selFilteredOut.concat(warnings);
        },
    },
    deactivated: function(){
        // no-op
    }
})


/**
 * HTML component representing the form element of IMTs and SA periods
 */
Vue.component('imt-select', {
    //https://vuejs.org/v2/guide/components-props.html#Prop-Types:
    props: {
    	field: {type: Object},
    },
    data: function () {
    	return {
    	    fieldCopy: Object.assign({}, this.field),
    	    SAPeriods: ''
        }
    },
    created: function(){
    	// no-op
    },
    watch: { // https://siongui.github.io/2017/02/03/vuejs-input-change-event/
        'fieldCopy.value': function(newVal, oldVal){
            this.updateSelectedImts();
        },
        'field.error': function(newVal, oldVal){
            this.fieldCopy.error = newVal;
        },
        'field.disabled': function(newVal, oldVal){
            this.fieldCopy.disabled = newVal;
        },
        'SAPeriods': function(newVal, oldVal){
            this.updateSelectedImts();
        }
    },
    computed: {
        // no-op
    },
    template: `<div class='d-flex flex-column'>
        <field-input :field="fieldCopy" class="mb-1"></field-input>
        <base-input v-model="SAPeriods" :disabled="field.disabled || !fieldCopy.value.includes('SA')"
                    placeholder="SA periods (space-separated)"></base-input>
    </div>`,
    methods: {
        updateSelectedImts(){
            this.field.value = this.getSelectedImts();
        },
        getSelectedImts(){
            var imts = Array.from(this.fieldCopy.value);
            if (imts.includes('SA')){
                var periods = this.SAPeriods.trim().split(/\s+/).map(p => `SA(${p})`);
                imts = imts.concat(periods);
            }
            return imts;
        }
    }
})