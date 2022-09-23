/* Flatfile components */

EGSIM.component('flatfile', {
	//https://vuejs.org/v2/guide/components-props.html#Prop-Types:
	props: {
		forms: Array,
		urls: Array
		// response: {type: Object, default: () => {return {}}}
	},
	data() {
		var compNames = ['flatfile-compilation', 'flatfile-plot'];  //, 'flatfile-inspection', 'flatfile-plot'];
		var compProps = {};
		compNames.forEach((elm, index) => {
			compProps[elm] = {
				form: this.forms[index],
				url: this.urls[index]
			};
		}, this);
		var compLabels = {
			'flatfile-compilation': 'Compilation',
			'flatfile-plot': 'Inspection plot'
		};
		return {
			componentNames: compNames,
			componentLabels: compLabels,
			componentProps: compProps,
			selComponentName: compNames[0],
		}
	},
	template: `<div class='d-flex flex-column' style='flex: 1 1 auto'>
		<ul class="nav nav-tabs">
			<li class="nav-item" v-for="compName in componentNames">
				<a class="nav-link" :class="selComponentName==compName ? 'active' : ''"
				   @click='selComponentName=compName'
				   :aria-current="compName" href="#">{{ componentLabels[compName] }}</a>
			</li>
		</ul>

		<transition name="fade" mode="out-in">
			<keep-alive>
				<component :is="selComponentName"
						   v-bind="componentProps[selComponentName]" />
			</keep-alive>
		</transition>
	</div>`
});


EGSIM.component('flatfile-compilation', {
	mixins: [BASE_FORM],
	//https://vuejs.org/v2/guide/components-props.html#Prop-Types:
	props: {
		form: Object,
		url: String,
		response: {type: Object, default: () => {return {}}}
	},
	data() {
		var supportedIMT = ['PGA', 'PGV', 'SA'];
		var selectedIMTs = ['PGA', 'SA'];
		var selectedSAPeriods = [0.1, 0.2, 0.3, 0.5, 1.0];
		this.form.gsim.value = ['AkkarEtAlRjb2014', 'BooreEtAl2014', 'CauzziEtAl2014'];
		return {
			responseData: this.response,
			imts: {
				value: selectedIMTs.filter(elm => elm != 'SA').concat(selectedSAPeriods.map(p => `SA(${p})`)),
				error: '',
				choices: supportedIMT,
				label: 'Intensity Measure Type(s)',
				name: 'imt',
				multiple: true
			},
			csvSep: ',',
			flatfileContent: '',
			flatfileHeader: []
		}
	},
	watch: {
		responseData(newVal, oldVal){
			this.updateFlatfile();
		},
		'imts.value':  function(newVal, oldVal){
			this.updateFlatfile();
		},
		csvSep(newVal, oldVal){
			this.updateFlatfile();
		}
	},
	template: `<form novalidate class='d-flex flex-column p-2' style='flex: 1 1 auto'>
		<div class='mt-3'>
			<p>
			Model-to-data comparison and testing require data which must be provided
			in eGSIM via flatfiles, i.e. text files in <a target="_blank"
			href="https://en.wikipedia.org/wiki/Comma-separated_values">CSV format</a>.
			Each line of a flatfile is an observed seismic waveform. Each waveform
			consists of one or more fields (the waveform data and metadata),
			separated by commas or similar characters (e.g. semicolon).
			The minimum required fields that must be provided when uploading a flatfile
			depend on the models to compare and the intensity measures used for
			comparison, as illustrated in the template below that can be dynamically
			adapted and used for compiling user defined flatfiles
			</p>
		</div>

		<div class='d-flex flex-row' style='flex: 1 1 auto;'>
			<div class='d-flex flex-column'>
				<div class='mb-3'>
					<b>Select models</b> ({{ form.gsim.value.length }}) <b>and intensity measures</b> ({{ imts.value.length }})
					<b>of interest:</b>
				</div>
				<gsim-select :field='form.gsim'
							 @gsim-selected='gsimSelected'
							 :imt-field="imts"
							 class='mb-3' style='flex: 1 1 auto' />
				<imt-select :field='imts' />
			</div>

			<div class='mx-3'></div>

			<div class='d-flex flex-column' style='flex: 1 1 auto'>
				<div class='mb-3 position-relative'>
					<b>Flatfile template</b>&nbsp; ({{ flatfileHeader.length }} columns)
					<div class='text-nowrap position-absolute end-0 top-0'>
						CSV separator
						<input type="text" v-model="csvSep" class='ms-1' style='max-width:2rem' />
					</div>
				</div>

				<textarea v-model='flatfileContent'
						  style='flex:1 1 auto; white-space: pre; font-family:monospace; background-color:#363945; color:#e1e1e1'>
				</textarea>

				<div class='mt-2 text-muted'>
				Hint: For performance reasons <b>try to keep uploaded flatfiles size within few tens of Megabytes</b>
				</div>

			</div>
		</div>
	</form>`,
	methods: {
		gsimSelected(){
			// query the server and store in response data the metadata columns
			// required for the current GSIM selection
			this.$nextTick(() => {
				this.submit().then(response => {
					this.responseData = response.data;
				});
			});
		},
		updateFlatfile(){
			var metadataColumns = this.getMetadataColumns();
			var imtColumns = this.getImtColumns();
			var columns = metadataColumns.concat(imtColumns);
			// calculate depths (characters length of each column):
			var helpHeaders = ['Column:', 'Type:', 'Data type:', 'Description:'];
			var depths = helpHeaders.map(elm => elm.length);
			var header = [];
			var max = Math.max;
			for (var val of columns){
				header.push(val[0]);
				depths = val.map((elm, index) => max(elm.length, depths[index]));
			}
			this.flatfileHeader = header;
			var flatfileContent = [
				header.join(this.csvSep), '',
				'# This block comment is not part of the CSV: it contains column information to help the compilation:',
			];
			for (var val of [helpHeaders].concat(columns)){
				var row = val.map((elm, index) => elm + " ".repeat(depths[index] - elm.length)).join(" | ");
				flatfileContent.push(`# ${row}`);
			}
			var numGsim = this.form.gsim.value.length;
			var listGsim = this.form.gsim.value.join(' ');
			flatfileContent.push(`# The metadata columns above are required in eGSIM by ${numGsim} selected model(s):  ${listGsim}`);
			flatfileContent.push('');
			this.flatfileContent = flatfileContent.join("\n");
		},
		getMetadataColumns(){  // -> Array[Array[str, str, str, str]]
			// return a list of metadata columns from the response data
			var data = this.responseData;
			// the columns are objects that are empty if the column is not needed in the flatfile:
			var namesOk = Object.keys(data).filter(name => !!Object.keys(data[name]).length);
			var namesNo = Object.keys(data).filter(name => !Object.keys(data[name]).length);
			var ret = [];
			for (var name of namesOk.sort()){
				var [dtype, help] = [data[name].dtype, data[name].help];
				if (Array.isArray(dtype)){
					help += `. Specify a value from: ${dtype.join(", ")}`;
					dtype = "categorical";
				}
				ret.push([name, "Metadata", dtype, help]);
			}
			return ret;
		},
		getImtColumns(){  // -> Array[Array[str, str, str, str]]
			var desc = (imt) => {
				if (imt.startsWith('SA')){
					return 'Spectral Acceleration, in g (computed at the given period, in s)'
				}else if (imt == 'PGA'){
					return 'Peak Ground Acceleration, in cm/s*s'
				}else if (imt == 'PGV'){
					return 'Peak Ground Velocity, in cm/s'
				}
				return '';
			}
			return this.imts.value.map(elm => [elm, 'Intensity measure', 'float', desc(elm)]);
		}
	}
});


EGSIM.component('flatfile-plot', {
	mixins: [BASE_FORM],  // will have props Form, url, and all methods for issuing post requests
	props: {
		form: Object,
		url: String,
		response: {type: Object, default: () => {return {}}}
	},
	data() {
		return {
			responseData: this.response,
		}
	},
	watch: {
//		no-op
	},
	methods: {
		request(){
			var form = this.form;
			Vue.post(this.url, form).then(response => {  // defined in `vueutil.js`
				if (response && response.data){
					this.responseData = response.data;
				}
			});
		},
		flatfileSelected(file){
			var vals = Object.keys(file.columns).map(col => [col, `${col} ${file.columns[col]}`]);
			this.form.x.choices = this.form.x.choices.slice(0, 1).concat(vals);
			this.form.y.choices = this.form.y.choices.slice(0, 1).concat(vals);
		},
		submitMe(){
			this.submit().then(response => {this.responseData = response.data});
		}
	},
	template: `<div class='d-flex flex-column' style='flex: 1 1 auto'>
		<div class='mb-3'>
		   <form novalidate @submit.prevent="submitMe">
				<div class="d-flex flex-row align-items-end" style='flex: 1 1 auto'>
					<flatfile-select :field="form.flatfile" @flatfile-selected="flatfileSelected" />
					<span class='me-3'></span>
					<flatfile-selexpr-input :field="form.selexpr" class='mt-3'/>
					<span class='me-3'></span>
					<field-input :field='form.x'/>
					<span class='me-3'></span>
					<field-input :field='form.y'/>
					<span class='me-3'></span>
					<button type="submit" class="btn btn-primary mt-2">
						Display plot
					</button>
				</div>
		   </form>
		</div>
		<flatfile-plot-div :data="responseData" class="invisible"
						   :style='{visibility: Object.keys(responseData).length ? "visible !important" : "", flex: "1 1 auto"}'/>
	</div>`
});


EGSIM.component('flatfile-plot-div', {
	mixins: [PLOT_DIV],
	methods: {
		// The next two methods are overwritten from PLOT_DIV. See README.md for details
		getData(responseObject){
			var jsondict = responseObject;
			var hist = true;
			// set plotly data from jsondict:
			if (jsondict.xlabel && jsondict.ylabel){
				hist = false;
				var trace = {
					x: jsondict.xvalues,
					y: jsondict.yvalues,
					mode: 'markers',
					type: 'scatter',
					text: jsondict.labels || [],
					name: `${jsondict.xlabel} vs ${jsondict.ylabel}`,
					marker: { size: 10 },
					// <extra></extra> hides the second tooltip (white):
					hovertemplate: `${jsondict.xlabel}=%{x}<br>${jsondict.ylabel}=%{y}`+
						`<extra></extra>`
				};
			}else if(jsondict.xlabel){
				var trace = {
					x: jsondict.xvalues,
					type: 'histogram',
					name: jsondict.xlabel,
					marker: { line: { width: 0 }}
				};
			}else{
				var trace = {
					y: jsondict.yvalues,
					type: 'histogram',
					name: jsondict.ylabel,
					marker: { line: { width: 0 }}
				  };
			}
			var color = this.addLegend(trace, trace.name); //sets also mainTrace.legendgroup
			// set the marker color (marker is visually a bar if mainTrace.type is 'bar'):
			trace.marker.color = this.colorMap.transparentize(color, .5);
			if (hist){
				trace.marker.line.color = color;
			}

			// modify here the default layout:
			// this.defaultlayout.title = `Magnitude Distance plot (${trace.x.length} records in database)`;
			var data = [ trace ];
			var xaxis = {
				// type: 'log',
				title: jsondict.xlabel || 'Count'
			};
			var yaxis = {
				title: jsondict.ylabel || 'Count'
			};

			var params = {};  // {'Magnitude Distance plot': title};
			return [{traces: [trace], params: params, xaxis: xaxis, yaxis: yaxis}];
		},
		displayGridLabels(axis, paramName, paramValues){ //
			return true;  // we have  single param (sort of title on the x axis), alswya show
		}
	}
});


EGSIM.component('flatfile-select', {
	//See README.md
	props: {
		field: {type: Object},
		doc: {
			'type': String,
			'default': `Upload a user-defined flatfile (CSV or zipped CSV).
					  Please consult also the tab "Flatfiles" to inspect your flatfile before usage.
					  An uploaded flatfile will be available in all tabs of this web page`
		}
	},
	data(){
		// In case of Proxy error, see here for details: https://stackoverflow.com/a/65732553
		return {
			selectedFlatfileIndex: -1  //our model value
		}
	},
	emits: ['flatfile-selected'],
	watch: {
		'$flatfiles': {
			// global property (see egsim.html): it provides the choices for the current
			// Field and makes all other similar Fields update automatically
			deep: true,
			immediate: true,
			handler(newVal, oldVal){
				this.field.choices = Array.from(newVal.map((elm, idx) => [idx, elm.label]));
			}
		}
	},
	computed: {
		flatfileURL(){
			if (this.selectedFlatfileIndex >=0 ){
				return this.$flatfiles[this.selectedFlatfileIndex].url;
			}
			return undefined;
		}
	},
	methods:{
		filesUploaded(files){
			var flatfiles = this.$flatfiles;
			for (let file of files){
				var label = `${file.name} (Uploaded: ${new Date().toLocaleString()})`;
				var append = true;
				for (let flatfile of flatfiles){
					if (!flatfile.file){  // pre-defined flatfile
						continue;
					}
					if (flatfile.name == file.name){
						this.upload(file).then(response => {
							flatfile.file = file;
							flatfile.label = label;  // update label on <select>
							flatfile.columns = response.data.columns;
						});
						append = false;
						break;
					}
				}
				if (append){
					this.upload(file).then(response => {
						var cols = response.data.columns;
						flatfiles.push({ name: file.name, label: label, file: file, columns: cols });
					});
				}
			}
		},
		upload(file){  // return a Promise
			var formData = new FormData();
			formData.append("flatfile", file);
			return EGSIM.post(this.field['data-url'], formData, {
				headers: {
				  'Content-Type': 'multipart/form-data'
				}
			});
		},
		ffSelected(flatfileIndex){
			// set the Field value as String (predefined flatfile) or File:
			var selFile = this.$flatfiles[parseInt(flatfileIndex)] || null;
			if (selFile){
				this.field.value = selFile.file || selFile.name;
				this.$emit('flatfile-selected', selFile);
			}
		}
	},
	template:`<div class='d-flex flex-column'>
		<field-label :field="field" />
		<div class='d-flex flex-row align-items-baseline'>
			<base-input :value="selectedFlatfileIndex"
						@value-changed="ffSelected"
						:choices="field.choices"
						:error="!!field.error" :disabled="field.disabled"/>
			<div class='d-flex flex-row align-items-baseline'>
				<a title='flatfile reference (opens in new tab)' target="_blank"
				   class='ms-1' v-show="!!flatfileURL" :href="flatfileURL"><i class="fa fa-link"></i></a>
				<button type="button" class="btn btn-primary ms-1" onclick="this.nextElementSibling.click()"
						:aria-label='doc' data-balloon-pos="down" data-balloon-length="large">
					upload
				</button>
				<!-- THIS MUST ALWAYS BE NEXT TO THE BUTTON ABOVE: -->
				<input type="file" v-show="false" @change="filesUploaded($event.target.files)"/>
			</div>
		</div>
	</div>`
});


EGSIM.component('flatfile-selexpr-input', {
	props: {
		field: {type: Object},
		doc: {
			type: String,
			default: `Type an expression that operates on arbitrary flatfile columns to select
					  only rows matching the expression, e.g.: "magnitude>5" (quote characters "" excluded).
					  Valid comparison operators are == != > < >= <=.
					  Logical operators are & (and) | (or) ! (not), e.g.:
					  "(magnitude >= 5) & (vs30 > 760)".
					  Use notna([column]) to match rows where the column value is given,
					  i.e. not 'not available' (na). For instance, to get records where at rjb or
					  repi is available:
					  "(magnitude>5) & (notna(rjb) | notna(repi))"
					  (notna works for numeric and string columns only)
					  `
		}
	},
	template: `<div class='d-flex flex-column'
			 :aria-label="doc" data-balloon-pos="down" data-balloon-length="xlarge">
			<field-label :field='field'/>
			<field-input :field='field' style='flex:1 1 auto'/>
		</div>`
});
