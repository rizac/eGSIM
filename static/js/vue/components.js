EGSIM.component('array-input', {
	// <input> for numeric arrays, to be typed as space- or comma-separated numbers
	props: {
		'modelValue': { type: Array }, // <- this is the value of v-model
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


EGSIM.component('array-div', {
	// <div> including an array-input with the option to
	// easily type linear or log evenly spaced numbers
	props: {
		modelValue: { type: Array },
		initialStart: {type: [String, Number], default: null},
		initialStop: {type: [String, Number], default: null},
		logScale: {type: Boolean, default: false}
	},
	data(){
		return {
			showBaseInput: true,
			log: !!this.logScale,
			start: parseFloat(this.initialStart),
			stop: parseFloat(this.initialStop),
			num: null,
			maxLength: 100  // max points in the array
		}
	},
	computed: {
		mValue: {
			get() { return this.modelValue },
			set(value) { this.$emit('update:modelValue', value) }
		}
	},
	emits: ['update:modelValue'],
	template: `<div class='d-flex'>
		<array-input v-show="showBaseInput" v-model="mValue" class='form-control rounded-end-0' style='flex: 1 1 auto'></array-input>
		<div :class="showBaseInput ? 'd-none' : 'd-flex'" class='align-items-center gap-1' style='flex: 1 1 0'>
			<input v-model="num" v-on:input="setArray" class='form-control' :title='"number of values (<= " + maxLength + ")"' style='width:0; flex: 1 1 auto'>
			<span class='text-nowrap'>values from</span>
			<input type='text' v-model="start" v-on:input="setArray" class='form-control' style='width:0; flex: 1 1 auto'>
			<span>to</span>
			<input type='text' v-model="stop" v-on:input="setArray" class='form-control' style='width:0; flex: 1 1 auto'>
			<label title='values will be spaced evenly on a log scale (default: linear scale)' class='text-nowrap'>
				<input type='checkbox' v-model='log' v-on:change="setArray" class='me-1'>log
			</label>
		</div>
		<button type='button'
			@click="showBaseInput=!showBaseInput"
			class='btn btn-outline-primary'
			:class='showBaseInput? "border border-start-0 rounded-start-0" : "border-0 ms-1"'
			:title='showBaseInput ? "input evenly spaced numbers over a specified interval on a linear or log scale" : "restore default input"'>
			<i v-show='showBaseInput' class="fa fa-pencil"></i>
			<i v-show='!showBaseInput' class="fa fa-reply"></i>
		</button>
	</div>`,
	methods: {
		setArray(){
			// calc in separate thread and fire if meanwhile we did not change the inputs:
			var [n, s, e, l, m] = [this.num, this.start, this.stop, this.log];
			setTimeout(() => {
				var arr = this.createArray(n, s, e, l, this.maxLength);
				if ((this.num === n) && (this.start === s) && (this.stop === e) && (this.log === l)){
					this.mValue = arr;
				}
			}, 25);
		},
		createArray(num, start, stop, log, maxLength){
			var num = parseInt(num);
			if (!(num > 1) || !(num <= maxLength)){  // note: this checks for num not NaN, too
				return [];
			}
			var start = parseFloat(start);
			var stop = parseFloat(stop);
			if (!(stop > start)){  // note: this checks for numbers not NaN, too
				return [];
			}
			var values = Array.from(Array(num).keys());
			if (log){
				var base = 10; // Math.E;
				// map [0, ..., N-1] into [1, ..., BASE] (approximately)
				values = values.map(i => base ** (i / values.length));
				// map to in [0, ..., 1]:
				var range = values[values.length-1] - values[0];
				values = values.map(v => (v - values[0]) / range);
				// map to [start, .. stop]:
				var range = stop - start;
				values = values.map(v =>  start + v * range);
			}else{
				var step = parseFloat((stop - start) / (num-1));
				values = values.map(i => start + (i * step));
			}
			// if for some reason we do not have a strict ordering, return []:
			if (!(values[0] < values[1])){ return []; }
			// Now fix floating-point error and compute the maximum required decimal digits (dd):
			var round = this.round;
			var dd = 0;
			while(
				(!(round(values[0], dd) < round(values[1], dd))) ||
				(start !== round(start, dd)) ||
				(stop !== round(stop, dd))){
				dd += 1;
			}
			return values.map(v => round(v, dd));
		},
		round(number, decimalDigits){
			var base = 10 ** decimalDigits;
			return Math.round(number * base) / base;
		}
	}
});


EGSIM.component('gsim-select', {
	// <div> including a <select> for the Ground motion models selection
	props: {
		modelValue: {type: Array},  // [NOTE: VUE model] Array of selected ground motion model names
		models: {type: Array},  // [Note: Ground Motion models] Array of available models. Each model is an objects with keys: name, warning, imts
		selectedImts: {type: Array, default: []}, // field of selected IMTs (strings)
		modelInfoUrl: {type: String, default: ""}
	},
	emits: ['update:modelValue'],
	data() {
		return {
			inputElementText: "",
			displayRegex: /[A-Z]+[^A-Z0-9]+|[0-9_]+|.+/g,  //NOTE safari does not support lookbehind/aheads!
			modelInfoText: "",
			highlightedModels: []
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
				if (text.startsWith("imt:")){
					var imt = text.substring("imt:".length);
					models = this.models.filter(m => m.imts.has(imt));
				}else{
					var regexp = new RegExp(text.replace(/\s+/, '').replace(/([^\w\*\?])/g, '\\$1').replace(/\*/g, '.*').replace(/\?/g, '.'), 'i');
					models = this.models.filter(m => m.name.search(regexp) > -1);
				}
				// adjust popup height:
				if (models.length){
					setTimeout( () => this.resizeHTMLSelectElement(models.length), 20 );
				}
			}
			if (!models.length){
				this.highlightedModels = [];
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
			<i v-show="Object.keys(warnings).length && !inputElementText"
				title="Unselect models with warnings (for details, hover mouse on each model)"
				class="fa fa-exclamation-triangle ms-2 text-warning"
				style="cursor: pointer;"
				@click="removeSelectedModelsWithWarnings()">
			</i>
			<i v-show="Object.keys(errors).length && !inputElementText"
				title="Unselect models with errors (for details, hover mouse on each model)"
				class="fa fa-exclamation-triangle ms-2 text-danger"
				style="cursor: pointer;"
				@click="removeSelectedModelsWithErrors()">
			</i>
			<i v-show="selectedModels.length && !inputElementText"
				title="Unselect all models"
				class="fa fa-times-circle ms-2"
				style="cursor: pointer"
				@click="removeSelectedModels()">
			</i>
		</div>
		<div style='overflow: auto; flex: 1 1 auto'
			class='rounded-bottom-0 flex-column form-control'
			:class="selectedModels.length ? 'd-flex': 'd-none'">
			<div class='d-flex flex-column'>
				<div v-for="model in selectedModels" class='d-flex align-items-baseline gap-1'
					:title="(errors[model] || []).concat(warnings[model] || []).join('<br>')"
					:class="errors[model] ? 'text-danger' : warnings[model] ? 'text-warning' : ''">
					<span title="Remove from selection"
						style="cursor: pointer"
						@click="selectedModels.splice(selectedModels.indexOf(model), 1)">
						<i class='fa fa-times-circle'></i>
					</span>
					<span>{{ model }}</span>
					<span v-show='errors[model] || warnings[model]'
						:title="(errors[model] || []).concat(warnings[model] || []).join('<br>')">
						<i class='fa fa-exclamation-triangle'></i>
					</span>
				</div>
			</div>
		</div>
		<!-- select text and relative popup/div -->
		<div class='d-flex position-relative'>
			<input type="text"
				v-model='inputElementText' ref="search"
				@keydown.down.prevent="focusHTMLSelectElement()"
				@keydown.esc.prevent="clearText()"
				class='form-control'
				:class="selectedModels.length ? 'rounded-top-0 border-top-0' : ''"
				:style="!!inputElementText ? 'padding-right: 5em' : ''"
				title="you can also type imt: followed by an intensity measure (e.g. imt:SA) to show only models defined for that imt"
				:placeholder="'Type name (' + models.length + ' models available) or select by region (click on map)'" />
			<button type='button' @click="clearText()" v-show="!!inputElementText"
				title='Clear text and hide popup (ESC key on keyboard)'
				class='btn bg-transparent border-0 text-nowrap text-center position-absolute p-0 m-0 end-0 top-0 bottom-0'
				style='z-index:10;width:5rem'>
				<i class='fa fa-times-circle'></i> (ESC)
			</button>
		</div>
		<div class='position-relative'style='overflow:visible'>
			<select multiple ref="list" v-show='!!selectableModels.length'
				class='border position-absolute shadow start-0 end-0'
				style='z-index:10000; outline: 0px !important;'
				v-model='highlightedModels'
				@dblclick.prevent="addModelsToSelection()"
				@keydown.enter.prevent="addModelsToSelection()"
				@keydown.up="if( $event.target.selectedIndex == 0 ){ focusHTMLInputElement(); $event.preventDefault(); }"
				@keydown.space.prevent="showInfo()"
				@keydown.esc.prevent="clearText()">
				<option v-for="m in selectableModels" :value='m.name'>
					{{ m.name.match(displayRegex).join(" ") }}
				</option>
			</select>
			<div ref='keystrokes'
				:class='highlightedModels.length ? "d-flex" : "d-none"'
				class='align-items-baseline bg-body shadow gap-1 p-1 position-absolute start-0 end-0 text-nowrap border border-top-0'
				style='z-index:10001; overflow: auto;'>
				<i class='fa fa-info-circle'></i> Select models with double-click or Enter; get info with spacebar
			</div>
			<div ref='info' v-show="(!!modelInfoText) && (!!inputElementText)" v-html="modelInfoText"
				class='form-control position-absolute bg-white rounded-0 end-100'
				style='max-width:33vw; top: 0; bottom: 10vh; left: calc(100% + 1em); overflow:auto; height: min-content;'>
			</div>
			<div ref='infoArrow' v-show="(!!modelInfoText) && (!!inputElementText)"
				class='position-absolute border border-end-0 border-top-0 bg-white'
				style='width: .75rem;height: .75rem;left: calc(100% + 1em - 0.75em/2 + .5px);top:.75em;transform: rotate(45deg);transform-origin: center;'>
			</div>
		</div>
	</div>`,
	methods: {
		showInfo(){
			// fetch and show info on the highlighted selectable models
			var models = this.highlightedModels;
			if (!models.length){
				return;
			}
			this.modelInfoText = 'Loading info ... ';
			fetch(this.modelInfoUrl, {
				method: "POST",
				headers: {
					"Content-Type": "application/json",
				},
				body: JSON.stringify({'model': models}),
			}).then(response => {
				var json = response.json().then(obj => {
					var arr = Object.keys(obj).map(k =>
						`<h5 class='text-nowrap text-primary'>${k}</h5>
						<b>Defined for:</b> ${obj[k]['defined_for'].join(', ')}</b><br>
						${!obj[k]['sa_period_limits'] ? '' : '<b>SA period limits:</b> ' + obj[k]['sa_period_limits'].join(', ') + '<br>' }
						<b>Requires:</b> ${Object.keys(obj[k]['requires']).join(', ')}
						<div class='mt-2'>${obj[k]['description'].trim().replaceAll(/\.\s*\n\s*/g, ".<br>")}</div>
					`);
					this.modelInfoText = '<div class="d-flex flex-column gap-4"><div>' + arr.join('</div><div>') + '</div></div>';
				});
			}).catch((error) => {
				this.modelInfoText = 'No info available';
			});
		},
		clearText(){
			this.inputElementText = "";
			this.modelInfoText = "";
			this.focusHTMLInputElement();
		},
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
			var sel = this.$refs.list;
			if (sel.options.length && (!this.highlightedModels.length)){
				this.highlightedModels = [sel.options[0].value];
			}
			sel.focus();
		},
		focusHTMLInputElement(){
			this.highlightedModels = [];
			this.$refs.search.focus();
		},
		addModelsToSelection(){
			var modelNames = Array.from(new Set(this.highlightedModels).
				difference(new Set(this.selectedModels)));
			if (!modelNames.length){
				return;
			}
			this.selectedModels.push(...modelNames);
			this.$nextTick(() => {
				this.clearText();
			});
		},
		resizeHTMLSelectElement(optionsLength){
			var rect = this.$refs.search.getBoundingClientRect();
			this.$refs.list.size = optionsLength;
			var h = 100*(document.documentElement.clientHeight - rect.bottom)/document.documentElement.clientHeight;
			this.$refs.list.style.maxHeight = `calc(${h}vh - 3rem)`;  // (.90 * (document.documentElement.clientHeight - rect.bottom)) + 'px';
			this.$refs.info.style.maxHeight = `calc(${h}vh - 3rem)`;
			this.$refs.keystrokes.style.top = `calc(${h}vh - 3rem)`;
		}
	}
});


EGSIM.component('imt-select', {
	// <div> including a <select> for the intensity measure types selection
	props: {
		modelValue: { type: Array },  // [Vue model] Array of IMT names, with or without arguments
		imts: { type: Array },  // input IMTs (without arguments, so 'SA', not 'SA(1.0)')
		saWithoutPeriod: {type: Boolean, default: false}  // whether SA must be typed with periods or not (=> use only <select>)
	},
	emits: ['update:modelValue'],
	data() {
		var selectedImtClassNames = Array.from(new Set(this.modelValue.map(i => i.startsWith('SA(') ? 'SA' : i)));
		var SAPeriods = this.modelValue.filter(i => i.startsWith('SA(')).map(sa => sa.substring(3, sa.length-1));
		return {
			selectedImtClassNames: selectedImtClassNames,
			SAPeriods: SAPeriods
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
	template: `<div class='d-flex flex-column form-control gap-2'
		title="Intensity measure type(s)">
		<span class='mb-2'>Imt ({{ selectedImts.length }} selected)</span>
		<select v-model="selectedImtClassNames"
			multiple
			class='form-control'
			style="flex: 1 1 auto;">
			<option	v-for='imt in imts' :value="imt">
				{{ imt }}
			</option>
		</select>
		<div class='align-items-baseline gap-1'
			:class="selectedImtClassNames.includes('SA') && !saWithoutPeriod ? 'd-flex' : 'd-none'">
			<span class='text-nowrap'>SA periods</span>
			<array-div v-model="SAPeriods" initial-start="0.05" initial-stop="10" style='flex: 1 1 auto' />
		</div>
	</div>`,
	methods: {
		updateSelectedImts(){
			// same as this.selectedImts = getSelectedImts(), but without creating new Array:
			this.selectedImts.splice(0, this.selectedImts.length, ...this.getSelectedImts());
		},
		getSelectedImts(){
			if (this.saWithoutPeriod){
				return Array.from(this.selectedImtClassNames);
			}
			var imts = this.selectedImtClassNames.filter(i => i != 'SA');
			if (imts.length < this.selectedImtClassNames.length){
				// we selected 'SA'. Add periods:
				imts = imts.concat(this.SAPeriods.map(p => `SA(${p})`));
			}
			return imts;
		}
	}
});


EGSIM.component('gsim-map', {
	// <div> that will be bound to a Leaflet Map for the Ground motion models selection
	// on geographic location (based on a list of chosen regionalizations)
	props: {
		regionalizations: {type: Array},  // Array of Objects with keys name, bbox, url
		regionSelectedUrl: {type: String}
	},
	data(){
		return {
			map: null  // leaflet map
		};
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
			let map = L.map(this.$refs.mapDiv, {
				center: [48, 7],
				zoom: 4,
				minZoom: 3,
				maxBounds: new L.LatLngBounds(new L.LatLng(-90, -180-160), new L.LatLng(90, 200))
			});
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
								<span class='_arrow'><i class='fa fa-chevron-down'></i></span>
								<span class="_arrow d-none"><i class='fa fa-chevron-up'></i></span>
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
					// Esri_WorldImagery:
					Esri: L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
						attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
					}),
					Carto: L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
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
				var outOfBounds = outOfBoundsLng(regBounds[0], regBounds[2]) ||
					outOfBoundsLat(regBounds[1], regBounds[3]);
				var elm = this.getRegionalizationInput(regx.name);
				if (elm){
					elm.parentNode.style.display = outOfBounds ? 'none' : 'flex';
				}
			}
		},
		mapClicked(event) {
			var latLng = [event.latlng.lat, event.latlng.lng];
			// check if longitude is outside [-180, 180] (we assume lat always within -90, 90)
			if (latLng[1] > 180){
				latLng[1] = -180 + (latLng[1] % 180)
			}else if (latLng[1] < -180){
				latLng[1] = 180 + (latLng[1] % 180)
			}

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
			}).then(jsonData => {
				var popupApp = this.buildPopupVueApp(jsonData);
				const container = document.createElement("div");
				// container.className = 'd-flex flex-column';
				popupApp.mount(container);

				const popup = L.popup({ maxWidth: "auto" })
					.setLatLng(latLng)
					.setContent(container)
					.openOn(this.map);

				this.map.once("popupclose", () => popupApp.unmount());
			});
		},
		buildPopupVueApp(jsonData){
			var modelRegs = jsonData.models;  // model -> Array of regionalizations
			var modelSelected = {};
			for(var m of Object.keys(modelRegs)){
				modelSelected[m] = true;
			}
			var regUrl = {};
			for(var r of this.regionalizations){
				regUrl[r.name] = r.url;
			}
			var parent = this;
			return Vue.createApp({
				data: () => ({ parent: parent, modelSelected: modelSelected, modelRegs: modelRegs, regUrl: regUrl }),
				template: `
				<div v-if='Object.keys(modelRegs).length < 1'>
					<h6 class='text-nowrap mb-0'>No model applicable here</h6>
				</div>
				<div v-else class='d-flex flex-column gap-2'>
					<h6 class='text-nowrap mb-0'>Models applicable here</h6>
					<div style='max-height:33vh;overflow-y:auto;overflow-x:hidden'>
					<table class="table-sm">
						<tr class='border-bottom'>
							<th>Name</th><th title='Name of the regionalization that is the source of the model assignment'>Source regionalization</th>
						</tr>
						<tr v-for="name in Object.keys(modelSelected)" :key="name">
							<td>
								<label class='text-nowrap'>
									<input type="checkbox" v-model="modelSelected[name]" class='me-1'>{{ name }}
								</label>
							</td>
							<td>
								<div v-for="reg in modelRegs[name]" class='text-nowrap'>
									<template v-if="regUrl[reg]" >
										<a target="_blank" href="regUrl[reg]"
											:title="reg + ' (click for ref. in new browser tab)'">
											 {{ reg }} <i class="fa fa-external-link"></i>
										</a>
									</template><template v-else>
									{{ reg }}
									</template>
								</div>
							</td>
						</tr>
					</table>
					</div>
					<div class='d-flex flex-row gap-2 pt-2 border-top justify-content-center'>
						<button type='button' :disabled="!Object.keys(modelSelected).some(m => modelSelected[m])"
							class='btn btn-primary btn-sm' @click="selectAll">
							Select
						</button>
						<button type='button' :disabled="!Object.keys(modelSelected).some(m => modelSelected[m])"
							class='btn btn-primary btn-sm' @click="deselectAll">
							Deselect
						</button>
					</div>
				</div>
				`,
				methods: {
					selectAll() {
						this.parent.$emit("gsim-selected", Object.keys(this.modelSelected).
							filter(m => this.modelSelected[m]));
					},
					deselectAll() {
						this.parent.$emit("gsim-unselected", Object.keys(this.modelSelected).
							filter(m => this.modelSelected[m]));
					}
				}
			});
		}
	}
})


EGSIM.component('flatfile-select', {
	// <div> including a <select> for the Flatfiles selection
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
	template:`<div class='d-flex align-items-baseline'>
		<span class='me-1'>flatfile</span>
		<select v-model="selectedIndex" class='form-control rounded-end-0'>
			<option v-for="(v, idx) in flatfiles" :value='idx'>
				{{ v.innerHTML }}
			</option>
		</select>
		<input type="file" style='display:none' @change="uploadFlatfiles($event.target.files)"/>
		<button class="btn btn-outline-primary border border-start-0 rounded-start-0" type="button"
			onclick="this.parentNode.querySelector('input[type=file]').click()"
			title="upload user-defined flatfile in CSV or HDF format">
			<i class='fa fa-upload'></i>
		</button>
		<a title="flatfile reference" target="_blank" class='ms-1'
			v-if="selectedIndex >=0 && flatfiles[selectedIndex].url"
			:href="flatfiles[selectedIndex].url">
			<i class="fa fa-external-link"></i>
		</a>
	</div>`
});
