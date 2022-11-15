/* Residuals plot components (model-to-data comparison) */

EGSIM.component('residuals', {
	props :{
		form: Object,
		url: String,
		urls: Object, // object with to props: downloadRequest, downloadResponse (both string)
	},
	data() {
		return {
			formVisible: true,
			formAsDialogBox: false,
			responseData: {}
		}
	},
	template: `<div class='d-flex flex-column position-relative' style="flex: 1 1 auto">
		<egsim-form :form="form" :url="url" :download-url="urls.downloadRequest"
					:show="formVisible" :dialogbox="formAsDialogBox"
					@submitted="(response) => {formVisible=false;formAsDialogBox=true;responseData=response.data}">

			<template v-slot:left-column>
				<gsim-select :field="form.gsim" :imtField="form.imt" style="flex:1 1 auto" />
			</template>

			<template v-slot:right-column>

				<imt-select :field="form.imt" style="flex: 1 1 auto;" />
				<div class="mt-4 form-control pb-3 pt-2" style="background-color:transparent">
					<flatfile-select :field="form.flatfile"/>
					<flatfile-selexpr-input :field="form.selexpr" class='mt-3' />
				</div>
				<div class="mt-4">
					<field-label :field='form.plot_type' />
					<field-input :field='form.plot_type' size="10"/>
				</div>

			</template>
		</egsim-form>

		<residuals-plot-div :data="responseData" :download-url="urls.downloadResponse"
							class='invisible position-absolute start-0 top-0 end-0 bottom-0'
							:style="{visibility: Object.keys(responseData).length ? 'visible !important' : '', 'z-index':1}">
			<slot>
				<button @click='formVisible=!formVisible' class='btn btn-sm btn-primary'>
					<i class='fa fa-list-alt'></i> Configuration
				</button>
			</slot>
		</residuals-plot-div>
	</div>`
});


EGSIM.component('residuals-plot-div', {
	mixins: [PlotsDiv],  // defined in plot-div.js
	methods: {
		getPlots(responseObject){
			// defined normal dist. constants:
			var E = Math.E;
			var PI = Math.PI;
			var exp = Math.exp;
			var pow = Math.pow;
			var sqrt = Math.sqrt;
			var normdist = function(xvalues, mean, sigma){
				var twoSigmaSquare = 2 * pow(sigma, 2);
				var multiplier = 1 / sqrt(PI*twoSigmaSquare);
				return xvalues.map(x => {
				   return multiplier * exp(-pow((x-mean), 2)/twoSigmaSquare);
				});
			};
			var resample = function(array, granularity=1, uniquesorted=true){
				if (uniquesorted){
					var arr = Array.from(new Set(array)).sort((a,b) => a > b ? 1 : a < b ? -1 : 0);
				}else{
					var arr = array.slice();
				}
				if (granularity <= 1 || array.length <= 1){
					return arr;
				}
				var newarray = [];
				for (var i=0; i< arr.length-1; i++){
					newarray.push(arr[i]);
					var step = (array[i+1] - array[i])/granularity;
					for(var j=1; j<granularity; j++){
						newarray.push(array[i] + step*j);
					}
				}
				newarray.push(array[array.length-1]);
				return newarray;
			};
			var endpoints = function(array){
				var sorted = array.filter(val => typeof val === 'number').
					sort((a,b) => a > b ? 1 : a < b ? -1 : 0);
				return sorted.length ? [sorted[0], sorted[sorted.length-1]] : [null, null];
			};
			// setup  plots:
			var data = responseObject;
			var plots = [];
			for (var imt of Object.keys(data)){
				for (var type of Object.keys(data[imt])){
					for (var gsim of Object.keys(data[imt][type])){
						var plotdata = data[imt][type][gsim];
						var hasLinearRegression = plotdata.intercept != null && plotdata.slope != null;
						var [xlbl, ylbl] = [plotdata.xlabel, plotdata.ylabel];
						var ptText = `${plotdata.xlabel}=%{x}<br>${plotdata.ylabel}=%{y}`;
						var mainTrace = {
							x: plotdata.xvalues,
							y: plotdata.yvalues,
							type: hasLinearRegression ? 'scatter' : 'bar',
							name: type,
							// <extra></extra> hides the second tooltip (white):
							hovertemplate: `${gsim}<br>${xlbl}=%{x}<br>${ylbl}=%{y}<extra></extra>`
						};
						mainTrace.legendgroup = mainTrace.name;
						var color = this.colors.get(mainTrace.legendgroup);
						mainTrace.marker = {color: this.colors.rgba(color, .5)};
						// add other stuff (normal distributions, regression lines, ...):
						if (hasLinearRegression){  // scatter plot
							mainTrace.mode = 'markers';  // hide connecting lines
							mainTrace.marker.size = 10;
							// show linear regression according to slope and intercept:
							// var [min, max] = endpoints(plotdata.xvalues);
							var [slope, intercept] = [plotdata.slope, plotdata.intercept];
							var xreg = resample(plotdata.xvalues);
							var yreg = xreg.map(x => x*slope+intercept);
							var linregtrace = {
								x: xreg,
								y: yreg,
								type: 'scatter',
								mode: 'lines',
								name: 'Linear regression',
								hovertemplate: `${gsim} linear regression` +
									`<br>slope=${slope}<br>intercept=${intercept}<br>pvalue=${plotdata.pvalue}`+
									`<br><br>${xlbl}=%{x}<br>${ylbl}=%{y}` +
									`<extra></extra>`
							}
							linregtrace.legendgroup = linregtrace.name;
							linregtrace.line = {color: '#331100'};
							var traces = [mainTrace, linregtrace];
						}else{
							// customize more the marker (which are bars in this case):
							mainTrace.marker.line = {
								color: color,
								width: 2
							};
							var hasMeanStdev = plotdata.mean != null && plotdata.stddev != null;
							var hasMedian = plotdata.median != null;
							if (hasMeanStdev){

								// show normal distribution and reference normal dist. (mean=0 sigma=1)
								var x = resample(plotdata.xvalues, granularity=5);
								var normdistline = {
									x: x,
									y: normdist(x, plotdata.mean, plotdata.stddev),
									type: 'scatter',
									mode: 'lines',
									name: 'Normal distribution',
									hovertemplate: `${gsim} normal distribution` +
										`<br>μ=${plotdata.mean}<br>σ=${plotdata.stddev}` +
										`<br><br>${xlbl}=%{x}<br>${ylbl}=%{y}` +
										`<extra></extra>`
								};
								normdistline.legendgroup = normdistline.name;
								normdistline.line = {color: '#331100'};

								var refnormdistline = {
									x: x,
									y: normdist(x, 0, 1),
									type: 'scatter',
									mode: 'lines',
									name: 'Normal distribution (μ=0, σ=1)',
									hovertemplate: `Standard normal distribution (μ=0, σ=1)` +
										`<br>${xlbl}=%{x}<br>${ylbl}=%{y}<extra></extra>`
								};
								refnormdistline.legendgroup = refnormdistline.name;
								refnormdistline.line = {color: '#999999'};

								var traces = [mainTrace, normdistline, refnormdistline];

							}else if(hasMedian){

								var [min, max] = endpoints(plotdata.yvalues);
								var medianline = {
									x: [plotdata.median, plotdata.median],
									y: [0, max],
									type: 'scatter',
									mode: 'lines',
									name: 'Median LH',
									hovertemplate: `${gsim} median<br>${xlbl}=${plotdata.median}<extra></extra>`
								};
								medianline.legendgroup = medianline.name;
								medianline.line = {color: '#331100', dash: 'dot'};

								var traces = [mainTrace, medianline];
							}
						}
						var plotparams = {model: gsim, imt: imt, 'residual type': type};
						plots.push({
							data: traces,
							params: plotparams,
							layout: {
								xaxis: {
									title: plotdata.xlabel,
									type: 'linear'
								},
								yaxis: {
									title: plotdata.ylabel,
									type: 'linear'
								}
							}
						});
					}
				}
			}
			return plots;
		}
	},
	computed: {  // "override" computed property from superclass
		legendNames(){
			// override legendNames property by ordering legend names so that statistics labels
			// are placed at the bottom:
			var names = Object.keys(this.legend);
			var statKeys = new Set(['Median LH', 'Normal distribution', 'Normal distribution (μ=0, σ=1)',
				'Linear regression' ]);
			var resTypes = names.filter(element => !statKeys.has(element));
			var statTypes = names.filter(element => statKeys.has(element));
			return resTypes.concat(statTypes);
		}
	}
});