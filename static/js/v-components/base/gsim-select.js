/* GSIM and IMT <select> components */

/* This is an input[type=text] where the v-model is an array. The array elements
will be displayed - and can be edited - on the input space- or comma-separated */
EGSIM.component('array-input', {
	props: {'modelValue': {type: Array}},
	emits: ['update:modelValue'],
	data(){
		return {
			modelValue2str: this.modelValue.join(' ')
		}
	},
	watch: {
		modelValue2str(newVal, oldVal){
			this.$emit('update:modelValue', newVal.trim().split(/\s*,\s*|\s+/))
		}
	},
	template: `<input type='text' placeholder='type values space- or comma-separated'
				class='form-control' v-model="modelValue2str"/>`
});


EGSIM.component('gsim-select', {
	props: {
		models: {type: Array},  // Array of objects with props: name, warning, imts
		selectedModelNames: {type: Array},  // Array of strings
		selectedImts: {type: Array, default: []} // field of IMTs (strings)
	},
	emits: ['gsim-selected'],
	data() {
		return {
			inputElementText: "",
			displayRegex: /[A-Z]+[^A-Z0-9]+|[0-9]+|.+/g  //NOTE safari does not support lookbehind/aheads!
		}
	},
	watch: {
		'selectedModelNames': {
			deep: true,
			handler(newVal, oldVal){
				this.$emit('gsim-selected', newVal)
			}
		},
	},
	computed: {
		selectedModels(){  // Array of Objects with props name, imts, warning
			var selectedModelNamesSet = new Set(this.selectedModelNames);
			return this.models.filter(m => selectedModelNamesSet.has(m.name));
		},
		selectableModels(){
			var models = [];
			var text = this.inputElementText;
			var selectedModelNamesSet = new Set(this.selectedModelNames);
			if (text){
				var regexp = new RegExp(text.replace(/\s+/, '').replace(/([^\w\*\?])/g, '\\$1').replace(/\*/g, '.*').replace(/\?/g, '.'), 'i');
				models = this.models.filter(m => !selectedModelNamesSet.has(m.name) && m.name.search(regexp) > -1);
			}
			// adjust popup height:
			if (models.length){
				setTimeout( () => this.resizeSelectElement(models.length), 50 );
			}
			return models;
		},
		errors(){
			var errors = {};
			var selimts = this.selectedImts.map(i => i.startsWith('SA') ? 'SA' : i);
			for (var model of this.selectedModels){
				var wrongimts = selimts.filter(i => !model.imts.has(i));
				if (wrongimts.length){
					errors[model.name] = `${model.name} does not support ${wrongimts.join(', ')}`;
				}
			}
			return errors;
		},
		warnings(){
			var warnings = {};
			for (var model of this.selectedModels){
				if (model.warning){
					warnings[model.name] = model.warning;
				}
			}
			return warnings;
		}
	},
	template: `<div class='d-flex flex-column'>
		<div class='d-flex flex-row align-items-baseline'>
			<label style="flex: 1 1 auto">model</label>
			<span flex='1 1 auto' class='ms-2 small'>({{ selectedModelNames.length }} of {{ models.length }} selected)</span>
			<i v-show="Object.keys(warnings).length"
			   aria-label="Remove models with warnings (for details, hover mouse on each model icon)"
			   class="fa fa-exclamation-triangle ms-2 text-warning" style="cursor: pointer;"
			   @click="removeSelectedModelsWithWarnings()"></i>
			<i v-show="Object.keys(errors).length"
			   aria-label="Remove models with errors (for details, hover mouse on each model icon)"
			   class="fa fa-exclamation-triangle ms-2 text-danger" style="cursor: pointer;"
			   @click="removeSelectedModelsWithErrors()"></i>
			<i v-show="selectedModelNames.length"
			   aria-label="Clear selection" class="fa fa-times-circle ms-2" style="cursor: pointer;"
			   @click="removeSelectedModels()"></i>
		</div>
		<div style='overflow: auto; flex: 0 1 auto; min-height:0px'
			 :class="selectedModelNames.length ? 'd-flex flex-column form-control mb-2': 'd-none'">
			<div class='d-flex flex-row'>
				<!-- div with cancel icons stacked vertically -->
				<div class='d-flex flex-column'>
					<div v-for="model in selectedModelNames" class='me-1'
						 :class="errors[model] ? 'text-danger' : warnings[model] ? 'text-warning' : ''"
						 aria-label="remove from selection (to remove all models, click the same button on this panel top right corner)"
						 @click="selectedModelNames.splice(selectedModelNames.indexOf(model), 1)">
						<i class='fa fa-times-circle'></i>
					</div>
				</div>
				<!-- div with selected model names stacked vertically -->
				<div class='d-flex flex-column ms-1'>
					<div v-for="model in selectedModelNames"
						 :class="errors[model] ? 'text-danger' : warnings[model] ? 'text-warning' : ''"
						 :aria-label="errors[model] || warnings[model] || ''">{{ model }}</div>
				</div>
				<!-- div with warning icons stacked vertically -->
				<div class='d-flex flex-column ms-1'>
					<span v-for="model in selectedModelNames"
						  :style='{visibility: errors[model] || warnings[model] ? "visible" : "hidden"}'
						  :class="errors[model] ? 'text-danger' : warnings[model] ? 'text-warning' : ''"
						  class='me-1'>
						<i class='fa fa-exclamation-triangle'></i>
					</span>
				</div>
			</div>
		</div>
		<!-- select text and relative popup/div -->
		<input type="text" style='width:30rem'
			   aria-label="Select a model by name (*=match any number of characters, ?=match any 1-length character): matching models will be displayed on a list and can be selected via double click or typing Enter/Return"
			   :placeholder="'Type name (' + models.length + ' models available) or select by region (click on map)'"
			   v-model='inputElementText' ref="inputElement"
			   @keydown.down.prevent="focusSelectElement()"
			   @keydown.esc.prevent="inputElementText=''"
			   class='form-control'>
		<div class='position-relative' style='overflow:visible'>
			<select multiple ref="selectElement"
					v-show='!!selectableModels.length'
					class='border position-absolute shadow'
					style='z-index:10000'
					@dblclick.capture.prevent="selectElementSelected()"
					@keydown.enter.prevent="selectElementSelected()"
					@keydown.up="focusInputElement($event);"
					@keydown.esc.prevent="inputElementText=''">
				<option v-for="m in selectableModels" :value='m.name'>
					{{ m.name.match(displayRegex).join(" ") }}
				</option>
			</select>
		</div>
	</div>`,
	methods: {
		removeSelectedModelsWithWarnings(){
			// this function filters the selectedModelNames Array without creating a new one:
			this.selectedModelNames.splice(0,
				this.selectedModelNames.length,
				...selectedModelNames.filter(m => !this.warnings[m]))
		},
		removeSelectedModelsWithErrors(){
			// this function filters the selectedModelNames Array without creating a new one:
			this.selectedModelNames.splice(0,
				this.selectedModelNames.length,
				...selectedModelNames.filter(m => !this.errors[m]))
		},
		removeSelectedModels(){
			// this function clears the selectedModelNames Array without creating a new one:
			this.selectedModelNames.splice(0, this.selectedModelNames.length)
		},
		focusSelectElement(){
			var sel = this.$refs.selectElement;
			sel.selectedIndex = 0;
			sel.focus();
		},
		selectElementSelected(){
			var sel = this.$refs.selectElement;
			var opts = Array.from(sel.selectedOptions);
			if (!opts.length && sel.selectedIndex > -1){
				opts = [sel.options[sel.selectedIndex]];
			}
			if(!opts.length){
				return;
			}
			this.selectedModelNames.push(...opts.map(opt => opt.value));
			this.$nextTick(() => {
				sel.selectedIndex = -1;
				this.$refs.inputElement.focus();
			});
		},
		resizeSelectElement(optionsLength){
			var rect = this.$refs.inputElement.getBoundingClientRect();
			this.$refs.selectElement.style.width = (rect.right - rect.left) + 'px';
			this.$refs.selectElement.size = optionsLength;
			this.$refs.selectElement.style.maxHeight = (.8 * (document.documentElement.clientHeight - rect.bottom)) + 'px';
		},
		focusInputElement(event){
			if(this.$refs.selectElement.selectedIndex==0){
				this.$refs.selectElement.selectedIndex=-1;
				this.$refs.inputElement.focus();
				event.preventDefault();
			}
		}
	}
});


/**
 * HTML component representing the form element of IMTs and SA periods
 */
EGSIM.component('imt-select', {
	//https://vuejs.org/v2/guide/components-props.html#Prop-Types:
	props: {
		imts: { type: Array },  // without arguments (so 'SA', not 'SA(1.0)')
		selectedImts: { type: Array }  // with or without arguments
	},
	emits: ['imt-selected'],
	data() {
		return {
			selectedImtClassNames: Array.from(new Set(this.selectedImts.map(i => i.startsWith('SA(') ? 'SA' : i))),
			SAPeriods: this.selectedImts.filter(i => i.startsWith('SA(')).map(sa => sa.substring(3, sa.length-1))
		}
	},
	watch: { // https://siongui.github.io/2017/02/03/vuejs-input-change-event/
		selectedImtClassNames: function(newVal, oldVal){
			this.updateSelectedImts();
		},
		SAPeriods: function(newVal, oldVal){
			this.updateSelectedImts();
		},
		selectedImts: {
			deep: true,
			handler(newVal, oldVal){
				this.$emit('imt-selected', newVal)
			}
		}
	},
	template: `<div class='d-flex flex-column'>
		<label>imt</label>
		<select v-model="selectedImtClassNames" multiple  class='form-control'
				style="flex: 1 1 0;min-height: 5rem;border-bottom-left-radius: 0;border-bottom-right-radius: 0;">
			<option	v-for='imt in imts' :value="imt">
				{{ imt }}
			</option>
		</select>
		<array-input v-model="SAPeriods" class='form-control'
				:disabled="!selectedImtClassNames.includes('SA')"
				placeholder="SA periods (space- or comma-separated)"
				:style="'border-top: 0 !important;border-top-left-radius: 0rem !important;border-top-right-radius: 0rem !important;'" />
	</div>`,
	methods: {
		updateSelectedImts(){
			// same as this.selectedImts = getSelectedImts(), but without creating new Array:
			this.selectedImts.splice(0, this.selectedImts.length, ...this.getSelectedImts());
		},
		getSelectedImts(){
			var imts = this.selectedImtClassNames.filter(i => i != 'SA');
			if (imts.length < this.selectedImtClassNames.length){
				// we selected 'SA'. Add periods:
				imts = imts.concat(this.SAPeriods.map(p => `SA(${p})`));
			}
			return imts;
		}
	}
});


/**
 * HTML component representing a map of regionalizations allowing models selection
 */
EGSIM.component('gsim-map', {
	props: {
		regionalizations: {type: Object}
	},
	data(){
		return {map: null};  // leaflet map
	},
	emits: ['gsim-selected'],
	template: `<div ref="mapDiv" style='cursor:pointer'></div>`,
	mounted(){
		this.map = this.createLeafletMap();
		this.mapBoundsChanged();  // update regionalization visibility
	},
	activated(){
		this.map && this.map.invalidateSize();
	},
	methods: {
		createLeafletMap(){
			let map = L.map(this.$refs.mapDiv, {center: [48, 7], zoom: 4});
			// center map:
			var mapCenter = L.latLng([49, 13]);
			map.fitBounds(L.latLngBounds([mapCenter, mapCenter]), {maxZoom: 3});
			map.zoomControl.setPosition('topright');
			// // add a button to call invalidateSize manually
			// var Control = L.Control.extend({
			// 	onAdd: function(map) {
			// 		var btn = L.DomUtil.create('button', 'btn btn-secondary btn-sm');
			// 		btn.setAttribute('type', 'button');  // prevent form submit
			// 		var onclick = (evt) => { evt.stopPropagation(); map.invalidateSize(); };
			// 		btn.addEventListener('click', onclick);
			// 		btn.innerHTML = '<i class="fa fa-refresh"></i> Redraw map'
			// 		return btn;
			// 	}
			// });
			// new Control({ position: 'bottomright' }).addTo(map);

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
					'Map: Geoportail': geoportailLayer,
					'Map: Carto': cartoLayer
				},
				{},
				{
					collapsed: false,
					position: 'topright'
				}
			).addTo(map);  // https://gis.stackexchange.com/a/68243
			this.addRegionalizationControl(map);
			map.on("click", this.mapClicked);
			map.on('zoomend', this.mapBoundsChanged);
			map.on('moveend', this.mapBoundsChanged);
			return map;
		},
		addRegionalizationControl(map){
			var regionalizations = this.regionalizations;
			var control = L.control({position: 'topright'});
			control.onAdd = function (map) {
				var div = L.DomUtil.create('div', 'leaflet-control-layers leaflet-control-layers-expanded leaflet-control');
				// prevent click on anything on the div to propagate on the map:
				L.DomEvent.disableClickPropagation(div);
				// Add title:
				var title = L.DomUtil.create('span', '', div);
				title.innerHTML = '<h6>Regionalization:</h6>';
				for (var name of regionalizations.names){
					// For each regionalization create a <label> wrapping several HTML controls
					// Leaflet syntax is: L.DomUtil.create(tag, classes, parent):
					// Note: display:flex will be set in mapBoundsChanged (see below)
					var label = L.DomUtil.create('label', 'flex-row align-items-baseline', div);
					// add input type=checkbox to label
					var input = L.DomUtil.create('input',
												 "leaflet-control-layers-selector",
												 label);
					input.setAttribute('type', 'checkbox');
					input.setAttribute('data-regionalization-name', name);
					input.setAttribute('checked', true);
					// add span to label (with regionalization name)
					var span = L.DomUtil.create('span', 'ms-2', label);
					span.innerHTML = name;
					// add anchor to label (with ref. URL, if given):
					if (regionalizations.ref[name]){
						var anchor = L.DomUtil.create('a', 'ms-2', label);
						anchor.setAttribute('href', regionalizations.ref[name]);
						anchor.setAttribute('target', "_blank");
						anchor.innerHTML = '<i class="fa fa-link"></i>';
						anchor.setAttribute('title', 'see ref (open link in new tab)');
					}
				}
				return div;
			};
			control.addTo(map);
		},
		isRegionalizationSelected(regionalizationName){
			var elm = this.getRegionalizationInput(regionalizationName);
			return elm && elm.parentNode.style.display!='none' && elm.checked;
		},
		getRegionalizationInput(regionalizationName){
			return this.$refs.mapDiv.querySelector(`input[data-regionalization-name='${regionalizationName}']`);
		},
		mapBoundsChanged(event){
			var mapLeafletBounds = this.map.getBounds();
			var southWest = mapLeafletBounds.getSouthWest().wrap();
			var northEast = mapLeafletBounds.getNorthEast().wrap();
			// define bounding check functions:
			function outOfBoundsLat(minLat, maxLat){
				return maxLat < southWest.lat || minLat > northEast.lat;
			}
			if (southWest.lng <= northEast.lng){
				function outOfBoundsLng(minLng, maxLng){
					return maxLng < southWest.lng || minLng > northEast.lng;
				}
			}else{
				// we have the antimeridian (mid pacific) in the map. This means southWest
				// is greater than northEast (usually should be the other way around)
				function outOfBoundsLng(minLng, maxLng){
					return maxLng < southWest.lng && minLng > northEast.lng;
				}
			}
			for (var name of this.regionalizations.names){
				var regBounds = this.regionalizations.bbox[name];  // (minLng, minLat, maxLng, maxLat)
				var outOfBounds = outOfBoundsLng(regBounds[0], regBounds[2]) || outOfBoundsLat(regBounds[1], regBounds[3]);
				this.getRegionalizationInput(name).parentNode.style.display = outOfBounds ? 'none' : 'flex';
			}
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
				'regionalization': this.regionalizations.names.filter(name => this.isRegionalizationSelected(name))
			};
			// query data and update filter func:
			fetch(this.regionalizations.url, data).then(response => {
				this.$emit('gsim-selected', response.data.models || [])
			});
		},
		removeMarkersFromMap(){
			this.map.eachLayer(function (layer) {
				if (layer instanceof L.Marker){
					layer.remove();
				}
			});
		}
	}
})