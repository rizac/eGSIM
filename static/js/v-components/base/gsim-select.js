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
	created(){
		this.regionalization = this.field['data-regionalization'] || {};
	},
	computed: {
		infoMsg(){
			return `${this.field.value.length || 0} of ${this.field.choices.length} selected`;
		},
		selectableModels(){
			var text = this.modeltext;
			if (!text){
				return [];
			}
			var regexp = new RegExp(text.replace(/\s+/, '').replace(/([^\w\*\?])/g, '\\$1').replace(/\*/g, '.*').replace(/\?/g, '.'), 'i');
			// filterFuncs.push(gsim => gsim.value.search(regexp) > -1);
			var selectedModelNames = new Set(this.field.value);
			return this.field.choices.filter(m => !selectedModelNames.has(m.value) && m.value.search(regexp) > -1);
		},
		modelHTMLAttrs(){
			var attrs = {};
			var selected = new Set(this.field.value);
			var selimts = Array.from(this.imtField ? new Set(this.imtField.value.map(elm => elm.startsWith('SA') ? 'SA' : elm)) : []);
			for (var model of this.field.choices.filter(m => selected.has(m.value))){
				var ws = [];
				var critical = false;
				if (selimts.length){
					var wrongimts = selimts.filter(i => !model.imts.includes(i));
					if (wrongimts.length){
						critical = true;
						ws.push(`${model.value} does not support ${wrongimts.join(', ')}`);
					}
				}
				if (model.warning){
					ws.push(model.warning);
				}
				attrs[model.value] = !ws.length ? {} : {
					class: critical ? 'text-danger' : 'text-warning',
					'title': ws.join('\n')
				};
			}
			return attrs;
		}
	},
	template: `<div class='d-flex flex-column' style='flex: 1 1 auto'>
		<field-label :field="field">
			<template v-slot:trailing-content>
				<span v-if="!field.error" class='ms-2 small text-muted' v-html="infoMsg"></span>
				<i v-if="field.value.length && !field.error"
				   @click="field.value=[]" class="fa fa-times-circle ms-2"
				   style="cursor: pointer;" title="Clear selection"></i>
			</template>
		</field-label>
		<div class='d-flex flex-column form-control' style="flex: 1 1 auto" :class="field.error ? 'border-danger' : ''" :style='{width: .75*Math.max(...field.choices.map(m => m.value.length)) + "rem"}'>
			<div class='d-flex flex-row' style='overflow: auto;max-height:20rem'>
				<div class='d-flex flex-column'>
					<div v-for="model in field.value" class='me-1' title="remove from selection" @click="this.field.value.splice(this.field.value.indexOf(model), 1)">
							<i class='fa fa-times-circle'></i>
					</div>
				</div>
				<div class='d-flex flex-column' style='flex: 1 1 auto'>
					<div v-for="model in field.value" v-bind="modelHTMLAttrs[model]">{{ model }}</div>
				</div>
				<div class='d-flex flex-column'>
					<span v-for="model in field.value" style='{visibility: Object.keys(modelHTMLAttrs[model]).length ? "visible" : "hidden"}'
						  v-bind="modelHTMLAttrs[model]" class='me-1'>
						<i class='fa fa-exclamation-triangle'></i>
					</span>
				</div>
			</div>
			<div v-show="!!field.value.length" class='mb-1 mt-1 border-top'></div>
			<div class='mt-1 d-flex flex-row align-items-baseline'>
				<input type="text" placeholder="Select by name" v-model='modeltext' class="form-control me-2" ref="modelText"
					   @keydown.down.prevent="focusSelectComponent()">
				<div style='flex: 1 1 auto'></div>
				<div class='text-nowrap'>Select by region (click on map):</div>
			</div>
			<div class='mt-1 d-flex flex-column position-relative' style='flex: 1 1 auto;min-height:15rem'>
				<select v-show='!!selectableModels.length' multiple class='form-control shadow rounded-0 border-0' ref="modelSelect"
						@click.capture.prevent="fetchSelectComponentModels()"
						@keydown.enter.prevent="fetchSelectComponentModels()"
						@keydown.up="if($refs.modelSelect.selectedIndex==0){ $refs.modelSelect.selectedIndex=-1; $refs.modelText.focus(); $evt.preventDefault();}"
						style='position:absolute;left:0;top:0;bottom:0;right:0;z-index:10000' >
					<option v-for="m in selectableModels" :value='m.value'>
						{{ m.innerHTML }}
					</option>
				</select>
				<div ref="mapDiv" style='flex: 1 1 auto;'></div>
			</div>
		</div>
	</div>`,
	mounted(){
		this.createLeafletMap();
	},
	methods: {
		focusSelectComponent(){
			if (!!this.selectableModels.length){
				var sel = this.$refs.modelSelect;
				sel.selectedIndex = 0;
				sel.focus();
			}
		},
		focusSelectComponent(){
			if (!!this.selectableModels.length){
				var sel = this.$refs.modelSelect;
				sel.selectedIndex = 0;
				sel.focus();
			}
		},
		focusSelectComponent(){
			if (!!this.selectableModels.length){
				var sel = this.$refs.modelSelect;
				sel.selectedIndex = 0;
				sel.focus();
			}
		},
		fetchSelectComponentModels(){
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
				this.$refs.modelText.focus();
			});
		},
		createLeafletMap(){
			var mapDiv = this.$refs.mapDiv;
			let map = L.map(mapDiv, {center: [48, 7], zoom: 4});
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
				let options = { root: document, threshold: 1.0 };
				let callback = (entries, observer) => {
					setTimeout(() => {
						map.invalidateSize();
					}, 100);
				};
				let observer = new IntersectionObserver(callback, options);
				observer.observe(mapDiv);
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
			axios.post(this.regionalization.url, data).then(response => {
				// response.data is an Array of gsim names
				var selectedModels = new Set(this.field.value || []);
				var gsims = (response.data || []).filter(m => !selectedModels.has(m));
				this.field.value.push(...gsims);
			});
		},
		removeMarkersFromMap(){
			this.map.eachLayer(function (layer) {
				if (layer instanceof L.Marker){
					layer.remove();
				}
			});
		},
		/*updateWarnings(){
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
		},*/
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