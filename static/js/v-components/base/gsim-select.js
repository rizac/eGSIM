/* GSIM and IMT <select> components */

EGSIM.component('gsim-select', {
	props: {
		field: {type: Object}, // see field-input
		imtField: {type: Object, default: null} // field of IMTs (can be null)
	},
	emits: ['gsim-selected'],
	data() {
		return {
			modeltext: ""
		}
	},
	watch: {
		'field.value': {
			deep: true,
			handler(newVal, oldVal){
				this.$emit('gsim-selected', newVal)
			}
		},
	},
	computed: {
		infoMsg(){
			return `${this.field.value.length || 0} of ${this.field.choices.length} selected`;
		},
		selectableModels(){
			var models = [];
			var text = this.modeltext;
			if (text){
				var regexp = new RegExp(text.replace(/\s+/, '').replace(/([^\w\*\?])/g, '\\$1').replace(/\*/g, '.*').replace(/\?/g, '.'), 'i');
				var selectedModelNames = new Set(this.field.value);
				models = this.field.choices.filter(m => !selectedModelNames.has(m.value) && m.value.search(regexp) > -1);
			}
			return models;
		},
		errors(){  // remember: props are cached https://vuejs.org/guide/essentials/computed.html#computed-caching-vs-methods
			var errors = {};
			var selected = new Set(this.field.value);
			var selimts = Array.from(this.imtField ? new Set(this.imtField.value.map(elm => elm.startsWith('SA') ? 'SA' : elm)) : []);
			for (var model of this.field.choices.filter(m => selected.has(m.value))){
				var wrongimts = selimts.filter(i => !model.imts.includes(i));
				if (wrongimts.length){
					errors[model.value] = `${model.value} does not support ${wrongimts.join(', ')}`;
				}
			}
			return errors;
		},
		warnings(){  // remember: props are cached https://vuejs.org/guide/essentials/computed.html#computed-caching-vs-methods
			var warnings = {};
			var selected = new Set(this.field.value);
			for (var model of this.field.choices.filter(m => selected.has(m.value))){
				if (model.warning){
					warnings[model.value] = model.warning || "";
				}
			}
			return warnings;
		}
	},
	template: `<div class='d-flex flex-column'>
		<field-label :field="field">
			<template v-slot:trailing-content>
				<span v-if="!field.error" class='ms-2 small text-muted' v-html="infoMsg"></span>
				<i v-show="Object.keys(warnings).length"
				   aria-label="Remove models with warnings (for details, hover mouse on the list below)"
				   class="fa fa-exclamation-triangle ms-2 text-warning" style="cursor: pointer;"
				   @click="field.value=field.value.filter(m => !warnings[m])"></i>
				<i v-show="Object.keys(errors).length"
				   aria-label="Remove models with errors (for details, hover mouse on the list below)"
				   class="fa fa-exclamation-triangle ms-2 text-danger" style="cursor: pointer;"
				   @click="field.value=field.value.filter(m => !errors[m])"></i>
				<i v-show="field.value.length && !field.error"
				   aria-label="Clear selection" class="fa fa-times-circle ms-2" style="cursor: pointer;"
				   @click="field.value=[]" ></i>
			</template>
		</field-label>
		<div class='d-flex flex-column' style="flex: 0 1 auto;">
			<div class='d-flex flex-column' style='flex: 0 1 auto'
				 :class="field.error ? 'border-danger' : ''">
				<div class='d-flex flex-row' style='overflow: auto; flex: 0 1 auto'
					 :style="{minHeight: field.value.length ? '3rem' : '0px' }"
					 :class="field.value.length ? 'form-control mb-2': ''">
					<!-- div with cancel icons stacked vertically -->
					<div class='d-flex flex-column'>
						<div v-for="model in field.value" class='me-1'
							 :class="errors[model] ? 'text-danger' : warnings[model] ? 'text-warning' : ''"
							 aria-label="remove from selection (to remove all models, click the same button on this panel top right corner)"
							 @click="this.field.value.splice(this.field.value.indexOf(model), 1)">
							<i class='fa fa-times-circle'></i>
						</div>
					</div>
					<!-- div with selected model names stacked vertically -->
					<div class='d-flex flex-column' style='flex: 1 1 auto'>
						<div v-for="model in field.value"
							 :class="errors[model] ? 'text-danger' : warnings[model] ? 'text-warning' : ''"
							 :aria-label="errors[model] || warnings[model] || ''">{{ model }}</div>
					</div>
					<!-- div with warning icons stacked vertically -->
					<div class='d-flex flex-column'>
						<span v-for="model in field.value"
							  :style='{visibility: errors[model] || warnings[model] ? "visible" : "hidden"}'
							  :class="errors[model] ? 'text-danger' : warnings[model] ? 'text-warning' : ''"
							  class='me-1'>
							<i class='fa fa-exclamation-triangle'></i>
						</span>
					</div>
				</div>
				<!-- select text and relative popup/div -->
				<input type="text" style='flex: 1 1 auto; width:30rem'
					   aria-label="Select a model by name (*=match any number of characters, ?=match any 1-length character): matching models will be displayed on a list and can be selected via double click or typing Enter/Return"
					   :placeholder="'Type model name (' + field.choices.length + ' available) or select by region (click on map)'"
					   v-model='modeltext' ref="modelTextControl"
					   @keydown.down.prevent="focusSelectComponent()"
					   @keydown.esc.prevent="modeltext=''"
					   class='form-control'
					   :style='selectableModels.length ? "border-bottom-left-radius:0rem !important;border-bottom-right-radius:0rem !important" : ""'>
				<select v-show='!!selectableModels.length' multiple ref="modelSelect"
						class='form-control'
						style='flex: 1 1 auto;border-top-left-radius:0rem !important;border-top-right-radius:0rem !important'
						@dblclick.capture.prevent="addSelectedOptionComponentValuesToModelSelection()"
						@keydown.enter.prevent="addSelectedOptionComponentValuesToModelSelection()"
						@keydown.up="focusTextInput($event);"
						@keydown.esc.prevent="modeltext=''">
					<option v-for="m in selectableModels" :value='m.value'>
						{{ m.innerHTML }}
					</option>
				</select>
			</div>
		</div>
	</div>`,
	methods: {
		focusSelectComponent(){
			if (!!this.selectableModels.length){
				var sel = this.$refs.modelSelect;
				sel.selectedIndex = 0;
				sel.focus();
			}
		},
		addSelectedOptionComponentValuesToModelSelection(){
			var sel = this.$refs.modelSelect;
			var opts = Array.from(sel.selectedOptions);
			if (!opts.length && sel.selectedIndex > -1){
				elms = [sel.options[sel.selectedIndex]];
			}
			if(!opts.length){
				return;
			}
			this.field.value.push(...opts.map(opt => opt.value));
			this.$nextTick(() => {
				sel.selectedIndex = -1;
				this.$refs.modelTextControl.focus();
			});
		},
		focusTextInput(event){
			if(this.$refs.modelSelect.selectedIndex==0){
				this.$refs.modelSelect.selectedIndex=-1;
				this.$refs.modelTextControl.focus();
				event.preventDefault();
			}
		}
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
	emits: ['imt-selected'],
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
		},
		'field.value': {
			deep: true,
			handler(newVal, oldVal){
				this.$emit('imt-selected', newVal)
			}
		}
	},
	template: `<div class='d-flex flex-column'>
		<field-label :field="fieldCopy" />
		<field-input :field="fieldCopy" style="flex: 1 1 0;min-height: 5rem" />
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
				var saWithPeriods = this.SAPeriods.trim().split(/\s*,\s*|\s+/).map(p => `SA(${p})`);
				imts = imts.filter(elm => elm!='SA').concat(saWithPeriods);
			}
			return imts;
		}
	}
})


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
			axios.post(this.regionalizations.url, data).then(response => {
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