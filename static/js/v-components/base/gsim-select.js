/**
 * Implements a component representing the form element of GSIMs
 */
Vue.component('gsim-select', {
    //https://vuejs.org/v2/guide/components-props.html#Prop-Types:
    props: {
        field: {type: Object}, // see field-input
        imtField: {type: Object, default: null}, // field of IMTs (can be null)
        regionalizations: {type: Array, default: []},
        regionalizationQueryURL: {type: String}
    },
    data: function () {
    	return {
        	// filterValue: '',
            // filterType: 'GSIM name',  // Filter Gsims by:
            filterBy: {  // DO NOT CHANGE KEYS!
                name: "",
                imt: false,
                geolocation: null
            },
            choices: Array.from(this.field.choices),  // copy Array to preserve order
            filterFunc: elm => true,
            // Vue.eGSIM is created in VueUtil.js: it's an Object storing gsims, imts,
            // and their relations via custom methods (e.g., imtsOf(gsim), warningOf(gsim)...)
            // make it available here as `this.gsimManager`:
            // gsimManager: Vue.eGSIM, // FIXME REMOVE
            selectableGsims: new Set(),  // updated in watcher below
            warnings: [] //list of strings of warnings (updated also in watchers below)
        }
    },
    watch: { // https://siongui.github.io/2017/02/03/vuejs-input-change-event/
//        filterValue: function(value, oldValue) {  // FIXME REMOVE
//            if (oldValue !== value){
//                this.updateFilter();
//            }
//        },
//        filterType: function(value, oldValue) {
//            if (oldValue !== value){
//            	// when changing the filterType, reset also the default ("" or [], depending on the type):
//            	var valIsStr = typeof this.filterValue === 'string';
//            	if (value === this.filterTypes[0] && !valIsStr){
//            		this.filterValue = '';  // calls updateFilter (see above)
//            		return;
//            	}else if(valIsStr){
//            		this.filterValue = [];  // calls updateFilter (see above)
//            		return;
//            	}
//                this.updateFilter();
//            }
//        },
        filterBy: function(value, oldValue){
            deep: true,
        	handler: function(newVal, oldVal){
        		this.filterUpdated();
        	}
        }
        // listen for changes in the selected imts:
        'imtField.value': {  // even if it should not happen: if we change the imt param name, change it also here ...
        	immediate: true,
        	handler: function(newVal, oldVal){
        	    this.filterUpdated();
//        		var selectableGsims = this.field.choices;
//	            var selectedimts = newVal;
//	            if (selectedimts.length){
//	                var gsimManager = this.gsimManager;
//	            	selectableGsims = selectableGsims.filter(gsim => {
//	                	return selectedimts.every(imt => gsimManager.imtsOf(gsim).includes(imt));
//	                });
//	            }
//	            this.selectableGsims = new Set(selectableGsims);
        	}
        },
        // listen for changes in gsim selection FIXME: REMOVE?? why this???
        'field.val': {
        	immediate: true,
        	handler: function(newVal, oldVal){
	        	var gsimManager = this.gsimManager;
        		this.warnings = (newVal || []).filter(gsim => gsimManager.warningOf(gsim)).map(gsim => gsimManager.warningOf(gsim));
        		if (this.warnings.length && newVal && newVal.length && this.$refs.select){
        			// scroll last element into view because we might hide it (see template)
        			// (https://vuejs.org/v2/guide/components-edge-cases.html#Accessing-Child-Component-Instances-amp-Child-Elements)
        			var elm = Array.from(this.$refs.select.options).filter(opt => opt.value === newVal[newVal.length-1]);
        			if (elm && elm.length == 1){
        				this.$nextTick(() => {
        					var [r1, r2] = [elm[0].parentElement.getBoundingClientRect(),
				        					elm[0].getBoundingClientRect()];
				        	if (r2.y >= r1.height + r1.y){
			                	elm[0].scrollIntoView(false);
			                }
			            });
        			}
        		}
        	}
        }
    },
    computed: {
        // computed properties are cached: https://vuejs.org/v2/guide/computed.html
        // https://forum.vuejs.org/t/how-do-computed-properties-know-how-to-change/24140/2
//        visibleGsimsSet: function(){
//        	return new Set(this.field.choices.filter(gsim => this.filterFunc(gsim)));
//        },
        selectedFilteredOut: function(){
            var selectedGsimNames = new Set(this.field.value);
            return this.choices.filter(elm => selectedGsimNames.has(elm.value));
        	// return this.field.value.reduce((accumulator, gsim) => accumulator + !this.visibleGsimsSet.has(gsim), 0);
        }
    },
    template: `<div>
        <field-input :field="field"></field-input>


        <div v-show='warnings.length' class='form-control position-relative border-top-0 rounded-top-0'
             style='height:4rem;overflow:auto'>

            <div class='small position-absolute pos-x-0 pos-y-0 p-1'>
                <div>{{ warnings.length }} warning(s):</div>
                <div v-for='warn in warnings'>
                    <span class='text-warning'><i class="fa fa-exclamation-triangle"></i></span> {{ warn }}
                </div>
            </div>
        </div>
    
      <!-- GSIM FILTER CONTROLS: -->
      <div class="mt-1" >
          <div>
	          <div class='d-flex flex-column small' style='padding-left: .3rem;'>
	          	  <span v-if="selectedHiddenCount">
	          	  	<i class="text-warning fa fa-exclamation-triangle"></i> {{ selectedFilteredOut.length }} filtered out Gsim(s) still selected
	          	  </span>
          	  </div>
          </div>
          Filter GSIMs by:
          <div class='text-nowrap'>
            Name: <input v-model="filterBy.name" :id="this.field.id + '_name'" type="text" class="form-control form-control-sm">
          </div>
          <div class='text-nowrap'>
            <input v-model="filterBy.imt" :id="this.field.id + '_imt'" type="checkbox">
            <label :for="this.field.id + '_imt'"> Selected IMTs</label>
          </div>
          <div>
              Gsims selected for a specific area (click on map):
              <div :id="this.field.id + '_geolocation'"></div>
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
            this.map = this.createLeafletMap();
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
//            // this.form.gsim.val = []; // force server to take all gsims by default
//            // this.form.imt.val = []; // force server to take all gsims by default
//            var overlays = this.overlays;
//            // perform query only on visible layers selected. Get visible layers:
//            this.form.trt.val = Object.keys(overlays).filter(layerName => {
//               return overlays[layerName]._map ? true : false;
//            });
//            // make imt and gsim hidden, this will NOT send the parameter to the
//            // client (=> do not filter by IMTs)
//            this.form.imt.is_hidden = true;
//            this.form.gsim.is_hidden = true;
//            // send request:
//            Vue.post(this.regionalizationQueryURL, this.regionalizations).then(response => {  // defined in `vueutil.js`
//                if(response.data && response.data.length){
//                    this.filterUpdated(response.data);
//                }
//            });
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
                var imtClassNames = new Set(this.imtField.value.map(elm => elm.startsWith('SA(') ? 'SA' : elm));
                filterFuncs.push(gsim => gsim.imts.some(imt => imtClassNames.has(imt)));
            }
            if (this.filterBy.geolocation){
                Vue.post(this.regionalizationQueryURL, this.regionalizations).then(response => {  // defined in `vueutil.js`
                    if(response.data && response.data.length){
                        var regionGsims = new Set(response.data);
                        filterFuncs.push(elm =>regionGsims.has(elm));
                        this.field.choices = this.filterChoices(filterFuncs);
                    }
                });
            }else if (filterFuncs.length){
                this.field.choices = this.filterChoices(filterFuncs);
            }else{
                this.field.choices = this.choices;
            }
        },
        filterChoices(filterFuncs){  // filters => callable, Set, Array
            var okGsim = new Array();
            var noGsim = new Array();

            for (var gsim of this.choices){
                // Provide strikethrough for filtered out <option>s but note that
                // styling does not work in Safari. As such , set also those options
                // disabled for cross browser compatibility:
                if (filterFuncs.every(filterFunc => filterFunc(gsim.value))){
                    gsim.disabled = false;
                    gsim.style = '';
                    okGsims.push(gsim);
                }else{
                    gsim.disabled = true;
                    gsim.style = 'text-decoration: line-through;';
                    noGsim.push(gsim);
                }
            }

            if (!noGsim){
                return this.choices;
            }

            var separator = {
                value: '',
                disabled: true
                innerHTML: `--- Filtered out (${noGsim.length} of ${this.choices.length}): ---`;
            };

            if(!okGsim){
                return [separator].concat(noGsim);
            }else{
                return okGsim.concat([separator]).concat(noGsim);
            }
        }
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
    	// (optional) name of the SA periods input component. form[saPeriodName] must be an Object
        // of the same type of 'elm' described above:
        // saPeriodName: {type: String, default: 'sa_period'},
    },
    data: function () {
    	return {
    	    selectedIMTClassnames = [],  // copy choices
    	    selectedSAPeriods = ''
//        	// define the Object whose data is associated to this component:
//            elm: this.form[this.name],
//            // define the Object whose data is associated to the selected gsims:
//            gsimField: this.form.gsim,
//            // define the Set of the selectable IMTs (see watchers below):
//            selectableImts: new Set(),
//            // Vue.eGSIM is created in vueutil.js: it's an Object storing gsims, imts,
//            // and their relations via custom methods (e.g., imtsOf(gsim), warningOf(gsim)...)
//            // make it available here as `this.gsimManager`:
//            gsimManager: Vue.eGSIM
        }
    },
    created: function(){
    	// no-op
    },
    watch: { // https://siongui.github.io/2017/02/03/vuejs-input-change-event/
        'selectedIMTClassNames': function(newVal, oldVal){
            this.updateSelectedImts();
        },
        'selectedSAPeriods': function(newVal, oldVal){
            this.updateSelectedImts();
        }
//    	'gsimField.val': function(newVal, oldVal){
//    		// watch for changes in selected gsims
//    		this.computeSelectableImts();
//    	},
//    	'elm.attrs.disabled': function(newVal, oldVal){
//    		// watch for changes in disabled state of the imt
//    		this.updateSaPeriodsEnabledState();
//    	},
//    	'elm.val': {
//    		// watch for changes in selected imts. Immediate=true: call handler immediately
//    		immediate: true,
//    		handler: function(newVal, oldVal){
//    			this.computeSelectableImts();
//    		}
//    	}
    },
    computed: {
        // no-op
    },
    template: `<div class='d-flex flex-column'>
        <base-input v-model="selectedIMTClassNames" :choices="field.choices" :disabled="field.disabled" multiple></base-input>
        <base-input v-model="selectedSAPeriods" :disabled="field.disabled || !selectedIMTClassnames.includes('SA')"
                    placeholder="SA periods (space-separated numbers)">
    </div>`,
    methods: {
        updateSelectedImts(){
            this.field.value = this.getSelectedImts();
        },
        getSelectedImts(){
            var imts = Array.from(this.selectedIMTClassNames);
            if (this.selectedIMTClassNames.includes('SA')){
                var periods = this.selectedSAPeriods.trim().split(/\s+/).map(p => `SA(${p})`);
                imts = imts.concat(periods);
            }
            return imts;
        }
//        ;: function(){
//        	var disabled = !!this.elm.attrs.disabled || !this.selectableImts.has('SA');
//        	this.form[this.saPeriodName].attrs.disabled = disabled;
//        	this.form[this.saPeriodName].is_hidden = !this.elm.val.includes('SA');
//        },
//        computeSelectableImts: function(){
//        	var gsimManager = this.gsimManager;
//            var selectedgsims = this.gsimField.val || [];
//            var selectableImts = [];
//            for (var gsim of selectedgsims){
//            	if (!selectableImts.length){ // first gsim element
//            		selectableImts = Array.from(gsimManager.imtsOf(gsim));  // make a copy
//            	}else{
//            		for (var i=selectableImts.length-1; i>=0; i--){
//            			if (!gsimManager.imtsOf(gsim).includes(selectableImts[i])){
//            				selectableImts.splice(i, 1);
//            			}
//            		}
//            	}
//            	if (!selectableImts.length){
//            		break;
//            	}
//            }
//            this.selectableImts = new Set(selectableImts);
//            this.updateSaPeriodsEnabledState();
//        }
    }
})