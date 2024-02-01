/* Flatfile components */
// FIXME import submitForm from ....

EGSIM.component('flatfile', {
	props: {
		forms: Array,
		urls: Array
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
			'flatfile-compilation': 'Flatfile compilation',
			'flatfile-plot': 'Flatfile inspection plots'
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
	props: {
		form: Object,
		url: String,
		response: {type: Object, default: () => {return {}}}
	},
	data() {
		this.form.imt.value = ['PGA', 'PGV', 'SA(0.1)'];
		this.form.gsim.value = ['AkkarEtAlRjb2014', 'BooreEtAl2014', 'CauzziEtAl2014'];
		return {
			responseData: this.response,
			csvSep: ',',
			flatfileContent: '',
			flatfileHeader: [],
			needsRefresh: true
		}
	},
	watch: {
		responseData(newVal, oldVal){
			this.updateFlatfile();
		},
		csvSep(newVal, oldVal){
			this.updateFlatfile();
		}
	},
	template: `<form novalidate class='d-flex flex-column p-2' style='flex: 1 1 auto'>
		<div class='mt-3'>
			<p>
			A Flatfile is the data set required in Model-to-data comparison and
			testing, and must be uploaded in eGSIM as zipped or uncompressed
			<a target="_blank"
			href="https://en.wikipedia.org/wiki/Comma-separated_values">CSV file</a>.
			Each line of a flatfile is an observed seismic waveform, each waveform
			consists of one or more fields (the waveform data and metadata),
			separated by commas or similar characters (e.g. semicolon)
			</p>
		</div>

		<div class='d-flex flex-row' style='flex: 1 1 auto;'>
			<div class='d-flex flex-column' style='flex: 1 1 auto'>
				<div class="d-flex flex-column" style='flex: 1 1 0; overflow-y: auto'>
					<div class='mb-3'>
						<b>Select models</b> ({{ form.gsim.value.length }}) <b>and intensity measures</b> ({{ form.imt.value.length }})
						<b>of interest:</b>
					</div>
					<gsim-select :field='form.gsim'
								 @gsim-selected='needsRefresh=true'
								 :imt-field="form.imt"
								 class='mb-3' style='flex: 1 1 auto' />
					<imt-select :field='form.imt' @imt-selected='needsRefresh=true' />
				</div>
			</div>

			<div class='mx-3'></div>

			<div class='d-flex flex-column' style='flex: 1 1 auto'>
				<div class="d-flex flex-column" style='flex: 1 1 0; overflow-y: auto'>
					<div class='mb-3 position-relative'>
						<b>Flatfile template</b>&nbsp; ({{ flatfileHeader.length }} columns)
						<button v-show='needsRefresh' type='button' class='btn btn-primary'
								@click='queryRequiredColumns'>Refresh</button>
						<div class='text-nowrap position-absolute end-0 top-0'>
							CSV separator
							<input type="text" v-model="csvSep" class='ms-1' style='max-width:2rem' />
						</div>
					</div>

					<textarea v-model='flatfileContent' spellcheck="false" class='form-control'
							  style='resize:none; flex:1 1 auto; white-space: pre; font-family:monospace; background-color: rgb(245, 242, 240);'>
					</textarea>

					<div class='mt-2 text-muted'>
					Hint: For performance reasons <b>try to keep uploaded flatfiles size within few tens of Megabytes</b>
					</div>
				</div>
			</div>
		</div>
	</form>`,
	methods: {
		queryRequiredColumns(){
			// query the server and store in response data the metadata columns
			// submitForm defined globally
				submitForm(this.url, this.form).then(response => {
					this.responseData = response.data;
					this.needsRefresh = false;
				});
			// });
		},
		updateFlatfile(){
			var flatfileContent = [
				Object.keys(this.responseData).join(this.csvSep), '',
				'# Column information (this is a block comment that does not need to be included in the CSV):',
				'#'
			];
			var names = ['Column:'];
			var helps = ['Description:'];
			var dtypes =['Data type:']
			var types = ['Type:'];
			for (var name of Object.keys(this.responseData)){
				var colMetadata = this.responseData[name];
				names.push(name)
				helps.push(colMetadata.help);
				types.push(colMetadata.type);
				dtypes.push(colMetadata.dtype);
			}
			var namesMaxlen = Math.max(...names.map(elm => elm.length));
			var helpsMaxlen = Math.max(...helps.map(elm => elm.length));
			var typesMaxlen = Math.max(...types.map(elm => elm.length));
			var dtypesMaxlen = Math.max(...dtypes.map(elm => elm.length));
			for (var i=0; i< names.length; i++){
				var line = [
					names[i] + " ".repeat(namesMaxlen - names[i].length),
					types[i] + " ".repeat(typesMaxlen - types[i].length),
					dtypes[i] + " ".repeat(dtypesMaxlen - dtypes[i].length),
					helps[i] + " ".repeat(helpsMaxlen - helps[i].length)
				];
				flatfileContent.push(`#  ${line.join(" | ")}`);
			}
			var numGsim = this.form.gsim.value.length;
			var listGsim = this.form.gsim.value.join(' ');
			flatfileContent.push(`#`);
			flatfileContent.push(`# This template has been generated to work with the following ${numGsim} model(s):`);
			flatfileContent.push(`# ${listGsim}`);
			flatfileContent.push('');
			this.flatfileContent = flatfileContent.join("\n");
		}
	}
});


EGSIM.component('flatfile-plot', {
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
	methods: {
		flatfileSelected(value, columns){  // value: string or File object
			var vals = value ? Object.keys(columns).map(col => [col, `${col} (${columns[col]})`]) : [];
			vals.sort((a, b) => { return a[0].toLowerCase() > b[0].toLowerCase() ? 1 : -1 });
			this.form.x.choices = this.form.x.choices.slice(0, 1).concat(vals);
			this.form.y.choices = this.form.y.choices.slice(0, 1).concat(vals);
		},
		submit(){
			submitForm(this.url, this.form).then(response => {this.responseData = response.data});
		}
	},
	template: `<div class='d-flex flex-column' style='flex: 1 1 auto'>
		<div class='mb-3'>
		   <form novalidate @submit.prevent="submit">
				<div class="d-flex flex-row align-items-end" style='flex: 1 1 auto'>
					<flatfile-select :field="form.flatfile" @flatfile-selected="flatfileSelected" style='flex: 1 1 100%'/>
					<span class='me-3'></span>
					<flatfile-selexpr-input :field="form.selexpr" class='mt-3'/>
					<span class='me-3'></span>
					<div class='d-flex flex-column'>
						<field-label :field='form.x'/>
						<field-input :field='form.x'/>
					</div>
					<span class='me-3'></span>
					<div class='d-flex flex-column'>
						<field-label :field='form.y'/>
						<field-input :field='form.y'/>
					</div>
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
	mixins: [PlotsDiv],
	methods: {
		getPlots(responseObject){
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
			trace.legendgroup = trace.name;
			var color = this.colors.get(trace.legendgroup);
			trace.marker.color = this.colors.rgba(color, .5);
			if (hist){
				trace.marker.line.color = color;
			}

			// modify here the default layout:
			// this.defaultlayout.title = `Magnitude Distance plot (${trace.x.length} records in database)`;
			var plot = {
				data: [ trace ],
				params: {},
				layout: {
					xaxis: {
						title: jsondict.xlabel || 'Count'
					},
					yaxis: {
						title: jsondict.ylabel || 'Count'
					}
				}
			}
			return [plot];
		}
	}
});


EGSIM.component('flatfile-select', {
	props: {
		field: {type: Object},
		doc: {
			'type': String,
			'default': `Upload a user-defined flatfile (CSV or zipped CSV).
					  It is recommended to inspect the flatfile before usage (see Data Management Tab).
					  An uploaded flatfile will be available in all tabs of this web page`
		}
	},
	data(){
		// the idea here is to provide a proxy Field and bound it to the <select>
		// This Proxy will have as value an index, which works with <option>s and allows
		// to easily check for duplicate Files, whereas our Field will have as value
		// either the File object or the string, in case of a predefined flatfile
		return {
			fieldProxy: {
				name: this.field.name,
				error: this.field.error,
				disabled: this.field.disabled || false,
				value: -1,
				choices: []
			}
		}
	},
	emits: ['flatfile-selected'],
	// FIXME: watch fieldProxy value and emit a flatfile selected
	watch: {
		'field.choices': {
			deep: true,
			immediate: true,
			handler(newVal, oldVal){
				this.fieldProxy.choices = newVal.map((elm, idx) => {
					return { url: elm.url || "", value: idx, innerHTML: elm.innerHTML };
				});
				// automatically select uploaded file, if any (select the last uploaded):
				for (var i=newVal.length-1; i>=0; i--){
					var isUploadedFile = newVal[i].value instanceof File;
					if (isUploadedFile){
						this.fieldProxy.value = i;
						break;
					}
				}
			}
		},
		'fieldProxy.value': {
			immediate: true,
			handler(newVal, oldVal){
				var choice = this.field.choices[newVal];
				this.field.value = choice ? choice.value || null : null;
				var columns = choice ? choice.columns || [] : []
				this.$emit('flatfile-selected', ... [this.field.value, columns]);
			}
		},
		'field.error': {
			immediate: true,
			handler(newVal, oldVal){
				this.fieldProxy.error = newVal;
			}
		}
	},
	computed: {
		flatfileURL(){
			var selIndex = this.fieldProxy.value;
			if (selIndex >=0 ){
				return this.fieldProxy.choices[selIndex].url;
			}
			return undefined;
		}
	},
	methods:{
		filesUploaded(files){
			var choices = this.field.choices;
			// var proxyChoices = this.fieldProxy.choices;
			for(var index = 0; index < files.length; index++){
				var file = files[index];
				var label = `${file.name} (${new Date().toLocaleString()})`;
				var append = true;
				for (let choice of choices){
					if (choice.value instanceof File && choice.value.name == file.name){
						this.upload(file).then(response => {
							choice.value = file;
							choice.innerHTML = label;  // update label on <select>
							choice.columns = response.data.columns;
						});
						append = false;
						break;
					}
				}
				if (append){
					this.upload(file).then(response => {
						var cols = response.data.columns;
						choices.push({ value: file, innerHTML: label, columns: cols });
					});
				}
			}
		},
		upload(file){  // return a Promise
			var formData = new FormData();
			formData.append("flatfile", file);
			return fetch(this.field['data-url'], formData, {
				headers: { 'Content-Type': 'multipart/form-data' }
			});
		}
	},
	template:`<div class='d-flex flex-column'>
		<field-label :field="fieldProxy" />
		<div class='d-flex flex-row align-items-baseline'>
			<field-input :field="fieldProxy" />
			<div class='d-flex flex-row align-items-baseline'>
				<a aria-label='flatfile reference (opens in new tab)' target="_blank"
				   class='ms-1' v-show="!!flatfileURL" :href="flatfileURL"><i class="fa fa-link"></i></a>
				<button type="button" class="btn btn-primary ms-1" onclick="this.nextElementSibling.click()" :aria-label='doc'>
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
					  only rows matching the expression. <br>Example:
					  <code>(magnitude &gt; 4.5) and ((event_id == "gfd20") or (vs30measured != true))</code>
					  <p></p>
					  You can also use specific column properties such as "median", "mean", "max", "min" or "notna"<br>
					  (the latter selects rows where the column value is not missing, useful for columns of type<br>
					  float, string, datetime that can have missing values such as NaN or null). Examples:
					  <br><code>magnitude.notna</code><br><code>vs30 &lt;= vs30.median</code>
					  <p></p>
					  Note: date-time values can be input as Python datetime objects, e.g.:
					  <br><code>datetime_column_name &lt;= datetime(2016, 12, 31, 23, 59, 59)</code>`
		}
	},
	template: `<div class='d-flex flex-column' :aria-label="doc">
			<field-label :field='field'/>
			<field-input :field='field' style='flex:1 1 auto'/>
		</div>`
});
