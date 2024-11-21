/* Base class to be used as mixin for any component showing plots as a result
of a response Object sent from the server */
EGSIM.component('plots-div', {
	props: {
		data: {type: [Array], default: () => { return [] }},
		downloadUrls: {type: Array, default: []}, // base url for download actions
		closeButton: {default: true}
	},
	emits: ['image-requested'],
	data(){
		return {
			// setup non reactive data:
			plots: [],  // populated in init`
			show: true,
			// boolean visualizing a div while drawing (to prevent user clicking everywhere for long taks):
			drawingPlots: false,
			// an Array of [legendgroup:str, traceProperties:Object] elements:
			legend: new Map(),
			// An Array of Param Objects for laying out plots. Each param has at least the function indexOf(plot, idx, plots)
			// and optionally a value:Array key and a name:str key. If the latter are provided, then the param
			// is displayable as label on the plot grids
			params: [],
			// subplots grid object:
			grid: {
				layouts: {}, // object of str mapped to an Array of 2 params: [x, y]
				selectedLayout: "",
				visibility: [true, true],  // x, y
				params: [{}, {}]  // Array of 2 params: [x, y]
			},
			// plot options configurable via html controls:
			plotoptions: {
				axis: {
					x: {
						log: {disabled: false, checked: undefined},
						sameRange: {disabled: false, checked: undefined, range: null},
						grid: {disabled: false, checked: undefined},  // plot x tick lines, not to be confused with this.grid
						title: {disabled: false, checked: undefined, title: ''}
					} ,
					y: {
						log: {disabled: false, checked: undefined},
						sameRange: {disabled: false, checked: undefined, range: null},
						grid: {disabled: false, checked: undefined},  // plot y tick lines, not to be confused with this.grid
						title: {disabled: false, checked: undefined, title: ''}
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
		// default Plotly layout (the `font` property will be set when page fonts are loaded, see init)
		this.defaultlayout = {
			autosize: true,  // without this, the inner svg does not expand properly
			paper_bgcolor: 'rgba(0,0,0,0)',
			plot_bgcolor: 'rgba(255,255,255,1)',
			showlegend: false,
			legend: { bgcolor: 'rgba(0,0,0,0)' },
			margin: { r: 0, b: 0, t: 0, l: 0, pad: 0 },
			annotations: [],
			xaxis: {  // https://plotly.com/javascript/reference/layout/xaxis/#layout-xaxis
				zeroline: false,
				showline: true,
				linewidth: 1,
				linecolor: '#444',
				mirror: true,
				showgrid: true,
				gridwidth: 1,
				gridcolor: "#eee",
				tickangle: 0
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
				tickangle: 0
			},
			hoverlabel:{
				namelength: -1  // show all tooltip text (no cut with ellipsis)
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
		this.doneCreated = true;
		this.init(this.data);
	},
	watch: {
		data: {
			handler(newVal, oldVal){
				if (this.doneCreated){
					this.init(newVal);
				}
			}
		},
		params: {
			deep: true,
			handler (newVal, oldVal) {
				this.updateGridParams();
				if(!this.drawingPlots){
					this.newPlot();
				}
			}
		},
		'grid.selectedLayout': function(newVal, oldVal){
			this.updateGridParams();
			if(!this.drawingPlots){
				this.newPlot();
			}
		},
		'grid.visibility': {
			deep: true,
			handler(newVal, oldVal){
				this.updateGridParams();
				if(!this.drawingPlots){
					var newLayout = {annotations: this.getGridLabels().concat(this.getGridTickLabels())};
					this.relayout(newLayout, true);
				}
			}
		},
		'plotoptions.axis': {
			deep: true,
			handler(newVal, oldVal){
				if(this.drawingPlots){ return; }
				var newLayout = this.updateLayoutFromCurrentAxisControls(...this.getPlotlyDataAndLayout());
				this.relayout(newLayout, true);
			}
		},
		'plotoptions.mouse': {
			deep: true,
			handler(newVal, oldVal){
				if(this.drawingPlots){ return; }
				this.relayout(newVal, false);
			}
		},
	},
	template: `<div class='flex-row bg-body p-1 align-items-stretch' :class='data.length && show ? "d-flex" : "d-none"'>
		<div class="d-flex flex-column" style="flex: 1 1 auto">
			<div v-if="params.length" class='d-flex flex-row justify-content-around'>
				<template v-for='(param, index) in params'>
					<div v-if='!grid.params.includes(param)'
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
		<div class='d-flex flex-column ps-4 gap-3'>
			<div class="btn-group">
				<button v-if="closeButton" type='button' class='btn btn-primary border-0 text-nowrap'
						@click="show = !show" title='close plots panel'>
					<i class='fa fa-times-circle ms-2'></i>
				</button>
				<div class="btn-group" title="Download visible plots in different image formats" style='flex: 1 1 auto'>
					<button class="btn btn-primary dropdown-toggle" type="button" data-bs-toggle="dropdown">
						<i class='fa fa-download'></i>
					</button>
					<ul class="dropdown-menu">
						<li v-for="url in downloadUrls">
							<a class="dropdown-item" href="#" @click='downloadImage(url)'>
								{{ url.substring(url.lastIndexOf('.') + 1, url.length).toUpperCase() }} format
							</a>
						</li>
					</ul>
				</div>
			</div>
			<div style='flex:1 1 0; overflow: auto' class='d-flex flex-column gap-3'>
				<div class='d-flex flex-column gap-2'>
				<div
					v-for="[legendgroup, legendObj] in Array.from(legend.entries()).filter(e => e[1].visible).concat(Array.from(legend.entries()).filter(e => !e[1].visible))"
					:style="legendObj.visible ? '' : {'visibility': 'hidden'}"
					class='d-flex flex-column p-2 border bg-white gap-2'
					>
					<div class='d-flex align-items-baseline gap-2 text-nowrap' :style="{color: legendObj.mainColor}">
						<input type='checkbox' title="Toggle plot trace(s) visibility"
							v-if="plots.some(p => p.data.length > 1)"
							v-model="legendObj.traceStyle.visible"
							@change="setTraceStyle(legendgroup, {visible: legendObj.traceStyle.visible})"
							:style="{'accent-color': legendObj.mainColor + ' !important'}" />
						<span style='flex: 1 1 auto'>{{ legendgroup }}</span>
						<button type='button' title="Style plot trace(s)" class='btn btn-sm border-0'
							@click="legendObj.expanded=!legendObj.expanded;"
							:style="{'color': legendObj.mainColor + ' !important'}">
							<span v-show="!legendObj.expanded"><i class='fa fa-chevron-down'></span>
							<span v-show="legendObj.expanded"><i class='fa fa-chevron-up'></span>
						</button>
					</div>
					<div :class="legendObj.expanded ? 'd-flex' :'d-none'"
						class='flex-column' style='flex: 1 1 auto;'
						:style="{color: legendObj.mainColor}">
						<textarea class='form-control rounded-bottom-0 border-bottom-0 p-1' spellcheck="false"
							size="3"
							style='color: inherit !important; resize: vertical; font-family:monospace; white-space: pre; overflow-wrap: normal; overflow: auto;'
							v-model="legendObj.traceStyleJSONString" />
						<button
							@click="try{ var json=JSON.parse(legendObj.traceStyleJSONString); setTraceStyle(legendgroup, json); }catch(e){ }"
							type="button" class='btn btn-sm rounded-top-0 border'
							style="color: inherit; !important">
								Apply
						</button>
					</div>
				</div>
				</div>
				<div :class="Object.keys(grid.layouts).length > 1 ? 'd-flex': 'd-none'"
					class='border p-2 bg-white flex-column gap-2'>
					<div>Subplots layout</div>
					<select v-model='grid.selectedLayout' class='form-control'>
						<option v-for='key in Object.keys(grid.layouts)' :value="key" v-html="key">
						</option>
					</select>
					<div class='d-flex flex-row'>
						<div>Show label</div>
						 <div v-for="ax in [1, 0]" class='ms-1 d-flex flex-row'>
							<label class='text-nowrap m-0 ms-2 align-items-baseline' v-show="!!grid.params[ax].label">
								<input type='checkbox' v-model="grid.visibility[ax]">
								<span class='ms-1 text-nowrap'>
									{{ grid.params[ax].label }}
								</span>
							</label>
						</div>
					</div>
				</div>
				<div class='d-flex flex-column border p-2 bg-white'>
					<div class="d-flex align-items-baseline gap-2"
						style="border-bottom: 1px solid var(--bs-primary) !important">
						<span style='flex: 1 1 auto'>Plots options</span>
						<ul class="nav nav-pills">
							<button type='button' class="nav-link active rounded-bottom-0"
									onclick='this.parentNode.querySelectorAll("button").forEach(e => e.classList.toggle("active")); this.parentNode.parentNode.parentNode.querySelectorAll("._panel").forEach(e => e.classList.toggle("d-none"))'>
								axis
							</button>
							<button type='button' class="nav-link rounded-bottom-0"
									onclick='this.parentNode.querySelectorAll("button").forEach(e => e.classList.toggle("active")); this.parentNode.parentNode.parentNode.querySelectorAll("._panel").forEach(e => e.classList.toggle("d-none"))'>
								mouse
							</button>
						</ul>
					</div>
					<table class='_panel table table-sm table-borderless mb-0'>
						<thead></thead>
						<tbody><tr v-for="ax in ['x', 'y']">
							<td class='text-nowrap text-end'>{{ ax }}</td>
							<td v-for="key in ['sameRange', 'log', 'grid', 'title']" class='text-nowrap text-end'>
								<label><input type='checkbox' v-model='plotoptions.axis[ax][key].checked'
									   :disabled="plotoptions.axis[ax][key].disabled">
									{{ key == 'sameRange' ? 'same range' : key }}
								</label>
							</td>
						</tr></tbody>
					</table>
					<table class='_panel table table-sm table-borderless mb-0 d-none'>
						<tbody><tr>
							<td>on hover</td>
							<td><select v-model="plotoptions.mouse.hovermode"
									class='form-control form-control-sm'>
								<option v-for='name in mouseMode.hovermodes' :value='name'>
									{{ mouseMode.hovermodeLabels[name] }}
								</option>
							</select></td>
						</tr>
						<tr>
							<td> on drag</td>
							<td><select v-model="plotoptions.mouse.dragmode"
									class='form-control form-control-sm'>
								<option v-for='name in mouseMode.dragmodes' :value='name'>
									{{ mouseMode.dragmodeLabels[name] }}
								</option>
							</select></td>
						</tr></tbody>
					</table>
				</div>
			</div>
		</div>
	</div>`,
	methods: {
		updateGridParams(){
			this.grid.params = this.grid.layouts[this.grid.selectedLayout] || [{}, {}];
			this.grid.params.forEach((p, i) => p.visible = !!(p.label && this.grid.visibility[i]));
		},
		init(data){
			if (!Array.isArray(data) || !data.length){
				return;
			}
			this.show = true;
			this.drawingPlots = true;
			// convert data:
			this.plots = Array.from(data);
			// update selection, taking into account previously selected stuff:
			this.setupParams();
			this.createLegend();
			this.initAxisControls();
			// now plot:
			this.$nextTick(() => {
				document.fonts.ready.then(() => {
					this.defaultlayout.font = this.computeFontObject();
					this.drawingPlots = false;
					this.newPlot();
				});
			});
		},
		computeFontObject(){
			var bodyStyle = window.getComputedStyle(document.getElementsByTagName('body')[0]);
			// define default font and infer from page if possible:
			var font = {};
			var fontf = bodyStyle.getPropertyValue('font-family');
			if (typeof fontf === 'string' && !!fontf){
				// Comma-separated font families work in Plotly here, but to download images
				// Plotly server side needs a single family, so set the 1st declared here:
				fontf = fontf.split(",")[0].trim();
				// remove quotes, if present:
				if ('\'"'.includes(fontf[0]) && fontf[fontf.length -1] == fontf[0]){
					fontf = fontf.substring(1, fontf.length - 1);
				}
				font.family = fontf;
			}
			var fonts = parseInt(bodyStyle.getPropertyValue('font-size'));
			if (typeof fonts === 'number' && !isNaN(fonts)){
				font.size = fonts;
			}
			return font;
		},
		setupParams(){
			var plots = this.plots;
			// sets up the params implemented on each plot. Params are used to select
			// specific plots to show, or to layout plots on a XY grid
			var paramvalues = new Map();  // preserves insertion order
			plots.forEach(plot => {
				var plotParams = plot.params || {};
				for (var paramName of Object.keys(plotParams)){
					if (!paramvalues.has(paramName)){
						paramvalues.set(paramName, []);
					}
					var pvalues = paramvalues.get(paramName);
					var pvalue = plotParams[paramName];
					if (!pvalues.includes(pvalue)){
						pvalues.push(pvalue);
					}
				}
			});
			// create an Array of params object (params mapped to a single value are discarded):
			var params = [];
			paramvalues.forEach((pvalues, pname) => {
				if(pvalues.length > 1){
					var values = Array.from(pvalues);
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
			var varr = '&#8679;';  // vertical arrow character
			var harr = '&#8680;';  // horizontal arrow character
			if (params.length == 0){
				if (plots.length == 1){
					// config this Vue Component with a 1x1 grid of plots non selectable and with no grid labels:
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
							var gridlayoutname = `${varr} ${prm2.label} vs. ${harr} ${prm1.label}`;
							gridlayouts[gridlayoutname] = [prm1, prm2];
							if (!selectedgridlayout){ // take the first combination as selected one:
								selectedgridlayout = gridlayoutname;
							}
						}
					}
				}
			}
			// set defaults:
			this.params = params;
			this.grid.layouts = gridlayouts;
			this.grid.selectedLayout = selectedgridlayout;
		},
		initAxisControls(){
			// initAxisControls is just about setting the initial checked state of the controls
			// The disable state or the v-model value associated to a checkbox (sameRange and title need one)
			// is set in initAxisControlsFromCurrentlyDisplayedPlots
			for (var layoutkey of ['xaxis', 'yaxis']){
				// get the Array of axis Objects:
				var axis = this.plots.map(p => (p.layout || {})[layoutkey] || {});
				// get the axis HTMl control:
				var control = layoutkey == 'xaxis' ? this.plotoptions.axis.x : this.plotoptions.axis.y;
				// title:
				control.title.checked = axis.every(a => a.title !== undefined);
				// grid:
				control.grid.checked = axis.every(a => a.showgrid || a.showgrid === undefined);
				// axis type (log / linear): enable only for specific plotly axis types:
				control.log.checked = axis.every(a => a.type === 'log');
				// same range is simply initialized to false by default
				control.sameRange.checked = false;
			}
		},
		newPlot(){  // redraw completely the plots
			this.drawingPlots = true;
			this.waitbar.msg = this.waitbar.DRAWING;
			setTimeout(() => {
				var divElement = this.$refs.rootDiv;
				var [data, layout] = this.createPlotlyDataAndLayout();
				Plotly.newPlot(divElement, data, layout, this.defaultplotlyconfig);
				// now compute labels and ticks size:
				var newLayout = this.updateLayoutFromCurrentlyDisplayedPlots(layout);
				Plotly.relayout(divElement, newLayout);
				this.drawingPlots = false;
			}, 100);
		},
		relayout(newLayout, updatePositions){  // Redraw the plot layout (anything but data)
			// updatePositions: set to true if newLayout affects in some way the position
			// of axis and gridlabels, which must thus be recomputed
			this.drawingPlots = true;
			this.waitbar.msg = this.waitbar.UPDATING;
			// TODO: if I do not do this, newLayout is undefined in setTimeout below?!!!
			var nl = newLayout || {};
			var up = updatePositions;
			setTimeout(() => {
				Plotly.relayout(this.$refs.rootDiv, nl);
				if (up){
					var newLayout = this.updateLayoutFromCurrentlyDisplayedPlots(this.getPlotlyDataAndLayout()[1]);
					Plotly.relayout(this.$refs.rootDiv, newLayout);
				}
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
		createPlotlyDataAndLayout(){
			var plots = this.plots;
			var [gridxparam, gridyparam] = this.grid.params;
			// filter plots according to the value of the parameter which are not displayed as grid param:
			for (var param of this.params){
				if (param === gridxparam || param === gridyparam){
					continue;
				}
				plots = plots.filter(plot => plot.params[param.label] === param.value);
			}
			this.initAxisControlsFromCurrentlyDisplayedPlots(plots);
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
			var plotBaseWidth = (1.0/cols); // as fraction of the whole plot area
			var plotBaseHeight = (1.0/rows); // as fraction of the whole plot area
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
				// compute axis domains. Remeber that xdomain = [x0, x1], where each xI in [0, 1] is
				// given as fraction of the main plot area width (same for ydomain wrt to total plot area height):
				var gridxindex = gridxindices[i];
				var gridyindex = gridyindices[i];
				var xdomain = [gridxindex*plotBaseWidth, gridxindex*plotBaseWidth + plotBaseWidth];
				var ydomain = [gridyindex*plotBaseHeight, gridyindex*plotBaseHeight + plotBaseHeight];
				// Now shrink both sizes by 50% to avoid plotly being too optimistic about the available plot space.
				// This prevents cases like e.g., plotly having enough space to lay out xtick labels horizontally and then,
				// after `updateLayoutFromCurrentlyDisplayedPlots` is executed (which likely shrinks the available space)
				// to lay them out vertically, causing overlapping labels as final result (another way of preventing this
				// is to set x(y)axis.tickangle!='auto' but it would cause other undesired drawbacks)
				xdomain[0] += plotBaseWidth/4.0;
				xdomain[1] -= plotBaseWidth/4.0;
				ydomain[0] += plotBaseHeight/4.0;
				ydomain[1] -= plotBaseHeight/4.0;
				// Add to the layout xaxis and yaxis, with specific key:
				var axisIndex = 1 + gridyindex * cols + gridxindex;
				layout[`xaxis${axisIndex}`] = Object.assign(xaxis, { domain: xdomain, anchor: `y${axisIndex}` });
				layout[`yaxis${axisIndex}`] = Object.assign(yaxis, { domain: ydomain, anchor: `x${axisIndex}` });
				// Map all traces to the axis just created on the layout:
				plot.data.forEach(trace => {
					trace.xaxis = `x${axisIndex}`;
					trace.yaxis = `y${axisIndex}`;
					if ('legendgroup' in trace){
						// this is necessary only if we show the plotly legend (we don't)
						// in order to avoid duplicated entries on the plotly legend:
						trace.showlegend = !legendgroups.has(trace.legendgroup);
						// this will be used later to set our legend visible:
						legendgroups.add(trace.legendgroup);
					}
					data.push(trace);
				});
			}
			// set legend visibility:
			for (var [key, legendObj] of this.legend.entries()) {
				legendObj.visible = legendgroups.has(key)
			}
			// add grid tick labels in form text placed on the plot (Plotly annotations).
			// The precise annotations positions will be set later (see `this.getPaperMargin`):
			// for now lace y labels+ticklabels on the left (x:0) and x stuff on the right (x:1)
			layout.annotations = this.getGridLabels().concat(this.getGridTickLabels());
			// delete xaxis and yaxis on layout, as they are meaningless (their values
			// are merged into each layout.xaxisN, layout.yaxisN Objects)
			delete layout.xaxis;
			delete layout.yaxis;
			// assign the axis properties from the controls:
			var newLayout = this.updateLayoutFromCurrentAxisControls(data, layout);
			// newLayout is flattened, so e.g. newLayout['xaxis.title.text'] must be
			// assigned to layout['xaxis']['title']['text']
			for (var key of Object.keys(newLayout)){
				var obj = layout;
				var subkeys = key.split('.');
				for (var subkey of subkeys.slice(0, -1)){
					if (!(subkey in obj)){
						obj[subkey] = {};
					}
					var obj = obj[subkey];
				}
				obj[subkeys[subkeys.length-1]] = newLayout[key];
			}
			return [data, layout];
		},
		initAxisControlsFromCurrentlyDisplayedPlots(plots){
			for (var layoutkey of ['xaxis', 'yaxis']){
				// get the Array of axis Objects:
				var axis = plots.map(p => (p.layout || {})[layoutkey] || {});
				// get the axis HTMl control:
				var control = layoutkey == 'xaxis' ? this.plotoptions.axis.x : this.plotoptions.axis.y;
				// title:
				var titles = axis.filter(
					a => a.title !== undefined
				).map(
					a => typeof a.title === 'object' ? a.title.text : a.title
				).filter(
					t => typeof t === "string"
				);
				control.title.disabled = true;
				if ((titles.length == plots.length) && (new Set(titles).size == 1)){
					control.title.disabled = false;
					control.title.text = titles[0];
				}
				// same range:
				control.sameRange.disabled = true;
				// consider only plots with data:
				var axiz = plots.filter(
					p => (p.data.length > 0) && Object.keys(p.data[0]).length > 0
				).map(
					p => (p.layout || {})[layoutkey] || {}
				);
				if (axiz.length > 1 && axiz.every(a => Array.isArray(a.range))){
					var mins = axiz.map(a => a.range[0]);
					var maxs = axiz.map(a => a.range[1]);
					// sort and get endpoints (Math.min and Math.max work for numeric data only)
					mins.sort((a, b) => a > b ? 1 : (b > a ? -1 : 0));
					maxs.sort((a, b) => a > b ? 1 : (b > a ? -1 : 0));
					var axisMin = mins[0];
					var axisMax = maxs[maxs.length-1];
					var invalid = [null, undefined, NaN];
					if (!invalid.includes(axisMin) && !invalid.includes(axisMax) && (axisMin < axisMax)){
						if (axiz.every(a => !('autorange' in a) || a.autorange === true)){ // autorange set for all plots
							control.sameRange.range = [axisMin, axisMax];
							control.sameRange.disabled = false;
						}
					}
				}
			}
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
		updateLayoutFromCurrentlyDisplayedPlots(layout){
			// return a new Object to be passed to `Plotly.relayout` where sizes and positions
			// of axis, gridlayout labels and ticks (if any) are recomputed from the HTML
			// elements currently laid out on the page. this is necessary because 1. our
			// gridlayout and 2. Plotly does not automatically computes ticklabels and label size
			// when setting a plot size
			var newLayout = {};
			for (var key of Object.keys(layout)){
				if ((key.startsWith('xaxis') || key.startsWith('yaxis')) && Array.isArray(layout[key].domain)){
					newLayout[`${key}.domain`] = Array.from(layout[key].domain);
				}
			}
			var axisKeys = Array.from(Object.keys(newLayout));
			// paper margin:
			var [gridxparam, gridyparam] = this.grid.params;
			var xdomains = gridxparam.values.map(x => null);  // new Array of null(s), filled later
			var ydomains = gridyparam.values.map(x => null);
			var cols = xdomains.length;
			var rows = ydomains.length;
			var plotmargin = this.getPlotsMaxMargin();
			var [w, h] = this.getElmSize(this.$refs.rootDiv);
			var [labelsmargin, ticklabelsmargin] = this.getPaperMargin();
			var papermargin = Object.assign({}, ticklabelsmargin);
			if (gridxparam.visible || gridyparam.visible){
				var linesmargin = Object.assign({}, ticklabelsmargin);
				//define spaces in font size units: label-tiklabels space, ticklabels-gridline space, gridline-axis space
				var _spaces = [0.75, 0.5, 2.25];
				// roughly get row height from min of papermargin, which should be the height of x axis
				var [fontW, fontH] = [layout.font.size / w, layout.font.size / h];
				if (gridxparam.visible){
					var spaces = _spaces.map(val => fontH * val);
					ticklabelsmargin.bottom += spaces[0];
					linesmargin.bottom += spaces[0] + spaces[1];
					papermargin.bottom += spaces[0] + spaces[1] + spaces[2];
				}
				if (gridyparam.visible){
					var spaces = _spaces.map(val => fontW * val);
					ticklabelsmargin.left += spaces[0];
					linesmargin.left += spaces[0] + spaces[1];
					papermargin.left += spaces[0] + spaces[1] + spaces[2];
				}
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
			if (gridxparam.visible || gridyparam.visible){
				newLayout.shapes = this.getGridLines(xdomains, ydomains, linesmargin);
				var annotations = this.getGridTickLabels(xdomains, ydomains, ticklabelsmargin);
				newLayout.annotations = annotations.concat(this.getGridLabels(xdomains, ydomains, labelsmargin));
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
				var xElm = infoLayer.querySelector(`g[class=g-${xindex}title]`);  // xlabel <g>
				if (xElm){
					xElm = xElm.getBBox();  // xlabel rect
				}
				if (!xElm || !xElm.height){
					xElm = elm.querySelector('g.xaxislayer-above');  // xticks+xticklabels <g>
					if (xElm){
						xElm = xElm.getBBox(); // xticks+xticklabels rect
					}
				}
				if (xElm && xElm.height){
					margin.bottom = max(margin.bottom, xElm.y + xElm.height - innerPlotRect.y - innerPlotRect.height);
				}
				// try to find the ylabel, otherwise get the yticks+yticklabels:
				var yElm =  infoLayer.querySelector(`g[class=g-${yindex}title]`); // ylabel
				if (yElm){
					yElm = yElm.getBBox();
				}
				if (!yElm || !yElm.width){
					yElm = elm.querySelector('g.yaxislayer-above');  // yticks+yticklabels
					if (yElm){
						yElm = yElm.getBBox();
					}
				}
				if (yElm && yElm.width){
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
		getPaperMargin(){ // returns two margins: gridlabels and gridticklabels (the latter is included in the former)
			var plotDiv = this.$refs.rootDiv;
			var [width, height] = this.getElmSize(plotDiv);
			var labelmargin = {top: 2.0/height, bottom: 2.0/height, left: 2.0/width, right: 2.0/width};
			var [gridxparam, gridyparam] = this.grid.params;
			if (!gridxparam.visible && !gridyparam.visible){
				return [labelmargin, labelmargin];
			}
			var ticklabelsmargin = {left: 0, top: 0, bottom: 0, right: 0};
			var infoLayer = plotDiv.querySelector('g.infolayer');
			var annotations = Array.from(infoLayer.querySelectorAll(`g[class=annotation]`)).sort((annot1, annot2) => {
				// sort annotations by their x midpoint:
				var box1 = annot1.getBBox();
				var box2 = annot2.getBBox();
				return (box1.x + box1.width/2) - (box2.x + box2.width/2);
			});
			if(gridxparam.visible){
				// get the x annotations, recognizable as those with lower x:
				var num = gridxparam.values.length;
				var annots = annotations.slice(annotations.length-num);
				var ticklabels = annots.filter(a => a.textContent !== gridxparam.label);
				if (ticklabels.length){
					ticklabelsmargin.bottom = Math.max(...ticklabels.map(elm => elm.getBBox().height)) / height;
				}
				var label = annots.filter(a => a.textContent === gridxparam.label)[0];
				if (label) {
					labelmargin.bottom = label.getBBox().height / height;
					ticklabelsmargin.bottom += labelmargin.bottom;
				};
			}
			if(gridyparam.visible){
				// get the y annotations, recognizable as those with higher x:
				var num = gridyparam.values.length;
				var annots = annotations.slice(0, num+1);
				var ticklabels = annots.filter(a => a.textContent !== gridyparam.label);
				if (ticklabels.length){
					ticklabelsmargin.left = Math.max(...ticklabels.map(elm => elm.getBBox().width)) / width;
				}
				var label = annots.filter(a => a.textContent === gridyparam.label)[0];
				if (label){
					labelmargin.left = label.getBBox().width / width;
					ticklabelsmargin.left += labelmargin.left;
				};
			}
			return [labelmargin, ticklabelsmargin];
		},
		getPlotGridPosition(axisKey){
			// return the current grid position [xIndex, yIndex] of the plot associated
			// to the string `axisKey` (a plotly layout key of the form:
			// /[xy]axis\d*/ where "xaxis" in plotly equals "xaxis1"). xIndex and yIndex
			// are in cartesian coordinates, so [0, 0] denotes the bottom-left plot,
			// [1, 0] the plot on its right, [0, 1] the plot above it, and so on
			var [gridxparam, gridyparam] = this.grid.params;
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
			if (!papermargin){
				papermargin = {left: 0.1, bottom: 0.1, top:0, right: 0};  // dummy margin
			}
			var [gridxparam, gridyparam] = this.grid.params;
			if (gridxparam.visible){
				if (!xdomains){
					xdomains = [[papermargin.left, 1-papermargin.right]];
				}
				annotations.push(this.createGridAnnotation({
					text: `${gridxparam.label}`,
					y: 0,
					yanchor: 'bottom',
					x: (xdomains[0][0] + xdomains[xdomains.length-1][1]) / 2,
					xanchor: 'center'
				}));
			}
			if (gridyparam.visible){
				if (!ydomains){
					ydomains = [[papermargin.bottom, 1-papermargin.top]];
				}
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
			if (!papermargin){
				papermargin = {left: 0.1, bottom: 0.1, top:0, right: 0};  // dummy margin
			}
			var [gridxparam, gridyparam] = this.grid.params;
			if (gridxparam.visible){
				var pvalues = gridxparam.values;
				if (!xdomains){
					var xs = pvalues.map((v, i, vs) => papermargin.left + i/vs.length);
				}else{
					var xs = xdomains.map(domain => (domain[1] + domain[0]) / 2);
				}
				for(var i =0; i < pvalues.length; i ++){
					annotations.push(this.createGridAnnotation({
						text: `${pvalues[i]}`,
						y: papermargin.bottom,
						yanchor: 'top',
						x: xs[i],
						xanchor: 'center'
					}));
				}
			}
			if (gridyparam.visible){
				var pvalues = gridyparam.values;
				if (!ydomains){
					var ys = pvalues.map((v, i, vs) => papermargin.bottom + i/vs.length);
				}else{
					var ys = ydomains.map(domain => (domain[1] + domain[0]) / 2);
				}
				for(var i =0; i < pvalues.length; i ++){
					annotations.push(this.createGridAnnotation({
						text: `${pvalues[i]}`,
						x: papermargin.left,
						xanchor: 'right',
						y: ys[i],
						yanchor: 'middle',
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
			var [gridxparam, gridyparam] = this.grid.params;
			if (gridxparam.visible){  // horizontal grid line
				shapes.push(Object.assign({}, defShape, {
					x0: xdomains[0][0],
					x1: xdomains[xdomains.length-1][1],  // 1 - papermargin.right,
					y0: papermargin.bottom,
					y1: papermargin.bottom
				}));
			}
			if (gridyparam.visible){  // vertical grid line
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
		updateLayoutFromCurrentAxisControls(data, layout){
			// return a new Object to be passed to `Plotly.relayout` with the axis properties
			// that are configurable (see `this.plotoptions`)
			var newLayout = {};
			for (var ax of ['x', 'y']){
				var control = ax == 'x' ? this.plotoptions.axis.x : this.plotoptions.axis.y;
				// get all layout['xaxis'], layout['xaxis1'] and so on. These are Objects
				// representing all plots x axis (same for 'y' the next loop):
				var regexp = ax == 'x' ? /^xaxis\d*$/g : /^yaxis\d*$/g;
				var axis = Object.keys(layout).filter(key => regexp.exec(key));
				// "remove" (set to undefined) the title
				// Note that we should call newPlot because we should recompute spaces
				// but that's too complex for the moment
				if (!control.title.disabled){
					var text = control.title.checked ? control.title.text : "";
					axis.forEach(a => newLayout[`${a}.title.text`] = text);
				}
				// set data from control:
				if (!control.grid.disabled){
					axis.forEach(a => newLayout[`${a}.showgrid`] = !!control.grid.checked);
				}
				if (!control.log.disabled){
					axis.forEach(a => newLayout[`${a}.type`] = control.log.checked ? 'log': 'linear');
				}
				// set data from control:
				if(!control.sameRange.disabled){
					if(!control.sameRange.checked){
						axis.forEach(a => newLayout[`${a}.range`] = undefined);
						axis.forEach(a => newLayout[`${a}.autorange`] = true);
					}else{
						var range = control.sameRange.range;
						range = control.log.checked ? [Math.log10(range[0]), Math.log10(range[1])] : Array.from(range);
						axis.forEach(a => newLayout[`${a}.range`] = range);
						axis.forEach(a => newLayout[`${a}.autorange`] = false);
					}
				}
			}
			return newLayout;
		},
		createLegend(){
			this.legend = new Map();
			for (var plot of this.plots){
				for (var trace of plot.data){
					if (trace.legendgroup && !this.legend.has(trace.legendgroup)){
						this.setLegendItem(trace.legendgroup, trace, true, false);
					}
				}
			}
		},
		setLegendItem(legendgroup, traceObject, visible, expanded){
			var traceStyle = {};
			['marker', 'line', 'xbins', 'ybins', 'fillcolor'].forEach(k => {
				if (k in traceObject){
					traceStyle[k] = traceObject[k];
				}
			});
			// create jsonString (to be set in the textarea and edited manually by users):
			var jsonString = JSON.stringify(traceStyle, null, 2);
			// Now set `traceStyle.visible`. Do this after creating the jsonString because
			// the visibility is set via a checkbox, not the textarea.
			// Note that traceObject.visible defaults to true if missing in plotly, so:
			traceStyle.visible = 'visible' in traceObject ? traceObject.visible : true;
			this.legend.set(legendgroup, {
				visible: visible,
				expanded: expanded,
				traceStyle: traceStyle,
				traceStyleJSONString: jsonString,
				traceStyleJSONValid: true,
				mainColor: this.getLegendColor(traceStyle)
			});
		},
		getLegendColor(styleObj){
			var color = '#000000';
			if (styleObj.marker && styleObj.marker.color){
				color = styleObj.marker.color + "";
			}else if(styleObj.line && styleObj.line.color){
				color = styleObj.line.color + "";
			}else if (styleObj.marker && styleObj.marker.line && styleObj.marker.line.color){
				color = styleObj.marker.line.color + "";
			}
			// if color is non-opaque, make it opaque:
			if (color.trim().toLowerCase().startsWith('rgba(')){
				color = color.replace(/,[^,]*\)\s*$/, ', 1)');
			}
			return color;
		},
		setTraceStyle(legendgroup, styleObject){
			try{
				var legendObj = this.legend.get(legendgroup);
				// same key => styleObject values will override legendObj.traceStyle values:
				var newStyleObject = Object.assign(legendObj.traceStyle, styleObject);
				this.setLegendItem(legendgroup, newStyleObject, legendObj.visible, legendObj.expanded);
			}catch(error){  // also raises if style is empty string
				return;
			}
			// update our data:
			this.plots.map(p => p.data).forEach(traces => {
				for (var i =0; i < traces.length; i++){
					if (traces[i].legendgroup === legendgroup){
						traces[i] = Object.assign(traces[i], styleObject);
					}
				}
			});
			// update plotly data, which requires the indices of the
			// currently displayed plots:
			var indices = [];
			var plotlydata = this.getPlotlyDataAndLayout()[0];
			plotlydata.forEach((trace, i) => {
				if (trace.legendgroup === legendgroup){
					indices.push(i);
				}
			});
			if(indices.length){
				this.restyle(styleObject, indices);
			}
		},
		getPlotlyDataAndLayout(){
			// returns the [data, layout] (Array, Object) currently displayed
			var elm = this.$refs.rootDiv;
			return elm ? [elm.data || [], elm.layout || {}] : [[], {}];
		},
		downloadImage(url){
			var [data, layout] = this.getPlotlyDataAndLayout();
			var parent = this.$refs.rootDiv; //.parentNode.parentNode.parentNode;
			var [width, height] = this.getElmSize(parent);
			data = data.filter(elm => elm.visible || !('visible' in elm));
			var postData = {data:data, layout:layout, width:width, height:height};
			this.$emit('image-requested', url, postData);
		}
	}
});