/* This is an input[type=text] where the v-model is an array represented on the
input as space space separated list (comma is also allowed)
*/
EGSIM.component('array-input', {
	// modelValue is the value of v-model set on this array-input:
	props: {
		'modelValue': { type: Array },
		'placeholder': { type: String, default: "type values comma- or space-separated"}
	},
	emits: ['update:modelValue'],
	data(){
		return { modelValue2str: null }  // string (null: uninitialized)
	},
	watch: {
		modelValue: {
			immediate: true,
			deep: true,
			handler(newVal, oldVal) {
				if (newVal === undefined){ newVal = []; }
				if (this.modelValueChanged(newVal)){
					this.modelValue2str = newVal.join(' ');
				}
			}
		},
		modelValue2str(newVal, oldVal){
			// emit a v-model update on this component, after converting back the internal string to an Array:
			this.$emit('update:modelValue', this.string2Array(newVal));
		}
	},
	template: `<input type='text' v-model="modelValue2str" :placeholder='placeholder' />`,
	methods: {
		string2Array(stringValue){
			return stringValue.trim() ? stringValue.trim().split(/\s*,\s*|\s+/) : [];  // https://stackoverflow.com/a/5164901
		},
		modelValueChanged(newArray){
			if (this.modelValue2str !== null){
				var oldArray = this.string2Array(this.modelValue2str);
				if (oldArray.length === newArray.length &&
						oldArray.every((e,i) => e === newArray[i])){
					return false;
				}
			}
			return true;
		}
	}
});


EGSIM.component('gsim-select', {
	props: {
		modelValue: {type: Array},  // [NOTE: VUE model] Array of selected ground motion model names
		models: {type: Array},  // [Note: Ground Motion models] Array of available models. Each model is an objects with keys: name, warning, imts
		selectedImts: {type: Array, default: []} // field of selected IMTs (strings)
	},
	emits: ['update:modelValue'],
	data() {
		return {
			inputElementText: "",
			displayRegex: /[A-Z]+[^A-Z0-9]+|[0-9_]+|.+/g  //NOTE safari does not support lookbehind/aheads!
		}
	},
	computed: {
		selectedModels: {
			get() {
				return this.modelValue;
			},
			set(value) {
				this.$emit('update:modelValue', value);
			}
		},
		selectableModels(){
			var models = [];
			var text = this.inputElementText.trim();
			if (text){
				var selectedModelsSet = new Set(this.selectedModels);
				var regexp = new RegExp(text.replace(/\s+/, '').replace(/([^\w\*\?])/g, '\\$1').replace(/\*/g, '.*').replace(/\?/g, '.'), 'i');
				models = this.models.filter(m => !selectedModelsSet.has(m.name) && m.name.search(regexp) > -1);
				// adjust popup height:
				if (models.length){
					setTimeout( () => this.resizeHTMLSelectElement(models.length), 20 );
				}
			}
			return models;
		},
		errors(){
			var errors = {};
			var selimts = this.selectedImts.map(i => i.startsWith('SA') ? 'SA' : i);
			var selectedModelsSet = new Set(this.selectedModels);
			for (var model of this.models.filter(m => selectedModelsSet.has(m.name))){
				var wrongimts = selimts.filter(i => !model.imts.has(i));
				if (wrongimts.length){
					errors[model.name] = [`${model.name} does not support ${wrongimts.join(', ')}`];
				}
			}
			return errors;
		},
		warnings(){
			var warnings = {};
			var saPeriods = this.selectedImts.filter(e => e.startsWith('SA(')).map(e => e.substring(3, e.length-1));
			var saLimits = saPeriods.length ? [Math.min(...saPeriods), Math.max(...saPeriods)] : [];
			var selectedModelsSet = new Set(this.selectedModels);
			for (var model of this.models.filter(m => selectedModelsSet.has(m.name))){
				var warns = [];
				if (model.warning){
					warns.push(model.warning);
				}
				if (saLimits.length){
					if (saPeriods.some(p => (p < model.saLimits[0] || p > model.saLimits[1]))){
						warns.push("Not defined for all supplied SA periods");
					}
				}
				if (warns.length){
					warnings[model.name] = warns;
				}
			}
			return warnings;
		}
	},
	template: `<div class='d-flex flex-column form-control' title="Ground motion model(s)">
		<div
			class='d-flex flex-row align-items-baseline mb-2'
			style='border-bottom:0 !important;border-bottom-left-radius:0 !important; border-bottom-right-radius:0 !important'>
			<span style="flex: 1 1 auto;" class='text-start'>Model ({{ selectedModels.length }} selected)</span>
			<span v-show='inputElementText' class='text-muted small'> [ESC]: clear text and hide popup</span>
			<i
				v-show="Object.keys(warnings).length && !inputElementText"
				title="Remove models with warnings (for details, hover mouse on each model icon)"
				class="fa fa-exclamation-triangle ms-2 text-warning"
				style="cursor: pointer;"
				@click="removeSelectedModelsWithWarnings()">
			</i>
			<i
				v-show="Object.keys(errors).length && !inputElementText"
				title="Remove models with errors (for details, hover mouse on each model icon)"
				class="fa fa-exclamation-triangle ms-2 text-danger"
				style="cursor: pointer;"
				@click="removeSelectedModelsWithErrors()">
			</i>
			<i
				v-show="selectedModels.length && !inputElementText"
				title="Remove all models from selection"
				class="fa fa-times-circle ms-2"
				style="cursor: pointer;"
				@click="removeSelectedModels()">
			</i>
		</div>
		<div style='overflow: auto; flex: 1 1 auto'
			class='rounded-bottom-0 flex-column form-control'
			:class="selectedModels.length ? 'd-flex': 'd-none'">
			<div class='d-flex flex-row'>
				<!-- div with cancel icons stacked vertically -->
				<div class='d-flex flex-column'>
					<div
						v-for="model in selectedModels"
						class='me-1'
						:class="errors[model] ? 'text-danger' : warnings[model] ? 'text-warning' : ''"
						title="Remove from selection"
						@click="selectedModels.splice(selectedModels.indexOf(model), 1)">
						<i class='fa fa-times-circle'></i>
					</div>
				</div>
				<!-- div with selected model names stacked vertically -->
				<div class='d-flex flex-column ms-1'>
					<div
						v-for="model in selectedModels"
						:title="(errors[model] || []).concat(warnings[model] || []).join('<br>')"
						:class="errors[model] ? 'text-danger' : warnings[model] ? 'text-warning' : ''"
						>
						{{ model }}
					</div>
				</div>
				<!-- div with warning icons stacked vertically -->
				<div class='d-flex flex-column ms-1'>
					<span
						v-for="model in selectedModels"
						:title="(errors[model] || []).concat(warnings[model] || []).join('<br>')"
						:style='{visibility: errors[model] || warnings[model] ? "visible" : "hidden"}'
						:class="errors[model] ? 'text-danger' : warnings[model] ? 'text-warning' : ''"
						class='me-1'>
						<i class='fa fa-exclamation-triangle'></i>
					</span>
				</div>
			</div>
		</div>
		<!-- select text and relative popup/div -->
		<input
			type="text"
			v-model='inputElementText' ref="inputElement"
			@keydown.down.prevent="focusHTMLSelectElement()"
			@keydown.esc.prevent="inputElementText=''"
			class='form-control'
			:class="selectedModels.length ? 'rounded-top-0 border-top-0' : ''"
			:placeholder="'Type name (' + models.length + ' models available) or select by region (click on map)'" />
		<div
			class='position-relative'
			style='overflow:visible'>
			<select
				title="Highlight models: Click or [&uarr;][&darr;] (with [Shift] or [Ctrl]: multi highlight)\nSelect highlighted models: Double click, [Return] or [Enter]\nClear text and hide popup: [ESC]"
				multiple
				ref="selectElement"
				v-show='!!selectableModels.length'
				class='border position-absolute shadow'
				style='z-index:10000; outline: 0px !important;'
				@dblclick.prevent="addModelsToSelection( Array.from($refs.selectElement.selectedOptions).map(o => o.value) )"
				@keydown.enter.prevent="addModelsToSelection( Array.from($refs.selectElement.selectedOptions).map(o => o.value) )"
				@keydown.up="$evt => { if( $refs.selectElement.selectedIndex == 0 ){ focusHTMLInputElement(); $evt.preventDefault(); } }"
				@keydown.esc.prevent="inputElementText=''">
				<option
					v-for="m in selectableModels"
					:value='m.name'>
					{{ m.name.match(displayRegex).join(" ") }}
				</option>
			</select>
		</div>
	</div>`,
	methods: {
		removeSelectedModelsWithWarnings(){
			// this function filters the selectedModels Array without creating a new one:
			this.selectedModels.splice(0,
				this.selectedModels.length,
				...this.selectedModels.filter(m => !this.warnings[m]))
		},
		removeSelectedModelsWithErrors(){
			// this function filters the selectedModels Array without creating a new one:
			this.selectedModels.splice(0,
				this.selectedModels.length,
				...this.selectedModels.filter(m => !this.errors[m]))
		},
		removeSelectedModels(){
			// this function clears the selectedModels Array without creating a new one:
			this.selectedModels.splice(0, this.selectedModels.length)
		},
		focusHTMLSelectElement(){
			var sel = this.$refs.selectElement;
			sel.selectedIndex = 0;
			sel.focus();
		},
		focusHTMLInputElement(){
			this.$refs.selectElement.selectedIndex=-1;
			this.$refs.inputElement.focus();
		},
		addModelsToSelection(modelNames){
			if (!modelNames){
				return;
			}
			this.selectedModels.push(...modelNames);
			this.$nextTick(() => {
				this.inputElementText = "";
				this.focusHTMLInputElement();
			});
		},
		resizeHTMLSelectElement(optionsLength){
			var rect = this.$refs.inputElement.getBoundingClientRect();
			this.$refs.selectElement.style.width = (rect.right - rect.left) + 'px';
			this.$refs.selectElement.size = optionsLength;
			this.$refs.selectElement.style.maxHeight = (.95 * (document.documentElement.clientHeight - rect.bottom)) + 'px';
		}
	}
});


/**
 * HTML component representing the form element of IMTs and SA periods
 */
EGSIM.component('imt-select', {
	//https://vuejs.org/v2/guide/components-props.html#Prop-Types:
	props: {
		modelValue: { type: Array },  // [Vue model] Array of IMT names, with or without arguments
		imts: { type: Array }  // without arguments (so 'SA', not 'SA(1.0)')
	},
	emits: ['update:modelValue'],
	data() {
		var selectedImtClassNames = Array.from(new Set(this.modelValue.map(i => i.startsWith('SA(') ? 'SA' : i)));
		var SAPeriods = this.modelValue.filter(i => i.startsWith('SA(')).map(sa => sa.substring(3, sa.length-1));
		return {
			selectedImtClassNames: selectedImtClassNames,
			SAPeriods: SAPeriods,
			defaultSAPeriods: [0.05, 0.075, 0.1, 0.11, 0.12, 0.13, 0.14, 0.15, 0.16, 0.17, 0.18, 0.19, 0.20,
				0.22, 0.24, 0.26, 0.28, 0.30, 0.32, 0.34, 0.36, 0.38, 0.40, 0.42, 0.44, 0.46, 0.48, 0.5, 0.55,
				0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8,
				1.9, 2.0, 3.0, 4.0, 5.0, 7.5, 10.0]
		}
	},
	computed: {
		selectedImts: {
			get(){
				return this.modelValue;
			},
			set(value) {
				this.$emit('update:modelValue', value);
			}
		}
	},
	watch: { // https://siongui.github.io/2017/02/03/vuejs-input-change-event/
		selectedImtClassNames: function(newVal, oldVal){
			this.updateSelectedImts();
		},
		SAPeriods: {
			deep: true,
			handler(newVal, oldVal){
				this.updateSelectedImts();
			}
		}
	},
	template: `<div class='d-flex flex-column form-control'
		title="Intensity measure type(s)">
		<span class='mb-2'>Imt ({{ selectedImts.length }} selected)</span>
		<select
			v-model="selectedImtClassNames"
			multiple
			class='form-control rounded-bottom-0'
			:class="selectedImtClassNames.includes('SA') ? '' : 'rounded-bottom'"
			style="flex: 1 1 auto;">
			<option	v-for='imt in imts' :value="imt">
				{{ imt }}
			</option>
		</select>
		<div v-show="selectedImtClassNames.includes('SA')" class='d-flex flex-row'>
			<array-input
				v-model="SAPeriods"
				class='form-control border-top-0 rounded-top-0 rounded-end-0 border-end-0'
				placeholder="SA periods (space- or comma-separated)"
			 />
			<button
				@click="SAPeriods = Array.from(SAPeriods.length ? [] : defaultSAPeriods)"
				type='button'
				:title='SAPeriods.length ? "clear text" : "input a predefined list of SA periods"'
				class='btn border-0 bg-white rounded-top-0 rounded-start-0 border-bottom border-end'>
				<i class="fa fa-times-circle"
					:class='SAPeriods.length ? "fa-times-circle" : "fa-arrow-circle-o-left"'></i>
			</button>
		</div>
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
		regionalizations: {type: Array},  // Array of Objects with keys name, bbox, url
		regionSelectedUrl: {type: String}
	},
	data(){
		return {map: null};  // leaflet map
	},
	emits: ['gsim-selected', 'gsim-unselected'],
	template: `<div ref="mapDiv" style='cursor:pointer'></div>`,
	mounted(){
		if (this.map === null){
			this.map = this.createLeafletMap();
			this.mapBoundsChanged();  // update regionalization visibility
		}
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
			this.addMapControl(map);
			map.on("click", this.mapClicked);
			map.on('zoomend', this.mapBoundsChanged);
			map.on('moveend', this.mapBoundsChanged);
			return map;
		},
		addMapControl(map){
			var regionalizations = this.regionalizations;
			var control = L.control({position: 'topright'});
			control.onAdd = function (map) {
				var div = document.createElement('div');
				div.className = 'leaflet-control-layers leaflet-control p-2';
				var rowDivPrefix = "<div class='d-flex flex-row align-items-center text-nowrap'>";
				// prevent click on anything on the div to propagate on the map:
				L.DomEvent.disableClickPropagation(div);
				var html = `<button class="border-0" type="button"
								onclick='this.parentNode.querySelector("._panel").classList.toggle("d-none");this.querySelectorAll("._arrow").forEach(e => e.classList.toggle("d-none"))'
								style='width:100%; background-color:transparent'>
								<span class='_arrow'>&#9207;</span>
								<span class="_arrow d-none">&#9206;</span>
							</button>
							<div class='_panel d-none'>`;
				// Add title:
				html += `<h6 class="mt-1">Map options</h6>
					<div style='max-width:12rem' class='mb-2'>On mouse click, querying the models
					selected in the following seismic hazard
					source regionalizations:
					</div>`;
				for (var regx of regionalizations){
					var name = regx.name;
					var ipt = `<label><input type='checkbox' data-regionalization-name='${name}' checked class='me-1' />${name}</label>`;
					if (regx.url){
						ipt += `<a class='ms-1' target="_blank" href="${regx.url}" title="ref (open link in new tab)">
							<i class="fa fa-external-link"></i>
						</a>`;
					}
					html += `${rowDivPrefix}${ipt}</div>`;
				}

				// add layers (to change default layer, see below at the end):
				var layers = {
					'Geoportail': L.tileLayer('https://wxs.ign.fr/{apikey}/geoportail/wmts?REQUEST=GetTile&SERVICE=WMTS&VERSION=1.0.0&STYLE={style}&TILEMATRIXSET=PM&FORMAT={format}&LAYER=ORTHOIMAGERY.ORTHOPHOTOS&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}', {
						attribution: '<a target="_blank" href="https://www.geoportail.gouv.fr/">Geoportail France</a>',
						bounds: [[-75, -180], [81, 180]],
						minZoom: 2,
						maxZoom: 19,
						apikey: 'choisirgeoportail',
						format: 'image/jpeg',
						style: 'normal'
					}),
					// 2 CartoDB gray scale map (very good with overlays, as in our case)
					// the added base layer added is set selected by default (do not add the others then)
					'Carto': L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
						attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
						subdomains: 'abcd',
						maxZoom: 19
					})
				};
				html += '<h6 class="mt-3">Base layer</h6>';
				for (var name of Object.keys(layers)){
					html += `${rowDivPrefix}
						<label><input type='radio' name='__gm_map_layer__' data-map-layer='${name}' class='me-1' />${name}</label>
					</div>`;
				}

				div.innerHTML = `${html}</div></div>`;
				// add events:
				function addLayer(name){
					map.eachLayer((layer) => {
						if (!(layer instanceof L.Marker)){
							layer.remove();
						}
					});
					layers[name].addTo(map);
				}
				div.querySelectorAll('input[data-map-layer]').forEach(elm => {
					elm.addEventListener('click', e => { addLayer(e.target.getAttribute('data-map-layer')); });
				});
				// default Layer (click on the associated HTML element to set it):
				var defaultLayerName = "Carto";
				div.querySelector(`input[data-map-layer="${defaultLayerName}"]`).click();
				return div;
			};
			control.addTo(map);
		},
		isRegionalizationSelected(regionalizationName){
			var elm = this.getRegionalizationInput(regionalizationName);
			return elm && elm.parentNode.style.display!='none' && elm.checked;
		},
		getRegionalizationInput(regionalizationName){
			if (!this.$refs.mapDiv){  // prevent weird log errors  "this.$refs.mapDiv is undefined"
				return null;
			}
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
			for (var regx of this.regionalizations){
				var regBounds = regx.bbox;  // (minLng, minLat, maxLng, maxLat)
				var outOfBounds = outOfBoundsLng(regBounds[0], regBounds[2]) || outOfBoundsLat(regBounds[1], regBounds[3]);
				var elm = this.getRegionalizationInput(regx.name);
				if (elm){
					elm.parentNode.style.display = outOfBounds ? 'none' : 'flex';
				}
			}
		},
		mapClicked(event) {
			var latLng = [event.latlng.lat, event.latlng.lng];
			// Destroy existing markers marker (or move existing one):
			this.map.eachLayer((layer) => { if (layer instanceof L.Marker){ layer.remove(); }});
			// ad new marker:
			var marker = L.marker(latLng).addTo(this.map);
			// query data:
			var data = {
				'latitude': latLng[0],
				'longitude': latLng[1],
				'regionalization': this.regionalizations.map(r => r.name).
					filter(name => this.isRegionalizationSelected(name))
			};
			// query data and update filter func:
			fetch(this.regionSelectedUrl, {
				method: "POST",
				headers: {
					"Content-Type": "application/json",
				},
				body: JSON.stringify(data),
			}).then(response => {
				return response.json();
			}).then(json_data => {
				let models = json_data.models;
				if (models.length){
					this.$emit('gsim-selected', models);
					marker.on('click', e => {
						this.$emit('gsim-unselected', models);
						marker.remove();
					});
				}
			});
		}
	}
})

EGSIM.component('flatfile-select', {
	props: {
		flatfiles: {type: Array},  // Array of Objet with keys value (str or File), key, innerHTML, url, columns
		modelValue: {type: [String, File], default: null},
		flatfileQuery: {type: String},
		uploadUrl: {type: String}
	},
	data(){
		return { selectedIndex: -1 };
	},
	emits: ['update:modelValue'],
	watch: {
		selectedIndex:{
			handler(newVal, oldVal){
				var selectedFlatfile = newVal !== undefined && newVal >= 0 ? this.flatfiles[newVal].value : null;
				this.$emit('update:modelValue', selectedFlatfile);
			}
		},
		modelValue: {
			deep: true,
			immediate: true,
			handler(newVal, oldVal){
				if (newVal instanceof File){
					newVal = newVal.name;
				}
				this.selectedIndex = this.flatfiles.map(f => f.name).indexOf(newVal);
			}
		}
	},
	methods:{
		uploadFlatfiles(files){
			var choices = this.flatfiles;
			var self = this;
			for(var index = 0; index < files.length; index++){
				var file = files[index];
				var label = `${file.name} (${new Date().toLocaleString()})`;
				var append = true;
				for (let choice of choices){
					if (choice.value instanceof File && choice.name == file.name){
						this.upload(file).then(data => {
							choice.value = file;
							choice.innerHTML = label;  // update label on <select>
							choice.columns = data.columns;
							self.selectedIndex = index;
						});
						append = false;
						break;
					}
				}
				if (append){
					this.upload(file).then(data => {
						var cols = data.columns;
						choices.push({ name: file.name, value: file, innerHTML: label, columns: cols });
						self.selectedIndex = choices.length - 1;
					});
				}
			}
		},
		upload(file){  // return a Promise
			var formData = new FormData();
			formData.append("flatfile", file);
			return fetch(this.uploadUrl, {
				method: "POST",
				body: formData
				// headers: { 'Content-Type': 'multipart/form-data' }  // not needed actually
			}).then(resp => resp.json());
		}
	},
	template:`<div class='d-flex align-items-baseline gap-1'>
		<span>flatfile</span>
		<select v-model="selectedIndex" class='form-control'>
			<option v-for="(v, idx) in flatfiles" :value='idx'>
				{{ v.innerHTML }}
			</option>
		</select>
		<a title="data reference" target="_blank"
			v-if="selectedIndex >=0 && flatfiles[selectedIndex].url"
			:href="flatfiles[selectedIndex].url">
			<i class="fa fa-external-link"></i>
		</a>
		<input type="file" style='display:none' @change="uploadFlatfiles($event.target.files)"/>
		<button
			class="btn btn-outline-primary border-0" type="button"
			onclick="this.parentNode.querySelector('input[type=file]').click()"
			title="upload user-defined flatfile in CSV or HDF format">
			<i class='fa fa-upload'></i>
		</button>
	</div>`
});


EGSIM.component('evenly-spaced-array-input', {
	props: {
		initialStart: {type: [String, Number], default: null},
		initialStop: {type: [String, Number], default: null},
	},
	data(){
		return {
			execCount: 0,
			maxNum: 2000, // prevent performance problems
			log: false,
			start: parseFloat(this.initialStart),
			stop: parseFloat(this.initialStop),
			num: null
		}
	},
	emits: ['array-created'],
	template:`<div class='d-flex align-items-baseline text-nowrap gap-1'>
		<input type='text' v-model="num" v-on:input="submit" class='form-control' :placeholder='"n (&le;" + maxNum + ")"' style='min-width:5.8rem !important'>
		values from
		<input type='text' v-model="start" v-on:input="submit" class='form-control'>
		to
		<input type='text' v-model="stop" v-on:input="submit" class='form-control'>
		<label title='values will be spaced evenly on a log scale (default: linear scale)'><input type='checkbox' v-model='log' v-on:change="submit" class='me-1'>log</label>
	</div>`,
	methods: {
		submit(){
			// calc in separate thread and fire if meanwhile we did not change the inputs:
			this.execCount += 1;
			var count = this.execCount;
			setTimeout(() => {
				var arr = this.createArray();
				if (this.execCount == count){
					this.$emit('array-created', arr);
				}
			}, 25);
		},
		createArray(){
			var num = parseInt(this.num);
			if (!(num > 1) || !(num <= this.maxNum)){  // note: this checks for num not NaN, too
				return [];
			}
			var start = parseFloat(this.start);
			var stop = parseFloat(this.stop);
			if (!(stop > start)){  // note: this checks for numbers not NaN, too
				return [];
			}
			var values = Array.from(Array(num).keys());
			if (this.log){
				// map [0...N-1] onto  [0...1] using y = e ** x:
				var E = Math.E;
				var range = E ** ((num-1) / num) - 1;
				values = values.map(i => (E ** (i/num) - 1)/ range);
				// map [0...1] onto  [start...end]:
				range = stop - start;
				values = values.map(v =>  start + v * range);
			}else{
				var step = parseFloat((stop - start) / (num-1));
				values = values.map(i => start + (i * step));
			}
			// Fix floating-point error and compute max decimal digits for better number visualization:
			var d = 1;  // power of then used to round (default 10**0)
			// start and stop can be rounded to log10(d) decimal digits without precision loss, and
			// each value rounded to log10(d) digits should be lower than the next value
			// (check values[1] - values[0] is sufficient, especially in log space)
			while((start != Math.round(d * start) / d) ||
				(stop != Math.round(d * stop) / d) ||
				parseInt(d * (values[1] - values[0])) < 1){
				d *= 10;
			}
			return values.map(v => Math.round(v * d) / d);
		}
	}
});