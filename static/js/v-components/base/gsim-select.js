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
        // set <select> style
        this.field.cstyle = ['border-bottom-left-radius: 0rem !important',
                            'border-bottom-right-radius: 0rem !important'].join(';')
        // return custom data:
        return {
            filterBy: {  // DO NOT CHANGE KEYS!
                name: "", // string matching gsim name(s)
                imt: false,  // boolean (imt filter on off)
                map: null  // null or function(gsim_name) => true/false
            },
            choices: Array.from(this.field.choices),  // copy Array to preserve order
            warnings: [], //list of strings of warnings (updated also in watchers below)
        }
    },
    watch: { // https://siongui.github.io/2017/02/03/vuejs-input-change-event/
        filterBy: {
            deep: true,
            handler: function(newVal, oldVal){
                this.filterUpdated();
            }
        },
        'imtField.disabled': function(newVal, oldVal){
            // if we disabled the imt field, uncheck the checkbox, too, if checked:
            if (newVal && this.filterBy.imt){
                this.filterBy.imt = false;
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
            <div style="position:relative; flex: 1 1 auto">
                <field-input :field="field" size="15"></field-input>
                <div v-if="!!warnings.length" class='form-control' ref='warningsDiv'
                     style="position:absolute; right:2rem; top:3rem; bottom:1rem; overflow:auto; width:15rem; word-wrap:break-word">
                    <div v-for="w in warnings" class="small text-muted pt-2 px-3">
                        <span class='text-warning'><i class='fa fa-exclamation-triangle'></i></span>{{ w }}
                    </div>
                </div>
            </div>
        </div>
    
        <!-- GSIM FILTER CONTROLS: -->
        <div class="pt-2 d-flex flex-column form-control border-top-0 rounded-top-0"
             style='flex: 1 1 auto; background-color:transparent !important'>
            <div class="d-flex flex-column" style='flex: 1 1 auto'>
                <div class='mb-1' style='position:relative'>
                    <div class='mb-1'><i class="fa fa-filter"></i> Filter GSIMs &hellip;</div>
                    <table>
                        <tr>
                        <td class='text-nowrap'>
                        <input v-model="filterBy.name" :id="this.field.id + '_name'"
                               placeholder="... by name (ignoring case and spaces)"
                               style='min-width:15rem;display:inline-block;width:initial'
                               type="text" class="form-control form-control-sm">
                        </td>
                        <td v-if="imtField" class='text-nowrap pl-3'>
                            <input v-model="filterBy.imt" :id="this.field.id + '_imt'"
                                   type="checkbox" :disabled='imtField.disabled'>
                            <label :for="this.field.id + '_imt'" class='small my-0'
                                   :disabled='imtField.disabled'>
                                &hellip; defined for selected IMTs
                            </label>
                        </td>
                        <td class='text-nowrap pl-3' style='text-align: right;'>
                        <span :style="[!!filterBy.map ? {'visibility': 'hidden'} : {}]" class='small'>
                            &hellip; selected for a specific region (click on map):
                        </span>
                        </td>
                        </tr>
                    </table>
                    <button v-if="!!filterBy.map" type='button' class="btn btn-sm btn-outline-dark" @click="clearMapFilter"
                            style="position:absolute; right:0; bottom:0">
                        Clear map filter
                    </button>
                </div>
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
            var geoportailLayer = L.tileLayer('https://wxs.ign.fr/{apikey}/geoportail/wmts?REQUEST=GetTile&SERVICE=WMTS&VERSION=1.0.0&STYLE={style}&TILEMATRIXSET=PM&FORMAT={format}&LAYER=ORTHOIMAGERY.ORTHOPHOTOS&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}', {
                attribution: '<a target="_blank" href="https://www.geoportail.gouv.fr/">Geoportail France</a>',
                bounds: [[-75, -180], [81, 180]],
                minZoom: 2,
                maxZoom: 19,
                apikey: 'choisirgeoportail',
                format: 'image/jpeg',
                style: 'normal'
            }).addTo(map);
            // 2 CartoDB gray scale map (very good with overlays, as in our case)
            // the added base layer added is set selected by default (do not add the others then)
            var cartoLayer = L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
                attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
                subdomains: 'abcd',
                maxZoom: 19
            }).addTo(map);

            // instantiate a layer control (the button on the top-right corner for showing/hiding overlays
            // overlays will be added when setting the tr model
            var layersControl = L.control.layers({
                'Map: Geoportail': geoportailLayer, 'Map: Carto': cartoLayer
            }, {}, {collapsed: false, position: 'bottomleft'}).addTo(map);  // https://gis.stackexchange.com/a/68243
            this.addRegionalizationControl(map);
            this.map = map;
            map.on("click", this.mapClicked);
        },
        addRegionalizationControl(map){
            var field = this.field;

            var control = L.control({position: 'topright'});
            control.onAdd = function (map) {
                var div = L.DomUtil.create('div', 'leaflet-control-layers leaflet-control-layers-expanded leaflet-control');
                // prevent click on anything on the div to propagate on the map:
                L.DomEvent.disableClickPropagation(div);
                // Add title:
                var title = L.DomUtil.create('span', '', div);
                title.innerHTML = '<h6>Regionalization:</h6>';
                for (var [val, name] of field.regionalization.choices){
                    var label = L.DomUtil.create('label', 'd-flex flex-row align-items-baseline', div);
                    var input = L.DomUtil.create('input',
                                                 "leaflet-control-layers-selector",
                                                 label);
                    var span = L.DomUtil.create('span', 'ml-2', label);
                    span.innerHTML = name;
                    input.setAttribute('type', 'checkbox');
                    input.setAttribute('value', val);
                    input.checked = field.regionalization.value.includes(val);
                    input.addEventListener('input', function (evt) {
                        var val = evt.target.value;
                        var idx = field.regionalization.value.indexOf(val);
                        if (idx == -1){
                            field.regionalization.value.push(val);
                        }else{
                            field.regionalization.value.splice(idx, 1);
                        }
                    });
                }
                return div;
            };
            control.addTo(map);
        },
        mapClicked(event) {
            var latLng = [event.latlng.lat, event.latlng.lng];
            // Destroy existing markers marker (or move existing one):
            this.removeMarkersFromMap();
            // ad new marker:
            L.marker(latLng).addTo(this.map);
            // query data:
            var data = {
                'lat': latLng[0],
                'lon': latLng[1],
                'reg': this.field.regionalization.value
            };
            // query data and update filter func:
            Vue.post(this.field.regionalization.url, data).then(response => {  // defined in `vueutil.js`
                var gsims = Array.isArray(response.data) ? response.data : Object.keys(response.data);
                this.filterBy.map = null;
                if(gsims && gsims.length){
                    var regionGsims = new Set(gsims);
                    // create filterFunc from list og Gsims:
                    this.filterBy.map = gsim => regionGsims.has(gsim.value);
                }
                this.filterUpdated();
            });
        },
        clearMapFilter(){
            // Destroy existing markers marker (or move existing one):
            this.removeMarkersFromMap();
            this.filterBy.map = null;
        },
        removeMarkersFromMap(){
            this.map.eachLayer(function (layer) {
                if (layer instanceof L.Marker){
                    layer.remove();
                }
            });
        },
        filterUpdated(){
            var defFilterFunc = elm => true;
            var filterFuncs = [];
            if (this.filterBy.name){
                var val = this.filterBy.name;
                var regexp = new RegExp(val.replace(/([^\w\*\?])/g, '\\$1').replace(/\*/g, '.*').replace(/\?/g, '.'), 'i');
                filterFuncs.push(gsim => gsim.value.search(regexp) > -1);
            }
            if (this.filterBy.imt && this.imtField.value && this.imtField.value.length && !this.imtField.disabled){
                var imtClassNames = new Set(this.imtField.value.map(elm => elm.startsWith('SA') ? 'SA' : elm));
                filterFuncs.push(gsim => gsim.imts.some(imt => imtClassNames.has(imt)));
            }
            if (this.filterBy.map){
                filterFuncs.push(this.filterBy.map);
            }
            this.field.choices = this.filterChoices(filterFuncs);
            this.updateWarnings();
        },
        filterChoices(filterFuncs){  // filterFuncs: callable(gsimName) -> bool
            var okGsims = new Array();
            var noGsims = new Array();

            for (var gsim of this.choices){
                // Provide strikethrough for filtered out GSIMs but this won't be
                // rendered in Safari, as <option>s cannot be styled. As such, set also
                // those <option>s disabled for cross browser compatibility:
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
            var disabledCount = 0;
            this.choices.forEach(elm => {
                var disabled = elm.disabled;
                disabledCount += !!disabled;
                if (selGsimNames.has(elm.value)){
                    if (disabled){
                        selFilteredOut.push(elm.value);
                    }
                    if(elm.warning){
                        warnings.push(elm.warning);
                    }
                }
            });
            var allDisabled = disabledCount == this.choices.length ? ['No GSIM matches current filters (all models filtered out)'] : [];
            selFilteredOut = selFilteredOut.map(elm => `${elm} is filtered out but still selected`);
            this.warnings = allDisabled.concat(selFilteredOut.concat(warnings));
            // scroll warnings to top:
            if (this.warnings.length){
                this.$nextTick(() => {
                    var selComp = this.$refs.warningsDiv;
                    if (selComp){
                        selComp.scrollTop=0;
                    }
                });
            }
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
        // copy field and add the 'cstyle' attribute:
        var fieldCopy = {
            'cstyle': ['border-bottom-left-radius:0rem !important',
                       'border-bottom-right-radius:0rem !important'].join(";")
        };
        if ('size' in this.$attrs){
            fieldCopy['size'] = this.$attrs['size'];
        }
        fieldCopy: Object.assign(fieldCopy, this.field);

        return {
            fieldCopy: fieldCopy,
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
        <field-input :field="fieldCopy"></field-input>
        <base-input v-model="SAPeriods" :disabled="field.disabled || !fieldCopy.value.includes('SA')"
                    placeholder="SA periods (space-separated)"
                    :cstyle="'border-top: 0 !important;border-top-left-radius: 0rem !important;border-top-right-radius: 0rem !important;'">
        </base-input>
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