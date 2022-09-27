/* GSIM and IMT <select> components */

EGSIM.component('gsim-select', {
	//https://vuejs.org/v2/guide/components-props.html#Prop-Types:
	props: {
		field: {type: Object}, // see field-input
		imtField: {type: Object, default: null} // field of IMTs (can be null)
	},
	emits: ['gsim-selected'],
	data() {
		// set <select> style
		this.field.style = ['border-bottom-left-radius: 0rem !important',
							'border-bottom-right-radius: 0rem !important'].join(';')
		// return custom data:
		return {
			regionalization: this.field['data-regionalization'] || {},
			filterBy: {  // DO NOT CHANGE KEYS!
				name: "", // string matching gsim name(s)
				imt: false,  // boolean (imt filter on off)
				map: null  // null or function(gsim_name) => true/false
			},
			mapOffsetParent: undefined,  // to refresh the map when made visible again
			choices: Array.from(this.field.choices),  // avoid modifying or reordering field.choices
			modelNamesSet: new Set(this.field.choices.map(elm => elm.value)), // used when view=text to check typos
			warnings: [], //list of strings of warnings (updated also in watchers below)
			mapId: `map${Date.now()}${Math.random()}`,
			selectionView: true
		}
	},
	watch: { // https://siongui.github.io/2017/02/03/vuejs-input-change-event/
		filterBy: {
			deep: true,
			handler(newVal, oldVal){
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
			handler(newVal, oldVal){
				if (this.filterBy.imt){
					this.filterUpdated();
				}
			}
		},
		'field.value': {
			immediate: true,
			handler(newVal, oldVal){
				this.updateWarnings();
				this.$emit('gsim-selected', newVal)
			}
		}
	},
	computed: {
		infoMsg(){
			return `${this.field.value.length || 0} of ${this.field.choices.length} selected`
		},
		textSelectionErrorMsg(){
			var msg = "";
			if (!(this.field.value) || !(this.field.value.length)){
				msg = "No model provided";
			}else if (this.field.value.some(elm => !elm || !this.modelNamesSet.has(elm))){
				msg = 'Invalid model name(s), check empty lines or typos';
			}
			return msg ? `<span class='text-warning me-1'><i class='fa fa-exclamation-triangle'></i></span>${msg}` : "";
		},
		modelSelectionAsString: {  // called when we are in text view mode
			get(){
				var retVal = (this.field.value.length ? this.field.value : []).join("\n")
				// retVal should be what the textarea displays, however, as it is it
				// would overwrite the text content while editing, e.g. typing a newline. So:
				if (this.$refs.textSelectionContainer){
					var textArea = this.$refs.textSelectionContainer.querySelector('textarea');
					var currentText = "" + textArea.value;
					// we need to allow newlines, so first get the text representation
					// of the currently selected models:
					if (currentText.trim() == retVal){
						retVal = currentText;
					}
				}
				return retVal;
			},
			set(text){
				this.field.value = text.trim().split("\n");
			}
		}
	},
	template: `<div class='d-flex flex-column' style='flex: 1 1 auto'>
		<field-label :field="field">
			<template v-slot:trailing-content>
				<span v-if="!field.error" class='ms-2 small text-muted' v-html="infoMsg"></span>
				<i v-if="field.value.length && !field.error"
				   @click="field.value=[]" class="fa fa-times-circle ms-2"
				   style="cursor: pointer;" title="Clear selection"></i>
				<i v-if="!field.error"
				   @click="toggleView" class="fa ms-2"
				   :class="selectionView ? 'fa-file-text' : 'fa-list-alt'"
				   :title="selectionView ? 'Switch to text view' : 'Switch to list view'"
				   style="cursor: pointer;" ></i>
			</template>
		</field-label>
		<div class='flex column' style="position:relative; flex: 1 1 auto"
			:style="{display: selectionView ? 'flex' : 'none'}"
			ref='listSelectionContainer'>
			<field-input :field="field" :style="'flex: 1 1 auto'"/>
			<div v-if="!!warnings.length" class='form-control' ref='warningsDiv'
				 style="position:absolute; right:2rem; top:1rem; bottom:1rem; overflow:auto; width:15rem; word-wrap:break-word">
				<div v-for="w in warnings" class="small text-muted pt-2 px-3">
					<span class='text-warning'><i class='fa fa-exclamation-triangle'></i></span>{{ w }}
				</div>
			</div>
		</div>
		<div class='flex-column' style="flex: 1 1 auto"
			 :style="{display: selectionView ? 'none' : 'flex'}" ref="textSelectionContainer">
			<textarea v-model="modelSelectionAsString" spellcheck="false"
					  class="form-control" :class="field.error ? 'border-danger' : ''"
					  style='flex: 1 1 auto; resize: none;'>
			</textarea>
			<div class='mt-2' v-show="textSelectionErrorMsg" v-html="textSelectionErrorMsg"></div>
		</div>
		<!-- GSIM FILTER CONTROLS: -->
		<div :style="{display: selectionView ? 'flex' : 'none'}"
			 class="pt-2 flex-column form-control border-top-0"
			 style='background-color:transparent !important; border-top-left-radius: 0rem!important; border-top-right-radius: 0rem!important;'>
			<div class="d-flex flex-column">
				<div class='mb-1' style='position:relative'>
					<table>
						<tr>
						<td class='text-nowrap'><i class="fa fa-filter"></i> Filter models: </td>
						<td class='text-nowrap ps-3' title="filter models by name. The search will ignore case and spaces">
							<input v-model="filterBy.name"
								   placeholder="by name (case and spaces ignored)"
								   style='min-width:13.5rem;display:inline-block;width:initial'
								   type="text" class="form-control form-control-sm">
						</td>
						<td v-if="imtField" class='text-nowrap ps-3' title='filter models that are defined for the currently selected IMT(s)'>
							<label class='small my-0' :disabled='imtField.disabled'>
								<input v-model="filterBy.imt" type="checkbox" :disabled='imtField.disabled'> by IMTs
							</label>
						</td>
						<td class='text-nowrap ps-3' style='text-align: right;' title='filter models that have been selected for a specific location according to one or more Seismic Hazard Source Regionalizations'>
							<span :style="[!!filterBy.map ? {'visibility': 'hidden'} : {}]" class='small'>
								by region (click on map):
							</span>
						</td>
						</tr>
					</table>
					<button v-if="!!filterBy.map" type='button' class="btn btn-sm btn-outline-dark" @click="clearMapFilter"
							style="position:absolute; right:0; bottom:0">
						Clear map filter
					</button>
				</div>
				<div :id="mapId" ref="mapDiv" style='height:14rem'></div>
		   </div>
		</div>
	</div>`,
	mounted(){
		this.createLeafletMap();
	},
	methods: {
		toggleView(){
			if (this.selectionView){
				var width = `${this.$refs.listSelectionContainer.offsetWidth}px`;
				// to avoid unpleasant resizing, set textarea size if we are about to show it:
				this.$refs.textSelectionContainer.style.width = width;
			}
			this.selectionView=!this.selectionView;
		},
		createLeafletMap(){
			let map = L.map(this.mapId, {center: [48, 7], zoom: 4});
			// center map:
			var mapCenter = L.latLng([49, 13]);
			map.fitBounds(L.latLngBounds([mapCenter, mapCenter]), {maxZoom: 3});
			// setup IntersectionObserver to auto-call invalidateSize on map resize/reshown:
			if (!window.IntersectionObserver){
				// old browser, add a button to call invalidateSize manually
				var Control = L.Control.extend({
					onAdd: function(map) {
						var btn = L.DomUtil.create('button', 'btn btn-secondary btn-sm');
						btn.setAttribute('type', 'button');  // prevent form submit
						var onclick = (evt) => { evt.stopPropagation(); map.invalidateSize(); };
						btn.addEventListener('click', onclick);
						btn.innerHTML = '<i class="fa fa-refresh"></i> Redraw map'
						return btn;
					}
				});
				new Control({ position: 'bottomright' }).addTo(map);
			}else{
				let mapElm = document.getElementById(this.mapId);
				let options = { root: document, threshold: 1.0 };
				let callback = (entries, observer) => {
					setTimeout(() => {
						map.invalidateSize();
					}, 100);
				};
				let observer = new IntersectionObserver(callback, options);
				observer.observe(mapElm);
			}

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
			var regionalization = this.regionalization;
			var control = L.control({position: 'topright'});
			control.onAdd = function (map) {
				var div = L.DomUtil.create('div', 'leaflet-control-layers leaflet-control-layers-expanded leaflet-control');
				// prevent click on anything on the div to propagate on the map:
				L.DomEvent.disableClickPropagation(div);
				// Add title:
				var title = L.DomUtil.create('span', '', div);
				title.innerHTML = '<h6>Regionalization:</h6>';
				for (var [val, name] of regionalization.choices){
					var label = L.DomUtil.create('label', 'd-flex flex-row align-items-baseline', div);
					var input = L.DomUtil.create('input',
												 "leaflet-control-layers-selector",
												 label);
					var span = L.DomUtil.create('span', 'ms-2', label);
					span.innerHTML = name;
					input.setAttribute('type', 'checkbox');
					input.setAttribute('value', val);
					input.checked = regionalization.value.includes(val);
					input.addEventListener('input', function (evt) {
						var val = evt.target.value;
						var idx = regionalization.value.indexOf(val);
						if (idx == -1){
							regionalization.value.push(val);
						}else{
							regionalization.value.splice(idx, 1);
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
				'latitude': latLng[0],
				'longitude': latLng[1],
				'regionalization': this.regionalization.value
			};
			// query data and update filter func:
			EGSIM.post(this.regionalization.url, data).then(response => {  // defined in `vueutil.js`
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
	}
})


/**
 * HTML component representing the form element of IMTs and SA periods
 */
EGSIM.component('imt-select', {
	//https://vuejs.org/v2/guide/components-props.html#Prop-Types:
	props: {
		field: {type: Object},
	},
	data() {
		var fieldCopy = {
			'style': ['border-bottom-left-radius:0rem !important',
					   'border-bottom-right-radius:0rem !important'].join(";")
		};
		if ('size' in this.$attrs){
			fieldCopy['size'] = this.$attrs['size'];
		}
		fieldCopy: Object.assign(fieldCopy, this.field);
		// setup the init values for IMTs in the <select> and SA Periods in the <input>:
		var imts = fieldCopy.value || [];
		fieldCopy.value = Array.from(new Set(imts.map(elm => elm.startsWith('SA(') ? 'SA' : elm)));
		var saPeriods = imts.filter(elm => elm.startsWith('SA(')).map(elm => elm.substring(3, elm.length-1)).join(' ');
		return {
			fieldCopy: fieldCopy,
			SAPeriods: saPeriods
		}
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
	template: `<div class='d-flex flex-column'>
		<field-label :field="fieldCopy" />
		<field-input :field="fieldCopy" style="flex: 1 1 auto" />
		<base-input :value="SAPeriods"
					@value-changed="(value) => {SAPeriods = value;}"
					:disabled="field.disabled || !fieldCopy.value.includes('SA')"
					placeholder="SA periods (space-separated)"
					:style="'border-top: 0 !important;border-top-left-radius: 0rem !important;border-top-right-radius: 0rem !important;'" />
	</div>`,
	methods: {
		updateSelectedImts(){
			this.field.value = this.getSelectedImts();
		},
		getSelectedImts(){
			var imts = Array.from(this.fieldCopy.value);
			if (imts.includes('SA')){
				var saWithPeriods = this.SAPeriods.trim().split(/\s+/).map(p => `SA(${p})`);
				imts = imts.filter(elm => elm!='SA').concat(saWithPeriods);
			}
			return imts;
		}
	}
})