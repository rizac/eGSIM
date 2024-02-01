/* Residuals plot components (model-to-data comparison) */

EGSIM.component('residuals', {
	props :{
		form: Object,
		url: String,
		// urls: Object, // object with to props: downloadRequest, downloadResponse (both string)
	},
	data() {
		return {
			responseData: {}
		}
	},
	template: `<div class='position-relative' style="flex: 1 1 auto;">
		<gsim-map @gsim-selected="(gs) => { form.gsim.value = Array.from(new Set(form.gsim.value.concat(gs))) }"
				  :regionalizations="form.gsim['data-regionalizations']"
				  style='position:absolute;inset:0px;z-index:0' />
		<form :form="form" :url="url" novalidate @submit.prevent="postData(url, form).then(r => { responseData = r; })"
			  class='d-flex flex-column ps-2' style='position:absolute;top:0px;bottom:0px;z-index:1'>
			<!-- css notes below: position makes z-index below work,
			z-index shows models popup in front of all other components -->
			<gsim-select :field="form.gsim" :imtField="form.imt"
						 class="mt-4 form-control pb-3 pt-2 position-relative"
						 style="z-index:1; flex: 0 1 auto;min-height:0px" />
			<imt-select :field="form.imt"
						class="my-4 form-control pb-3 pt-2 position-relative" />
			<div class="mb-4 form-control pb-3 pt-2 position-relative">
				<flatfile-select :field="form.flatfile"/>
				<flatfile-selexpr-input :field="form.selexpr" class='mt-3' />
			</div>

			<div class='d-flex flex-column'>
				<div> Model-to-data comparison </div>
				<div class='d-flex flex-row'>
					<button type='button' class='me-2 btn-btn-primary'>
						<i class="fa fa-bar-chart"></i> Show
					</button>
					<button type='button' class='me-2 btn-btn-primary'>
						<i class="fa fa-download"></i> Get
					</button>
					<button type='button' class='me-2 btn-btn-primary'>
						<i class="fa fa-download"></i> Get with tutorial
					</button>
					<button type='button' class='me-2 btn-btn-primary'>
						<i class="fa fa-download"></i> run in custom code
					</button>
				</div>
			</div>
		</form>

		<residuals-plot-div :data="responseData"
							class='invisible'
							style='position:absolute;inset:0px;z-index:10'
							:style="{visibility: Object.keys(responseData).length ? 'visible !important' : ''}">
		</residuals-plot-div>
	</div>`
});


// FIXME: REMOVE: attr of residuals-plot was: :download-url="urls.downloadResponse"

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
			var types = new Set();
			var gsims = new Set();
			// Get all residuals types and models (some might be missing):
			for (var imt of Object.keys(data)){
				for (var type of Object.keys(data[imt])){
					types.add(type);
					for (var gsim of Object.keys(data[imt][type])){
						gsims.add(gsim);
					}
				}
			}
			// iterate:
			for (var imt of Object.keys(data)){
				for (var type of types){
					for (var gsim of gsims){
						// setup plot for the case we do not have data (in most of the
						// cases these default Objects will be deleted or overwritten):
						var plotdata = {xlabel: "Data N/A", ylabel: ""};
						// note: adding an annotation (in layout.annotations) showing
						// "Data N/A" wpuld be better, but layout.annotations will be overwritten
						// when setting the grid labels (see plotdiv.js)
						var mainTrace = {
							x: [],
							y: [],
							name: type,
							// <extra></extra> hides the second tooltip (white):
							// hovertemplate: `${gsim}<br>${xlbl}=%{x}<br>${ylbl}=%{y}<extra></extra>`
						};
						mainTrace.legendgroup = mainTrace.name;
						var traces = [mainTrace];
						if (data[imt] && data[imt][type] && data[imt][type][gsim]){  // data exists
							var plotdata = data[imt][type][gsim];
							var hasLinearRegression = plotdata.intercept != null && plotdata.slope != null;
							var [xlbl, ylbl] = [plotdata.xlabel, plotdata.ylabel];
							var ptText = `${plotdata.xlabel}=%{x}<br>${plotdata.ylabel}=%{y}`;
							mainTrace.x = plotdata.xvalues;
							mainTrace.y = plotdata.yvalues;
							mainTrace.type = hasLinearRegression ? 'scatter' : 'bar';
							// <extra></extra> hides the second tooltip (white):
							mainTrace.hovertemplate = `${gsim}<br>${xlbl}=%{x}<br>${ylbl}=%{y}<extra></extra>`;
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
								traces.push(linregtrace);
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
									traces.push(normdistline, refnormdistline);
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
									traces.push(medianline);
								}
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