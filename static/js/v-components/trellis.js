/* Trellis plot components (model-to-model comparison) */

EGSIM.component('trellis', {
	props :{
		form: Object,
		url: String,
		urls: Object, // object with to props: downloadRequest, downloadResponse (both string)
	},
	data() {
		return {
			formVisible: true,
			formAsDialogBox: false,
			predefinedSA: false,  // whether we have selected spectra as plot type
			responseData: {},
			scenarioKeys: Object.keys(this.form).filter(key => key!='gsim' && key!='imt' && key!='plot_type' && key!='stdev')
		}
	},
	computed: {
		scenarioHasErrors(){
			var form = this.form;
			return this.scenarioKeys.some(key => !!form[key].error);
		}
	},
	watch: {
		'form.plot_type.value': {
			// watch the selected plot type and enable/disable the imt <select> accordingly
			immediate: true,
			handler(newVal, oldVal){
				var enabled = newVal !== 's' && newVal !== 'ss';
				this.form.imt.disabled = !enabled;
				this.predefinedSA = !enabled;
			}
		}
	},
	template: `<div class='d-flex flex-column position-relative' style="flex: 1 1 auto">
		<egsim-form :form="form" :url="url" :download-url="urls.downloadRequest"
					:show="formVisible" :dialogbox="formAsDialogBox"
					@submitted="(response) => {formVisible=false;formAsDialogBox=true;responseData=response.data;}">

			<template v-slot:left-column>
				<gsim-select :field="form['gsim']" :imtField="form['imt']" style="flex:1 1 auto" />
			</template>

			<template v-slot:right-column>
				<div style="position:relative">
					<imt-select :field="form['imt']" />
					<div v-show='predefinedSA' class="form-control small text-muted"
						 style="position:absolute;bottom:1rem;right:1rem;width:13rem;text-align:justify">
						<i class='text-warning fa fa-info-circle'></i>
						Intensity Measure will default to 'SA' with a set of pre-defined periods
					</div>
				</div>
				<div class="form-control mt-4"
					 :class="{'border-danger': scenarioHasErrors}"
					 style="flex: 1 1 0;min-height:3rem;background-color:transparent;overflow-y:auto">

					<template v-for="(name, index) in scenarioKeys" >
						<div v-if="form[name].type != 'checkbox'" class='d-flex flex-column'
							 :class="{ 'mt-2': index > 0 }">
							<field-label :field="form[name]" />
							<field-input :field="form[name]" />
						</div>
						<div v-else class='d-flex flex-row align-items-baseline'
							 :class="{ 'mt-2': index > 0 }">
							<field-input :field="form[name]" />
							<field-label :field="form[name]" class='ms-2' style='flex: 1 1 auto'/>
						</div>
					</template>

				</div>

				<div class="mt-4" style="background-color:transparent">
					<field-label :field='form["plot_type"]' />
					<field-input :field='form["plot_type"]' size="3" />
					<div class='mt-1 d-flex flex-row align-items-baseline'>
						<field-input :field='form["stdev"]'/>
						<field-label :field='form["stdev"]' class='ms-2' style='flex: 1 1 auto'/>
					</div>
				</div>
			</template>
		</egsim-form>

		<trellis-plot-div :data="responseData" :download-url="urls.downloadResponse"
						  class='invisible position-absolute start-0 top-0 end-0 bottom-0'
						  :style="{visibility: Object.keys(responseData).length ? 'visible !important' : '', 'z-index':1}">
			<slot>
				<button @click='formVisible=!formVisible' class='btn btn-sm btn-primary'>
					<i class='fa fa-list-alt'></i> Configuration
				</button>
			</slot>
		</trellis-plot-div>
	</div>`
});


EGSIM.component('trellis-plot-div', {
	mixins: [PlotsDiv],  // defined in plot-div.js
	methods: {
		getPlots(responseObject){
			var ln10 = Math.log(10);
			var mathlog = Math.log;
			function log10(val) {  // https://stackoverflow.com/a/3019290
				return mathlog(val) / ln10;
			}
			var mathpow = Math.pow;
			var pow10 = elm => mathpow(10, elm);

			var data = responseObject;
			var plots = [];
			// setup  label texts:
			for (var imt of data.imts){
				var figures = data[imt];
				for (var fig of figures){
					var params = {};
					params.imt = imt;
					params.magnitude = fig.magnitude;
					params.distance = fig.distance;
					params.vs30 = fig.vs30;
					var traces = [];
					Object.keys(fig.yvalues).map(function(name){
						// to test that plots are correctly placed, uncomment this:
						// var name = `${name}_${params.magnitude}_${params.distance}_${params.vs30}`;
						var yvalues = fig.yvalues[name];
						var trace = {
								x: data.xvalues,
								// <extra></extra> hides the second tooltip (white):
								hovertemplate: `${name}<br>${data.xlabel}=%{x}<br>` +
									`${fig.ylabel}=%{y}<extra></extra>`,
								y: yvalues,
								type: 'scatter',
								mode: (data.xvalues.length == 1 ? 'markers' : 'lines'),
								name: name
						};
						trace.legendgroup = name;
						var color = this.colors.get(trace.legendgroup);
						if (data.xvalues.length == 1){
							trace.marker = {color: color};
						}else{
							trace.line = {color: color, width: 3};
						}

						var _traces = [trace];
						// add stdev if present:
						var stdev = (fig.stdvalues || {})[name];
						if (stdev && stdev.length){
							//copy the trace Object (shallow except the 'y' property, copied deeply):
							var _traces = [
								trace,
								Object.assign({}, trace, {y:  yvalues.slice()}),
								Object.assign({}, trace, {y:  yvalues.slice()})
							];
							// put new values:
							stdev.forEach((std, index) => {
								if (std === null || _traces[1].y[index] === null){
									_traces[1].y[index] = null;
									_traces[2].y[index] = null;
								}else{
									_traces[1].y[index] = pow10(log10(_traces[1].y[index]) + std);
									_traces[2].y[index] = pow10(log10(_traces[2].y[index]) - std);
								}
							});
							// Values are now ok, now arrange visual stuff:
							var colorT = this.colors.rgba(color, 0.2);
							for (var i of [2]){
								_traces[i].fill = 'tonexty'; // which actually fills to PREVIOUS TRACE!
							}
							for (var i of [1, 2]){
								_traces[i].line = {width: 0, color: color};  // the color here will be used in the label on hover
								_traces[i].fillcolor = colorT;
								var info = i==1 ? `value computed as 10<sup>log(${imt})+σ</sup>` : `value computed as 10<sup>log(${imt})-σ</sup>`;
								_traces[i].hovertemplate = `${name}<br>${data.xlabel}=%{x}<br>${fig.ylabel}=%{y}` +
									`<br><i>(${info})</i><extra></extra>`;
							}
						}

						// put traces into array:
						for (var t of _traces){
							traces.push(t);
						}

					}, this);
					plots.push({
						data: traces,
						params: params,
						layout: {
							xaxis: {
								title: data.xlabel,
								type: 'linear'
							},
							yaxis: {
								title: fig.ylabel,
								type: 'log'
							}
						}
					});
				}
			}
			return plots;
		}
	}
});