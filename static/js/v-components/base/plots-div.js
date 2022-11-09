/* Base class to be used as mixin for any component showing plots as a result
of a response Object sent from the server */
var PlotsDiv = {
	mixins: [DataDownloader],
	props: {
		data: {type: Object, default: () => { return {} }},
		downloadUrl: String // base url for download actions
	},
	data(){
		return {
			// boolean visualizing a div while drawing (to prevent user clicking everywhere for long taks):
			drawingPlots: false,
			// an Array of [legendgroup:str, traceProperties:Object] elements:
			legend: [],
			// An Array of Param Objects for laying out plots. Each param has at least the function indexOf(plot, idx, plots)
			// and optionally a value:Array key and a name:str key. If the latter are provided, then the param
			// is displayable as label on the plot grids
			params: [],
			// dict of subplots layout name (string) mapped to an Array of two params dictating the layout.
			// Params are those implemented in params (se above) or other dummy params created in `setoSelection`
			gridlayouts: {},
			// string denoting the selected layout name of gridlayouts (see above)
			selectedgridlayout: '',
			// plot options configurable via html controls:
			plotoptions: {
				axis: {
					x: {
						log: {disabled: false, value: undefined},
						sameRange: {disabled: false, value: undefined},
						grid: {disabled: false, value: undefined}
					} ,
					y: {
						log: {disabled: false, value: undefined},
						sameRange: {disabled: false, value: undefined},
						grid: {disabled: false, value: undefined}
					}
				},
				mouse: {
					hovermode: 'closest',  // will set this value to the Plotly layout before plotting, if not explicitly set
					dragmode: 'zoom'  // will set this value to the Plotly layout before plotting, if not explicitly set
				}
			},
			// the wait bar while drawing plots
			waitbar: {
				msg: '',  // the message to be displayed, and below some defaults:
				DRAWING: 'Drawing plots... <i class="fa fa-hourglass-o"></i>',
				UPDATING: 'Updating plots... <i class="fa fa-hourglass-o"></i>'
			}
		}
	},
	created(){
		// setup non reactive data:
		this.plots = [];  // populated in `init`
		// define default font and infer from page if possible:
		var font = {
			family: 'Helvetica, Arial, sans-serif',
			size: 16
		};
		var fontf = window.getComputedStyle(document.getElementsByTagName('body')[0]).getPropertyValue('font-family');
		if (typeof fontf === 'string' && !!fontf){
			font.family = fontf;
		}
		var fonts = parseInt(window.getComputedStyle(document.getElementsByTagName('body')[0]).getPropertyValue('font-size'));
		if (typeof fonts === 'number' && !isNaN(fonts)){
			font.size = fonts;
		}
		// default Plotly layout
		this.defaultlayout = {
			autosize: true,  // without this, the inner svg does not expand properly FIXME HERE
			paper_bgcolor: 'rgba(0,0,0,0)',
			plot_bgcolor: 'rgba(255,255,255,1)',
			showlegend: false,
			legend: { bgcolor: 'rgba(0,0,0,0)'},
			margin: { r: 0, b: 0, t: 0, l: 0, pad: 0 },
			font: font,
			annotations: [],
			xaxis: {  // https://plotly.com/javascript/reference/layout/xaxis/#layout-xaxis
				zeroline: false,
				showline: true,
				linewidth: 1,
				linecolor: '#444',
				mirror: true,
				showgrid: true,
				gridwidth: 1,
				gridcolor: "#eee"
			},
			yaxis: {
				zeroline: false,
				showline: true,
				linewidth: 1,
				linecolor: '#444',
				mirror: true,
				showgrid: true,
				gridwidth: 1,
				gridcolor: "#eee",
			}
		};
		// options of the side panel to configure mouse interactions on the plots:
		this.mouseMode = { // https://plot.ly/python/reference/#layout-hovermode
			// hovermodes (plotly keys). Note that we remove the 'y' key because useless
			hovermodes: ["closest", "x", false],
			// the labels of hovermodes to be displayed. Copied from plotly modebar after visual test
			// (note that we remove  the value associated to 'y' because plotly does not implement it
			// and anyway, even providing a mapped label such as 'show y', tests revealed the mode was useless):
			hovermodeLabels: {closest: 'show closest point', x: 'compare data',false: 'do nothing'},
			dragmodes: ["zoom", "pan"],  // "select", "lasso" are useless. false does not seem to work (it's zoom)
			dragmodeLabels: {zoom: 'zoom', pan: 'pan'},
		};

		// the plotly config for plots. See
		// https://community.plot.ly/t/remove-options-from-the-hover-toolbar/130/14
		this.defaultplotlyconfig = {
			responsive: true,
			modeBarButtonsToRemove: ['sendDataToCloud', 'toImage'],
			displaylogo: false
		};

		this.colors = {
			_i: -1,
			_values: [
				'#1f77b4',  // muted blue
				'#ff7f0e',  // safety orange
				'#2ca02c',  // cooked asparagus green
				'#d62728',  // brick red
				'#9467bd',  // muted purple
				'#8c564b',  // chestnut brown
				'#e377c2',  // raspberry yogurt pink
				'#7f7f7f',  // middle gray
				'#bcbd22',  // curry yellow-green
				'#17becf'   // blue-teal
			],
			_cmap: {},
			get(key){  // return a new color mapped to key. Subsequent calls with `key` as argument return the same color
				if (!(key in this._cmap)){
					this._cmap[key] = this._values[(++this._i) % this._values.length];
				}
				return this._cmap[key];
			},
			rgba(hexcolor, alpha) {
				// Returns the corresponding 'rgba' string of `hexcolor` with the given alpha channel ( in [0, 1], 1:opaque)
				if (hexcolor.length == 4){
					var [r, g, b] = [hexcolor.substring(1, 2), hexcolor.substring(2, 3), hexcolor.substring(3, 4)];
					var [r, g, b] = [r+r, g+g, b+b];
				}else if(hexcolor.length == 7){
					var [r, g, b] = [hexcolor.substring(1, 3), hexcolor.substring(3, 5), hexcolor.substring(5, 7)];
				}else{
					return hexcolor;
				}
				var [r, g, b] = [parseInt(r, 16), parseInt(g, 16), parseInt(b, 16)];
				return `rgba(${r}, ${g}, ${b}, ${alpha})`;
			}
		};
	},
	activated(){  // when component become active

	},
	watch: {
		data: {
			immediate: true,
			handler(newval, oldval){
				if (typeof newval === 'object' && Object.keys(newval).length){
					this.init.call(this, newval);
				}
			}
		},
		params: {
			deep: true,
			handler (newval, oldval) {
				if(!this.drawingPlots){
					this.newPlot();
				}
			}
		},
		selectedgridlayout: function(newval, oldval){
			if(!this.drawingPlots){
				this.newPlot();
			}
		},
		'plotoptions.axis': {
			deep: true,
			handler(newval, oldval){
				if(this.drawingPlots){ return; }
				var [data, layout]  = this.getPlotlyDataAndLayout();
				var newLayout = this.setupAxisConfigurableProperties(data, layout);
				this.relayout(newLayout);
			}
		},
		'plotoptions.mouse': {
			deep: true,
			handler(newval, oldval){
				if(this.drawingPlots){ return; }
				this.relayout({ dragmode: newval });
			}
		},
	},
	computed: {
		isGridCusomizable(){
			return Object.keys(this.gridlayouts).length>1;
		}
	},
	template: `<div v-show='Object.keys(data).length' class='d-flex flex-row'>
		<div class="d-flex flex-column" style="flex: 1 1 auto">
			<div v-if="params.length" class='d-flex flex-row justify-content-around'>
				<template v-for='(param, index) in params'>
					<div v-if='param.label && param.value!==undefined && selectedgridlayout && !gridlayouts[selectedgridlayout].includes(param)'
						 class='d-flex flex-row align-items-baseline mb-3'
						 :class="index > 0 ? 'ms-2' : ''" style="flex: 1 1 auto">
						<span class='text-nowrap me-1'>{{ param.label }}</span>
						<select v-model="param.value" class='form-control' style="flex: 1 1 auto">
							<option v-for='value in param.values' :value="value">
								{{ value }}
							</option>
						</select>
					</div>
				</template>
			</div>
			<div class='position-relative' style="flex: 1 1 auto">
				<div :style='{display: drawingPlots ? "flex" : "none"}'
					 class='position-absolute start-0 top-0 end-0 bottom-0 flex-column align-items-center justify-content-center'
					 style='z-index:1001;background-color:rgba(0,0,0,0.0)'>
					<div class='p-2 shadow border rounded text-white d-flex flex-column align-items-center'
						 style="background-color:rgba(0,0,0,0.3)">
						<span v-html="waitbar.msg" class='border-0 bg-transparent' style="font-size:200%;"></span>
						<span class='border-0 bg-transparent'>(It might take a while, please wait)</span>
					</div>
				</div>
				<div class='position-absolute start-0 top-0 end-0 bottom-0' ref='rootDiv'
					 :id="'plot-div-' + new Date().getTime() + Math.random()"></div>
			</div>
		</div>
		<!-- RIGHT TOOLBAR (legend, buttons, controls) -->
		<div class='d-flex flex-column ps-4' v-show="legend.length || isGridCusomizable">
			<slot></slot> <!-- slot for custom buttons -->
			<div v-show='legend.length' class='mt-3 border p-2 bg-white px-1'
				 style='flex: 1 1 auto;overflow: auto'>
				<div>Legend</div>
				<div v-for="l in legend" class='d-flex flex-column'>
					<div class='d-flex flex-row align-items-baseline'  getLegendColor
						 :style="{color: getLegendColor(l[1])}">
						<label class='my-0 mt-2 text-nowrap' :class="{'checked': l[1].visible}"
							style='flex: 1 1 auto'>
							<input type='checkbox' v-model="l[1].visible"  getLegendColor
								   :style="{'accent-color': getLegendColor(l[1]) + ' !important'}"
								   @change="setTraceStyle(l[0], l[1])"> {{ l[0] }}
						</label>

						<div data-balloon-pos="left" data-balloon-length="small" class='ms-1'
						     aria-label='Style the plot traces (lines, bars, markers) of this legend group'>
							<i class="fa fa-chevron-down" style="cursor:pointer"
							   onclick='this.parentNode.parentNode.parentNode.querySelector("div._pso").classList.toggle("d-none"); this.classList.toggle("fa-chevron-up"); this.classList.toggle("fa-chevron-down")'></i>
						</div>
					</div>
					<div class='_pso d-flex flex-column d-none'>
						<textarea class='border' spellcheck="false"
								  style='margin:0px;padding:0px !important; height: 12rem;font-family:monospace; white-space: pre; overflow-wrap: normal; overflow-x: scroll; z-index:100; background-color: #f5f2f0;'
								  v-model="l[2]"/>
						<button type="button" class='mt-1 btn btn-sm' :disabled="!jsonParse(l[2])"
								@click="setTraceStyle(l[0], jsonParse(l[2]))"
								:style="{color: getLegendColor(l[1]), 'border-color': getLegendColor(l[1])}">Apply</button>
					</div>
				</div>
			</div>
			<div>
				<div class='mt-3 border p-2 bg-white'>
					<select @change="downloadTriggered" class='form-control'
							data-balloon-pos='left' data-balloon-length='medium'
							aria-label='Download the computed results in different formats. Notes: EPS images do not support color transparency, the result might not match what you see'>
						<option value="">Download as:</option>
						<option value="json">json</option>
						<option value="csv">text/csv</option>
						<option value="csv_eu">tex/csv (decimal comma)</option>
						<option value="png">png (visible plots only)</option>
						<option value="pdf">pdf (visible plots only)</option>
						<option value="eps">eps (visible plots only)</option>
						<option value="svg">svg (visible plots only)</option>
					</select>
				</div>
				<div v-show="isGridCusomizable" class='mt-3 border p-2 bg-white'>
					<div>Subplots layout</div>
					<select v-model='selectedgridlayout' class='form-control mt-1'>
						<option v-for='key in Object.keys(gridlayouts)' :value="key" v-html="key">
						</option>
					</select>
				</div>
				<div class='mt-3 d-flex flex-column border p-2 bg-white'>
					<div>Axis</div>
					<div v-for="(axiscontrol, idx) in [plotoptions.axis.x, plotoptions.axis.y]"
					     class='d-flex flex-row mt-1 text-nowrap align-items-baseline'>
						<span class='text-nowrap'>{{ idx == 0 ? 'x' : 'y' }}:</span>
						<label class='text-nowrap m-0 ms-2'
							   :class="{'checked': axiscontrol.sameRange.value}"
							   :disabled="axiscontrol.sameRange.disabled">
							<input type='checkbox' v-model='axiscontrol.sameRange.value'
								   :disabled="axiscontrol.sameRange.disabled"  class="me-1">
							<span>same range</span>
						</label>
						<label class='text-nowrap m-0 ms-2'
							   :class="{'checked': axiscontrol.log.value}"
							   :disabled="axiscontrol.log.disabled">
							<input type='checkbox' v-model='axiscontrol.log.value'
								   :disabled="axiscontrol.log.disabled" class="me-1">
							<span>log scale</span>
						</label>
						<label class='text-nowrap m-0 ms-2'
							   :class="{'checked': axiscontrol.grid.value}"
							   :disabled="axiscontrol.grid.disabled">
							<input type='checkbox' v-model='axiscontrol.grid.value'
								   :disabled="axiscontrol.grid.disabled" class="me-1">
							<span>grid</span>
						</label>
					</div>
				</div>
				<div class='mt-3 d-flex flex-column border p-2 bg-white'>
					<div> Mouse interactions</div>
					<div class='d-flex flex-row mt-1 align-items-baseline'>
						<span class='text-nowrap me-1'> on hover:</span>
						<select v-model="plotoptions.mouse.hovermode"
								class='form-control form-control-sm'>
							<option v-for='name in mouseMode.hovermodes' :value='name'>
								{{ mouseMode.hovermodeLabels[name] }}
							</option>
						</select>
					</div>
					<div class='d-flex flex-row mt-1 align-items-baseline'>
						<span class='text-nowrap me-1'> on drag:</span>
						<select v-model="plotoptions.mouse.dragmode"
								class='form-control form-control-sm'>
							<option v-for='name in mouseMode.dragmodes' :value='name'>
								{{ mouseMode.dragmodeLabels[name] }}
							</option>
						</select>
					</div>
				</div>
			</div>
		</div>
	</div>`,
	methods: {
		getPlots(responseObject){
			/* METHOD TO BE SUBCLASSED: return from the given response object an Array of Objects representing
			the sub-plot to be visualized. Each sub-plot Object has the form:
			{data: Array, layout: Object, params: Object}
			See README, residuals.js and trellis.js for a details docstring and implementation
			*/
		},
		init(jsondict){
			this.legend = {};
			// convert data:
			this.plots = this.getPlots(jsondict);
			this.drawingPlots = true;
			// update selection, taking into account previously selected stuff:
			this.setupParams();
			this.createLegend();
			// now plot:
			this.newPlot();
		},
		setupParams(){
			var plots = this.plots;
			// sets up the params implemented on each plot. Params are used to select
			// specific plots to show, or to layout plots on a XY grid
			var paramvalues = new Map();
			plots.forEach(plot => {
				var plotParams = plot.params || {};
				for (var paramName of Object.keys(plotParams)){
					if(!paramvalues.has(paramName)){
						paramvalues.set(paramName, new Set());
					}
					paramvalues.get(paramName).add(plotParams[paramName]);
				}
			});
			// create an Array of params object (params mapped to a single value are discarded):
			var params = [];
			paramvalues.forEach((pvalues, pname) => {
				if(pvalues.size > 1){
					var values = Array.from(pvalues);
					if (values.some(v => v!==null) && values.every(v => v === null || typeof v === 'number')){
						values.sort((a, b) => b===null ? 1 : (a===null ? -1 : a - b));  // https://stackoverflow.com/a/1063027
					}else{
						values.sort();
					}
					params.push({
						values: values,
						label: pname,
						value: values[0],
						indexOf(plot, idx, plots){
							return this.values.indexOf(plot.params[this.label]);
						}
					});
				}
			});

			// dummy params that might be added below. It has no label (=>cannot be on the grid)
			// and no value (=>cannot be selectable via <select> controls)
			var singleParam = {
				values: [''],  // Array of empty values (just to calculate plots width/height)
				indexOf(plot, idx, plots){
					return 0;
				}
			};

			var gridlayouts = {};
			var selectedgridlayout = '';
			var varr = '&udarr;';  // vartical arrow character
			var harr = '&rlarr;';  // horiontal arrow character
			if (params.length == 0){
				if (plots.length == 1){
					// config this Vue Component with a 1x1 grid of plots non selectable and with no grid labels:
					params = [singleParam, singleParam];
					selectedgridlayout = '---';  // any value is irrelevant
					gridlayouts[selectedgridlayout] = [singleParam, singleParam];
				}else{
					// config this Vue Component with two selectable 1xn or nx1 grids of plots,
					// but without grid labels:
					var multiParam = {
						values: plots.map(elm => ''), // Array of empty values (just to calculate plots width/height)
						indexOf(plot, idx, plots){
							return idx;
						}
					};
					params = [multiParam, singleParam];
					selectedgridlayout = `${varr} stack vertically`;
					gridlayouts[selectedgridlayout] = [singleParam, multiParam];
					gridlayouts[`${harr} stack horizontally`] = [multiParam, singleParam];
				}
			}else{
				// always provide a grid option selecting a single plot:
				gridlayouts['single plot'] = [singleParam, singleParam];
				if (params.length == 1){
					// config this Vue Component with two selectable 1xn or nx1 grids of plots,
					// with the grid labels displayed according to the only param:
					selectedgridlayout = `${varr} ${params[0].label}`;
					gridlayouts[selectedgridlayout] = [singleParam, params[0]];
					gridlayouts[`${harr} ${params[0].label}`] = [params[0], singleParam];
				}else{
					// config this Vue Component with n>2 selectable grids of plots,
					// with the grid labels displayed according to the selected params:
					for (var prm1 of params){
						for (var prm2 of params){
							if (prm1 === prm2){
								continue;
							}
							var gridlayoutname = `${harr} ${prm1.label} vs. ${varr} ${prm2.label}`;
							gridlayouts[gridlayoutname] = [prm1, prm2];
							if (!selectedgridlayout){ // take the first combination as selected one:
								selectedgridlayout = gridlayoutname;
							}
						}
					}
				}
			}
			// set defaults:
			this.gridlayouts = gridlayouts;
			this.selectedgridlayout = selectedgridlayout;
			this.params = params;
		},
		newPlot(){  // redraw completely the plots
			this.drawingPlots = true;
			this.waitbar.msg = this.waitbar.DRAWING;
			setTimeout(() => {
				var divElement = this.$refs.rootDiv;
				var [data, layout] = this.setupPlotlyDataAndLayout();
				Plotly.newPlot(divElement, data, layout, this.defaultplotlyconfig);
				// now compute labels and ticks size:
				var newLayout = this.setupAxisDomainsAndGridLabels(layout);
				Plotly.relayout(divElement, newLayout);
				this.drawingPlots = false;
			}, 150);
		},
		relayout(newLayout){  // Redraw the plot layout (anything but data)
			this.drawingPlots = true;
			this.waitbar.msg = this.waitbar.UPDATING;
			setTimeout(() => {
				Plotly.relayout(this.$refs.rootDiv, newLayout || {});
				this.drawingPlots = false;
			}, 100);
		},
		restyle(newData, traceIndices){  // Redraw the plot data
			this.drawingPlots = true;
			this.waitbar.msg = this.waitbar.UPDATING;
			setTimeout(() => {
				Plotly.restyle(this.$refs.rootDiv, newData, traceIndices);
				this.drawingPlots = false;
			}, 100);
		},
		setupPlotlyDataAndLayout(){
			var plots = this.plots;
			var [gridxparam, gridyparam] = this.gridlayouts[this.selectedgridlayout];
			// filter plots according to the value of the parameter which are not displayed as grid param:
			for (var param of this.params){
				if (param === gridxparam || param === gridyparam || param.value === undefined){
					continue;
				}
				plots = plots.filter(plot => plot.params[param.label] == param.value);
			}

			// now build an array the same length as plots with each element the grids position [index_x, index_y]
			var gridxindices = plots.map((plot, idx, plots) => gridxparam.indexOf(plot, idx, plots));
			var gridyindices = plots.map((plot, idx, plots) => gridyparam.indexOf(plot, idx, plots));

			// initialize our layout Object (see plotly doc for details):
			var layout = Object.assign({}, this.defaultlayout, {
				hovermode: this.plotoptions.mouse.hovermode,
				dragmode: this.plotoptions.mouse.dragmode
			});
			var data = [];
			// compute rows, cols, and margins for paramsGrid labels:
			var cols = gridxparam.values.length || 1;
			var rows = gridyparam.values.length || 1;

			var legendgroups = new Set();
			for (var i = 0; i < plots.length; i++){
				var plot = plots[i];
				var plotLayout = plot.layout || {};
				// Before merging plotLayout into `layout`, keep track of its xaxis and yaxis Objects:
				var xaxis = Object.assign({}, this.defaultlayout.xaxis || {}, plotLayout.xaxis || {});
				var yaxis = Object.assign({}, this.defaultlayout.yaxis || {}, plotLayout.yaxis || {});
				// merge plot layout keys into main layout:
				Object.assign(layout, plotLayout);
				// Edit xaxis and yaxis:
				if (xaxis.title){
					if(typeof xaxis.title !== 'object'){
						xaxis.title = {text: `${xaxis.title}`};
					}
					xaxis.title.standoff = 10; // space between label and axis
				}
				if (yaxis.title){
					if(typeof yaxis.title !== 'object'){
						yaxis.title = {text: `${yaxis.title}`};
					}
					yaxis.title.standoff = 5; // space between label and axis
				}
				// compute axis domains (assure the second domain element is 1 and not, e.g., 0.9999):
				var gridxindex = gridxindices[i];
				var gridyindex = gridyindices[i];
				var xdomain = [gridxindex*(1.0/cols), (1+gridxindex)*(1.0/cols)];
				var ydomain = [gridyindex*(1.0/rows), (1+gridyindex)*(1.0/rows)];
				// Add to the layout xaxis and yaxis, with specific key:
				var axisIndex = 1 + gridyindex * cols + gridxindex;
				layout[`xaxis${axisIndex}`] = Object.assign(xaxis, { domain: xdomain, anchor: `y${axisIndex}` });
				layout[`yaxis${axisIndex}`] = Object.assign(yaxis, { domain: ydomain, anchor: `x${axisIndex}` });
				// Map all traces to the axis just created on the layout:
				plot.data.forEach((trace) => {
					trace.xaxis = `x${axisIndex}`;
					trace.yaxis = `y${axisIndex}`;
					// this is necessary only if we show the plotly legend (we don't)
					// in order to avoid duplicated entries on the plotly legend:
					if ('legendgroup' in trace){
						trace.showlegend = !legendgroups.has(trace.legendgroup);
						legendgroups.add(trace.legendgroup);
					}
					data.push(trace);
				});
			}
			// add grid tick labels in form text placed on the plot (Plotly annotations).
			// The annotations position is only relevant to retrieve their <svg> elements
			// later (see `this.getPaperMargin`). As such just place x grid labels on the
			// left and y grid labels on the right. Prefer x because plotly y coordinates
			// are cartesian (y increases upwards) and <svg> not (y increases downwards)
			layout.annotations = [];
			for (var i=0; i < gridxparam.values.length; i++){
				layout.annotations.push(this.createGridAnnotation({
					text: `${gridxparam.values[i]}`,
					x: 0
				}));
			}
			for (var i=0; i < gridyparam.values.length; i++){
				layout.annotations.push(this.createGridAnnotation({
					text: `${gridyparam.values[i]}`,
					x: 1
				}));
			}
			// delete xaxis and yaxis on layout, as they are meaningless (their values
			// are merged into each layout.xaxisN, layout.yaxisN Objects)
			delete layout.xaxis;
			delete layout.yaxis;
			var newLayout = this.setupAxisConfigurableProperties(data, layout);
			for(key of Object.keys(newLayout)){
				var keys = key.split('.');
				if(keys.length == 2){
					layout[keys[0]][keys[1]] = newLayout[key];
				}
			}
			return [data, layout];
		},
		createGridAnnotation(props){
			var annotation = {
				xref: 'paper',
				yref: 'paper',
				showarrow: false,
				bgcolor: 'rgba(255,255,255,0)',
				borderwidth: 0,
				bordercolor: 'rgba(255,255,255,0)'
			};
			return Object.assign(annotation, props || {});
		},
		setupAxisConfigurableProperties(data, layout){
			// return a new Object to be passed to `Plotly.relayout` with the axis properties
			// that are configurable (see `this.plotoptions`)
			var newLayout = {};
			for (var ax of ['x', 'y']){
				var axisControl = ax == 'x' ? this.plotoptions.axis.x : this.plotoptions.axis.y;
				// get all layout['xaxis'], layout['xaxis1'] and so on. These are Objects
				// representing all plots x axis (same for 'y' the next loop):
				var regexp = ax == 'x' ? /^xaxis\d*$/g : /^yaxis\d*$/g;
				var axis = Object.keys(layout).filter(key => regexp.exec(key));

				// set grid on/off
				if (axisControl.grid.value === undefined){
					axisControl.grid.disabled = true;
					// set control from data:
					if (axis.every(a => layout[a].showgrid || layout[a].showgrid === undefined)){
						axisControl.grid.disabled = false;
						axisControl.grid.value = true;
					}else if (axis.every(a => a.showgrid === false)){
						axisControl.grid.disabled = false;
						axisControl.grid.value = false;
					}
				}else{
					// set data from control:
					axis.forEach(a => newLayout[`${a}.showgrid`] = !!axisControl.grid.value);
				}

				// set log / linear (not log). Note that non numeric data (e.g. category) disabled the control
				if (axisControl.log.value === undefined){
					axisControl.log.disabled = true;
					// set control from data:
					if (axis.every(a => layout[a].type === 'log')){
						// if all axes are log type, then set the checkbox value first:
						axisControl.log.value = true;
						axisControl.log.disabled = false;
					}else if (axis.every(a => layout[a].type === 'linear')){
						// if all axes are linear type, then set the type according to the checkbox:
						axisControl.log.disabled = false;
						axisControl.log.value = false;
					}else if (axis.every(a => layout[a].type === undefined || layout[a].type === '-')){
						// undefined and '-' are plotly default for: infer. Let's do the same:
						if (data.every(trace => (ax in trace) && trace[ax].every(v => typeof v === 'number'))){
							axisControl.log.disabled = false;
							axisControl.log.value = false;
						}
					}
				}else{
					axis.forEach(a => newLayout[`${a}.type`] = axisControl.log.value ? 'log': 'linear');
				}

				// set the range
				if (axisControl.sameRange.value === undefined){
					// set control from data:
					axisControl.sameRange.disabled = axisControl.log.disabled ||
						axis.some(a => a.range !== undefined);
				}else{
					// set data from control:
					if(!axisControl.sameRange.value){
						// Provide a 'delete range key' command by setting it undefined (infer range):
						axis.forEach(a => newLayout[`${a}.range`] = undefined);
					}else{
						var range = [Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY];
						data.forEach(trace => {
							var values = (trace[ax] || []).filter(v => typeof v === 'number' && !isNaN(v));
							if(values.length){
								range = [Math.min(...values, range[0]), Math.max(...values, range[1])];
							}
						});
						if (range[0] < range[1]){
							// add margins for better visualization:
							var margin = Math.abs(range[1] - range[0]) / 50;
							// be careful with negative logarithmic values:
							if (!axisControl.log.value || (range[0] > margin && range[1] > 0)){
								range[0] -= margin;
								range[1] += margin;
							}
							// set computed ranges to all plot axis:
							axis.forEach(a => newLayout[`${a}.range`]  = axisControl.log.value ? [Math.log10(range[0]), Math.log10(range[1])] : range);
						}
					}
				}
			}
			return newLayout;
		},
		setupAxisDomainsAndGridLabels(layout){
			// return a new Object to be passed to `Plotly.relayout` with the axis domains
			// (positions) re-adjusted to account for axis ticks and label size, and, if
			// needed, the Plotly annotations, i.e.the grid labels resulting from the
			// currently selected grid parameters
			var newLayout = {};
			for (var key of Object.keys(layout)){
				if ((key.startsWith('xaxis') || key.startsWith('yaxis')) && Array.isArray(layout[key].domain)){
					newLayout[`${key}.domain`] = Array.from(layout[key].domain);
				}
			}
			var axisKeys = Array.from(Object.keys(newLayout));
			// paper margin:
			var [gridxparam, gridyparam] = this.gridlayouts[this.selectedgridlayout];
			var xdomains = gridxparam.label ? new Array(gridxparam.values.length) : [];
			var ydomains = gridyparam.label ? new Array(gridyparam.values.length) : [];
			var cols = Math.max(xdomains.length, 1);
			var rows = Math.max(ydomains.length, 1);
			var papermargin = this.getPaperMargin();
			var plotmargin = this.getPlotsMaxMargin();
			// roughly get row height from min of papermargin, which should be the height of x axis
			if (gridxparam.label || gridyparam.label){
				var [w, h] = this.getElmSize(this.$refs.rootDiv);
				var [fontwidth, fontheight] = [layout.font.size / w, layout.font.size / h];
				if (gridxparam.label){ papermargin.left += 5 * fontwidth; }
				if (gridyparam.label){ papermargin.bottom += 5 * fontheight; }
			}
			for (var key of axisKeys){
				var [col, row] = this.getPlotGridPosition(key);
				var width = (1 - papermargin.left - papermargin.right - cols*(plotmargin.left + plotmargin.right))/cols;
				var height = (1 - papermargin.top - papermargin.bottom - rows*(plotmargin.top + plotmargin.bottom))/rows;
				if (key.startsWith('x')){
					var x0 = papermargin.left + (col +1 ) * plotmargin.left + col * (width + plotmargin.right);
					newLayout[key] = [x0, x0 + width];
					if (row == 0){
						xdomains[col] = newLayout[key];  // store to put grid labels and ticks (see below)
					}
				}else{
					var y0 = papermargin.bottom + (row + 1) * plotmargin.bottom + row * (height + plotmargin.top);
					newLayout[key] = [y0, y0 + height];
					if (col == 0){
						ydomains[row] = newLayout[key];  // store to put grid labels and ticks (see below)
					}
				}
			}
			newLayout.shapes = [];
			newLayout.annotations = [];
			if (gridxparam.label || gridyparam.label){
				papermargin.left -= 2*fontwidth;
				papermargin.bottom -= 2*fontheight;
				newLayout.shapes = this.getGridLines(xdomains, ydomains, papermargin);
				papermargin.left -= .5*fontwidth;
				papermargin.bottom -= .5*fontheight;
				var annotations = this.getGridTickLabels(xdomains, ydomains, papermargin);
				newLayout.annotations = annotations.concat(this.getGridLabels(xdomains, ydomains, papermargin));
			}
			return newLayout;
		},
		getPlotsMaxMargin(){
			// Return an object representing the max margin to be applied to each individual plot,
			// where each plot margin is computed subtracting the outer axes rectangle
			// (plot area + axis ticks and ticklabels area) and the inner one
			var margin = { top: 20, bottom: 0, right: 10, left: 0 };
			var [min, max, abs] = [Math.min, Math.max, Math.abs];
			var plotDiv = this.$refs.rootDiv;
			var certesianLayer = plotDiv.querySelector('g.cartesianlayer');
			var infoLayer = plotDiv.querySelector('g.infolayer');
			for (var elm of certesianLayer.querySelectorAll('g[class^=subplot]')){
				// get plot index from classes of type 'xy' 'x2y2' and so on:
				var xindex = '';
				var yindex = '';
				var re = /^(x\d*)(y\d*)$/g;
				for (var cls of elm.classList){
					var matches = re.exec(cls);
					if (matches){
						xindex = matches[1];
						yindex = matches[2];
						break;
					}
				}
				if (!xindex || !yindex){
					continue;
				}
				var innerPlotRect = elm.querySelector(`path.ylines-above.crisp`) || elm.querySelector(`path.xlines-above.crisp`);
				if(!innerPlotRect){
					continue;
				}
				innerPlotRect = innerPlotRect.getBBox();

				// try to find the xlabel, otherwise get the xticks+xticklabels:
				var xlabel = infoLayer.querySelector(`g[class=g-${xindex}title]`) || elm.querySelector('g.xaxislayer-above');
				if (xlabel){
					var xElm = xlabel.getBBox();
					margin.bottom = max(margin.bottom, xElm.y + xElm.height - innerPlotRect.y - innerPlotRect.height);
				}
				// try to find the ylabel, otherwise get the yticks+yticklabels:
				var ylabel =  infoLayer.querySelector(`g[class=g-${yindex}title]`)  || elm.querySelector('g.yaxislayer-above');
				if (ylabel){
					var yElm = ylabel.getBBox();
					// margin.top = max(margin.top, axesRect.y - yElm.y);
					margin.left = max(margin.left, innerPlotRect.x - yElm.x);
				}
			}
			var [width, height] = this.getElmSize(this.$refs.rootDiv);
			margin.left /= width;
			margin.right /= width;
			margin.top /= height;
			margin.bottom /= height;
			return margin;
		},
		getPaperMargin(){
			var plotDiv = this.$refs.rootDiv;
			var [width, height] = this.getElmSize(plotDiv);
			var margin = {top: 2.0/height, bottom: 2.0/height, left: 2.0/width, right: 2.0/width};
			var [gridxparam, gridyparam] = this.gridlayouts[this.selectedgridlayout];
			if (!gridxparam.label && !gridyparam.label){
				return margin;
			}
			var infoLayer = plotDiv.querySelector('g.infolayer');
			var annotations = Array.from(infoLayer.querySelectorAll(`g[class=annotation]`));
			if(gridxparam.label){
				// get the x annotations, recognizable as those with lower x:
				var num = gridxparam.values.length;
				var annots = annotations.sort((a, b) => (a.getBBox().x - b.getBBox().x)).slice(0, num);
				margin.bottom = Math.max(margin.bottom, Math.max(...annots.map(elm => elm.getBBox().height)) / height);
			}
			if(gridyparam.label){
				// get the y annotations, recognizable as those with higher x:
				var num = annotations.length - gridyparam.values.length;
				var annots = annotations.sort((a, b) => (a.getBBox().y - b.getBBox().y)).slice(num);
				margin.left = Math.max(margin.left, Math.max(...annots.map(elm => elm.getBBox().width)) / width);
			}
			return margin;
		},
		getPlotGridPosition(axisKey){
			// return the current grid position [xIndex, yIndex] of the plot associated
			// to the string `axisKey`, which is a plotly layout key of the form:
			// /[xy]axis\d*/ (where "xaxis" in plotly equals "xaxis1"). xIndex and yIndex
			// are in cartesian coordinates, so [0, 0] denotes the bottom-left plot,
			// [1, 0] the plot on its right, [0, 1] the plot above it, and so on
			var [gridxparam, gridyparam] = this.gridlayouts[this.selectedgridlayout];
			var cols = gridxparam.values.length || 1;
			var rows = gridyparam.values.length || 1;
			if (cols == 1 && rows == 1){
				return [0, 0];
			}
			// plotly.relayout accepts keys such as "[xy]axis.[subset]", e.g. "xaxis.domain"
			// in that case, split(".")[0] assures we get rid of everything after a dot (if any):
			var axisIndex = parseInt(axisKey.split('.')[0].substring(5) || 1);  // xaxis.domain -> '', yaxis3.domain -> 3, and so on ...
			var col = (axisIndex - 1) % cols;
			var row = parseInt((axisIndex - 1) / cols);
			return [col, row];
		},
		getGridLabels(xdomains, ydomains, papermargin){
			// return an Array of zero to two Objects representing the plots grid labels.
			// xdomains and ydomains are arrays denoting the space reserved by the grid
			// columns and rows: xdomains returns the horizontal space taken by the lower
			// left plot (index 0) up to the rightmost plot (last index) on the same row,
			// whereas ydomains[0] returns the vertical space of the lower left plot
			// (index 0) up to the uppermost plot (last index) on the same column. Each
			// domain represents the space as an Array of two numbers [start, end], both
			// in [0, 1], i.e. relative to the plotly "paper" (the root <div>)
			var annotations = [];
			var [gridxparam, gridyparam] = this.gridlayouts[this.selectedgridlayout];
			if (gridxparam.label){
				annotations.push(this.createGridAnnotation({
					text: `${gridxparam.label}`,
					y: 0,
					yanchor: 'bottom',
					x: (xdomains[0][0] + xdomains[xdomains.length-1][1]) / 2,
					xanchor: 'center'
				}));
			}
			if (gridyparam.label){
				annotations.push(this.createGridAnnotation({
					text: `${gridyparam.label}`,
					x: 0,
					xanchor: 'left',
					y: (ydomains[0][0] + ydomains[ydomains.length-1][1]) / 2,
					yanchor: 'middle',
					textangle: -90,
				}));
			}
			return annotations;
		},
		getGridTickLabels(xdomains, ydomains, papermargin){
			// return an Array of columns*rows Objects representing the plots grid ticklabels.
			// xdomains and ydomains are arrays denoting the space reserved by the grid
			// columns and rows: xdomains returns the horizontal space taken by the lower
			// left plot (index 0) up to the rightmost plot (last index) on the same row,
			// whereas ydomains[0] returns the vertical space of the lower left plot
			// (index 0) up to the uppermost plot (last index) on the same column. Each
			// domain represents the space as an Array of two numbers [start, end], both
			// in [0, 1], i.e. relative to the plotly "paper" (the root <div>)
			var annotations = [];
			var [gridxparam, gridyparam] = this.gridlayouts[this.selectedgridlayout];
			if (gridxparam.label){
				for(var i =0; i < gridxparam.values.length; i ++){
					var domain = xdomains[i];
					annotations.push(this.createGridAnnotation({
						text: `${gridxparam.values[i]}`,
						y: papermargin.bottom,
						yanchor: 'top',
						x: (domain[1] + domain[0]) / 2,
						xanchor: 'center'
					}));
				}
			}
			if (gridyparam.label){
				for(var i =0; i < gridyparam.values.length; i ++){
					var domain = ydomains[i];
					annotations.push(this.createGridAnnotation({
						text: `${gridyparam.values[i]}`,
						x: papermargin.left,
						xanchor: 'right',
						y: (domain[1] + domain[0]) / 2,
						yanchor: 'center',
					}));
				}
			}
			return annotations;
		},
		getGridLines(xdomains, ydomains, papermargin){
			// Now the grid, if present.
			// add lines (plotly shapes):
			var defShape = {
				xref: 'paper',
				yref: 'paper',
				line: {
					color: '#444',
					width: 1
				}
			};
			var shapes = [];
			var [gridxparam, gridyparam] = this.gridlayouts[this.selectedgridlayout];
			if (gridxparam.label){  // horizontal grid line
				shapes.push(Object.assign({}, defShape, {
					x0: xdomains[0][0],
					x1: xdomains[xdomains.length-1][1],  // 1 - papermargin.right,
					y0: papermargin.bottom,
					y1: papermargin.bottom
				}));
			}
			if (gridyparam.label){  // vertical grid line
				shapes.push(Object.assign({}, defShape, {
					x0: papermargin.left,
					x1: papermargin.left,
					y0: ydomains[0][0],
					y1: ydomains[ydomains.length-1][1]  // 1 - papermargin.top
				}));
			}
			return shapes;
		},
		getElmSize(domElement){
			// returns the Array [width, height] of the given dom element size
			return [domElement.offsetWidth, domElement.offsetHeight];
		},
		createLegend(){
			this.legend = [];
			var legend = this.legend;
			var legendgroups = new Set();
			this.plots.forEach((plot, i) => {
				plot.data.forEach((trace) => {
					var legendgroup = trace.legendgroup;
					if (legendgroup && !legendgroups.has(legendgroup)){
						legendgroups.add(legendgroup);
						var legenddata = {visible: ('visible' in trace) ? !!trace.visible : true};
						for (var key of ['line', 'marker']){
							if (key in trace){
								legenddata[key] = Object.assign({}, trace[key]);
							}
						}
						legend.push([legendgroup, legenddata, JSON.stringify(legenddata, null, '  ')]);
					}
				});
			});
		},
		getLegendColor(legenddata){
			if (legenddata) {
				var marker = legenddata.marker;
				if (marker && marker.line && marker.line.color){
					return marker.line.color;
				}
				if (legenddata.line && legenddata.line.color){
					return legenddata.line.color;
				}
				if (marker && marker.color){
					return marker.color;
				}
			}
			return '#000000';
		},
		setTraceStyle(legendgroup, legenddata){
			if (!legenddata){ return; }
			for (var legend of this.legend){
				if(legend[0] === legendgroup){
					legend[1] = legenddata;
					legend[2] = JSON.stringify(legenddata, null, "  ")
				}
			}
			var indices = [];
			var plotlydata = this.getPlotlyDataAndLayout()[0];
			plotlydata.forEach(function(data, i){
				if (data.legendgroup === legendgroup){
					indices.push(i);
				}
			});
			if(indices.length){
				this.restyle(legenddata, indices);
			}
		},
		jsonParse(jsonString){
			try{
				return JSON.parse(jsonString);
			}catch(error){
				return null;
			}
		},
		getPlotlyDataAndLayout(){
			// returns the [data, layout] (Array, Object) currently displayed
			var elm = this.$refs.rootDiv;
			return elm ? [elm.data || [], elm.layout || {}] : [[], {}];
		},
		downloadTriggered(event){
			var selectElement = event.target;
			if (selectElement.selectedIndex == 0){
				return;
			}
			var format = selectElement.value;
			var url = this.downloadUrl + '.' + format;
			var data = this.data;
			if (format == 'json'){
				var filename =  url.split('/').pop();
				this.saveAsJSON(data, filename);
			} else if (format.startsWith('csv')){
				this.download(url, data);
			}else{
				// image format:
				var [data, layout] = this.getPlotlyDataAndLayout();
				var parent = this.$refs.rootDiv; //.parentNode.parentNode.parentNode;
				var [width, height] = this.getElmSize(parent);
				data = data.filter(elm => elm.visible || !('visible' in elm));
				postData = {data:data, layout:layout, width:width, height:height};
				this.download(url, postData);
			}
			selectElement.selectedIndex = 0;
		}
	}
};