/* Base class to be used as mixin for any component showing plots as a result
of a response Object sent from the server */

var PlotsDiv = {
	props: {
		data: {type: Object, default: () => { return{} }},
		// this is used to calculate plot areas and set it in the default layout
		// (use computed body font-size. Note that parseInt('16px')=16):
		plotfontsize: {
			type: Number,
			default: parseInt(window.getComputedStyle(document.getElementsByTagName('body')[0]).getPropertyValue('font-size'))
		},
		downloadUrl: String // base url for download actions
	},
	data(){
		// unique id based on the component name (note that if this is called by a subclass,
		// then this.$options.name is the subclass name). FIXME: NOT USED REMOVE?
		var id = this.$options.name + new Date().getTime().toString();
		return {
			downloadActions: [],  // populated when data is there, see watch.data
			visible: false, // see watcher below
			// boolean visualizing a div while drawing (to prevent user clicking everywhere for long taks):
			drawingPlots: true,
			// store watchers to dynamically create / remove to avoid useless plot redrawing or calculations (see init)
			watchers: {},
			paramnames2showongrid: new Set(),  // parameter names to show on the grid
			plotdivid: Date.now().toString(),
			// an Object of names -> {visible: boolean, color: html color (string)}:
			legend: {},
			// plots is the data constructed from the received response.
			// It is an Array of Objects, each Object representing a plot P:
			// P: {
			//   traces: Array of Plotly Objects,
			//   params: Object of keys (string) mapped to a value, with the values
			//		   of this plot used to retrieve it when selecting what to show
			//   xaxis: Plotly Object with the xaxis data
			//   yaxis: Plotly Object with the yaxis data
			// }
			plots: [],
			// a dict of property names mapped (string) to an array of possible (string) values. This is
			// built automatically according to all possible values of the each Plot.params Object (see above)
			params: {},
			// dict of subplots layout (string) mapped to a two element Array
			// [xgrid param name, y grid param name]:
			gridlayouts: {},
			// string denoting the selected key of gridLayouts:
			selectedgridlayout: '',
			// selectedParams below is a dict of property names mapped to a scalar denoting the selected value
			// it is the keys of this.params without the values of this.gridlayouts[this.selectedgridlayout]
			// and each param will be displayed on one single-value-choosable combobox
			selectedParams: {},
			// defaultlayout. Note that defaultlayout.annotations, if specified here, will be copied and then
			// xaxis and grid labels will be copied to the new copied Array before passing it to Plotly as layout argument
			defaultlayout: {
				autosize: true,  // without this, the inner svg does not expand properly
				paper_bgcolor: 'rgba(0,0,0,0)', //window.getComputedStyle(document.getElementsByTagName('body')[0]).getPropertyValue('background-color'),
				// font: {family: "Encode Sans Condensed, sans-serif", size: 12}, // this will be overridden
				showlegend: false,
				legend: { bgcolor: 'rgba(0,0,0,0)'},
				margin: {r: 0, b: 0, t: 0, l:0, pad:0},
				annotations: []
			},
			mouseMode: { // https://plot.ly/python/reference/#layout-hovermode
				// hovermodes (plotly keys). Note that we remove the 'y' key because useless
				hovermodes: ["closest", "x", false],
				// the labels of hovermodes to be displayed. Copied from plotly modebar after visual test
				// (note that we remove  the value associated to 'y' because plotly does not implement it
				// and anyway, even providing a mapped label such as 'show y', tests revealed the mode was useless):
				hovermodeLabels: {closest: 'show closest point', x: 'compare data',false: 'do nothing'},
				dragmodes: ["zoom", "pan"],  // "select", "lasso" are useless. false does not seem to work (it's zoom)
				dragmodeLabels: {zoom: 'zoom', pan: 'pan'},
				hovermode: 'closest',  // will set this value to the Plotly layout before plotting, if not explicitly set
				dragmode: 'zoom'  // will set this value to the Plotly layout before plotting, if not explicitly set
			},
			// axis options:
			axis: {
				// reminder: x.log and y.log determine the type of axis. Plotly has xaxis.type that can be:
				// ['-', 'linear', 'log', ... other values ], we will set here only 'normal' (log checkbox unselected)
				// or log (log checkbox selected)
				x: {
					log: {disabled: false, value: undefined},  // undefined: infer from plots, null: disable the option, otherwise boolean
					sameRange: {disabled: false, value: undefined}, // same as above
				},
				y: {
					log: {disabled: false, value: undefined}, // see above
					sameRange: {disabled: false, value: undefined} // see above
				}
			},
			// the plotly config for plots. See
			// https://community.plot.ly/t/remove-options-from-the-hover-toolbar/130/14
			defaultplotlyconfig: {
				responsive: true,
				modeBarButtonsToRemove: ['sendDataToCloud', 'toImage'],
				displaylogo: false
			},
			defaultxaxis: {mirror: true, zeroline: false, linewidth: 1},  // domain and anchor properties will be overridden
			defaultyaxis: {mirror: true, zeroline: false, linewidth: 1},  // domain and anchor properties will be overridden
			colorMap: this.createColorMap(),
			// the waitbar while drawing plots
			waitbar: {
				msg: '',  // the message to be displayed, and below some defaults:
				DRAWING: 'Drawing plots... <i class="fa fa-hourglass-o"></i>',
				UPDATING: 'Updating plots... <i class="fa fa-hourglass-o"></i>'
			}
		}
	},
	watch: {
		// NOTE: There are several data variable that are watched dynamically
		// to avoid redrawing and recalculating the plot with recursive loops
		// See 'init' (calling 'turnWatchersOn')
		data: {
			immediate: true,
			handler(newval, oldval){
				this.visible = (typeof newval === 'object') && (Object.keys(newval).length);
				if (this.visible){ // see prop below
					this.init.call(this, newval);
					this.downloadActions = this.createDownloadActions();
				}
			}
		}
	},
	activated(){  // when component become active
		if (this.visible){
			this.react();
		}
	},
	computed: {  // https://stackoverflow.com/a/47044150
		legendNames(){
			return Object.keys(this.legend);
		},
		isGridCusomizable(){
			return Object.keys(this.gridlayouts).length>1;
		}
	},
	template: `<div v-show='visible' class='d-flex flex-row'>
		<div class="d-flex flex-column" style="flex: 1 1 auto">
			<div v-if="Object.keys(selectedParams).length"
				 class='d-flex flex-row justify-content-around mb-3'>
				<div v-for='(values, key, index) in selectedParams'
					 class='d-flex flex-row align-items-baseline'
					 :class="index > 0 ? 'ms-2' : ''" style="flex: 1 1 auto">
					<span class='text-nowrap me-1'>{{ key }}</span>
					<select v-model="selectedParams[key]" class='form-control' style="flex: 1 1 auto">
						<option v-for='value in params[key]' :value="value">
							{{ value }}
						</option>
					</select>
				</div>
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
				<div class='position-absolute start-0 top-0 end-0 bottom-0'
					 :id="plotdivid"></div>
			</div>
		</div>
	
		<!-- RIGHT TOOLBAR (legend, buttons, controls) -->

		<div class='d-flex flex-column ps-4' v-show="legendNames.length || isGridCusomizable">
			<slot></slot> <!-- slot for custom buttons -->
			<div v-show='legendNames.length' class='mt-3 border p-2 bg-white'
				 style='flex: 1 1 auto;overflow: auto'>
				<div>Legend</div>
				<div v-for="traceName in legendNames">
					<label class='my-0 mt-2' :class="{'checked': legend[traceName].visible}"
						:style="{color: legend[traceName].color}">
						<input type='checkbox' v-model="legend[traceName].visible"
							   :style="{'accent-color': legend[traceName].color}"
							   @change="traceVisibilityChanged(traceName)"> {{ traceName }}
					</label>
				</div>
			</div>

			<div>
				<div class='mt-3 border p-2 bg-white'>
					<action-select :actions="downloadActions" class='form-control'
								   data-balloon-pos='left' data-balloon-length='medium'
								   aria-label='Download the computed results in different formats. Notes: EPS images do not support color transparency, the result might not match what you see'>
						Download as:
					</action-select>
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
					<div v-for="type in ['x', 'y']" class='d-flex flex-row mt-1 text-nowrap align-items-baseline'>
						<span class='text-nowrap'>{{ type }}:</span>
						<label class='text-nowrap m-0 ms-2'
							   :class="{'checked': axis[type].sameRange.value}"
							   :disabled="axis[type].sameRange.disabled">
							<input type='checkbox' v-model='axis[type].sameRange.value'
								   :disabled="axis[type].sameRange.disabled"  class="me-1">
							<span>same range</span>
						</label>
						<label class='text-nowrap m-0 ms-2'
							   :class="{'checked': axis[type].log.value}"
							   :disabled="axis[type].log.disabled">
							<input type='checkbox' v-model='axis[type].log.value'
								   :disabled="axis[type].log.disabled" class="me-1">
							<span>log scale</span>
						</label>
					</div>
				</div>

				<div class='mt-3 d-flex flex-column border p-2 bg-white'>
					<div> Mouse interactions</div>
					<div class='d-flex flex-row mt-1 align-items-baseline'>
						<span class='text-nowrap me-1'> on hover:</span>
						<select v-model="mouseMode.hovermode"
								class='form-control form-control-sm'>
							<option v-for='name in mouseMode.hovermodes' :value='name'>
								{{ mouseMode.hovermodeLabels[name] }}
							</option>
						</select>
					</div>
					<div class='d-flex flex-row mt-1 align-items-baseline'>
						<span class='text-nowrap me-1'> on drag:</span>
						<select v-model="mouseMode.dragmode"
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
		// methods to be overridden:
		getData(responseObject){
			/* Return from the given response object an Array of Objects representing
			the sub-plot to be visualized. Each sub-plot Object has the form:
			{traces: Array, params: Object, xaxis: Object, yaxis: Object}

			See residuals.js and trellis.js for a details docstring and implementation
			*/
		},
		displayGridLabels(axis, paramName, paramValues){
			/* Return true / false to specify if the given parameter should be displayed
			as grid parameter along the specified axis. In this default implementation,
			return true if `paramValues.length > 1`.
			Function arguments:
				`axis`: string, either 'x' or 'y'
				`paramName`: the string denoting the parameter name along the given axis
				`paramValues`: Array of the values of the parameter keyed by 'paramName'
			*/
			return paramValues.length > 1;
		},
		configureLayout(layout){
			/* Configure the `layout` Object to be passed to plotly (for details, see
			https://plotly.com/javascript/reference/layout/). Note that the `layout` keys
			`font.family` and `font.size` will be overwritten if present as they need to
			be equal to the HTML page in order to reliably calculate spaces and sizes.
			Function argument:
				`layout` Object copied from `this.defaultlayout` which can be modified
					here. Note that this function does not need to return any value
			*/
			return
		},
		// END OF OVERRIDABLE METHODS
		addLegend(trace, key, defaultColor){
			// defaultColor is optional. If given (not undefined), it is in the form '#XXXXXX'
			var color;
			var colorMap = Vue.toRaw(this.colorMap);
			if (defaultColor !== undefined && !colorMap.has(key)){
				colorMap.set(key, defaultColor);
				color = defaultColor;
			}else{
				color = colorMap.get(key);  // sets also the key if not existing
			}
			if (!(key in this.legend)){
				this.legend[key] = {visible: true, color: color};
			}else{
				this.legend[key].color = color;
			}
			trace.legendgroup = key;
			return color;
		},
		init(jsondict){
			// unwatch watchers, if any:
			this.watchOff();
			this.legend = {};
			// convert data:
			this.plots = this.getData(jsondict);
			// update selection, taking into account previously selected stuff:
			this.setupSelection(); // which sets this.selectedgridlayout which calls this.gridLayoutChanged (see watch above)
			// which in turn sets this.selectedParams which eventually calls this.newPlot (see watch above)
			this.watchOn('selectedParams', function (newval, oldval) {
				this.newPlot();
			},{deep: true});
			this.watchOn('selectedgridlayout', function(newval, oldval){
				this.gridLayoutChanged(); // which changes this.selectedParams which should call newPlot above
			});
			this.setupAxisDefaults();
			// now plot:
			this.newPlot();
		},
		watchOff(...keys){
			// turns (dynamically created/destroyed) watchers off.
			// If keys (list of strings) is NOT provided, turns off and deletes all watchers
			var keys2delete = keys.length ? keys : Object.keys(this.watchers);
			for(var name of keys2delete){
				if (name in this.watchers){
					this.watchers[name]();
					delete this.watchers[name];
				}
			}
		},
		watchOn(key, callback, options){
			if (key in this.watchers){
				this.watchOff(key);
			}
			var watch = this.$watch(key, callback, options || {});
			this.watchers[key] = watch;
		},
		setupSelection(){
			// sets up selectable params, including those choosable as 'x grid' or 'y rid'.
			// called once from 'init'
			var plots = this.plots;
			var allparams = {};
			plots.forEach(plotElement => {
			   var plotParams = plotElement.params;
			   for (var key of Object.keys(plotParams)){
				   var paramValue = plotParams[key];
				   if(!(key in allparams)){
					   allparams[key] = new Set();
				   }
				   allparams[key].add(paramValue);
			   }
			});
			
			// adds a new parameter name to each plot and to all plot
			// argument multiValue is boolean (false: single value)
			var addParam = function(multiValue){
				var newParamName = '';
				while (newParamName in allparams){
					newParamName += ' ';
				}
				allparams[newParamName] = new Set();
				for (var i=0; i < plots.length; i++){
					var val = multiValue ? i : 0;
					plots[i].params[newParamName] = val;
					allparams[newParamName].add(val);
				}
				return newParamName;
			}
			// param names with a single choosable value, and multi values:
			var multiValueParamNames = Object.keys(allparams).filter(key => allparams[key].size > 1);
			var singleValueParamNames = Object.keys(allparams).filter(key => allparams[key].size == 1);

			var [paramNames, gridlabels2show] = [[], []];
			
			var gridlayouts = {};
			var selectedgridlayout = '';
			
			// set the param names to be choosen.
			// DEFINITIONS:
			// SVP (single value param): a parameter that has the same value for all plots
			// MVP (multi value param): a parameter that has a unique value for each plot
			// (note that the case where two plots share the same param value should never happen,
			// but we cannot check and correct for it)
			
			if (multiValueParamNames.length == 0){
				if (plots.length == 1){
					
					// case 1 (see DEFINITIONS above): only N>=0 SVPs, and the plots count is one:
					// nothing complex to do: assure the param count is at least two,
					// take the first two and provide a single possible grid selection (based on those two parameters)
					// the grid selection will be hidden as nothing can be choosen

					// if we have a single SVP, and one plot, display the param name for that SVP
					// on the xgrid above the plot, as to emulate a title, if one wants to:
					if (singleValueParamNames.length == 1){
						gridlabels2show.push(singleValueParamNames[0]);
					}
					
					// assure SVPs are at least two:
					while (singleValueParamNames.length < 2){
						singleValueParamNames.push(addParam(false));
					}
					
					// set the two SVPs as only choosable grid option (the option will be hidden as
					// there is nothing else to choose):
					paramNames = singleValueParamNames.slice(0, 2);
					gridlayouts['---'] = paramNames;  // the key of gridlayouts is ininfluent
					selectedgridlayout = '---';
				}else{
					
					// case 2 (see DEFINITIONS above): only N>=0 SVPs and the plots count is more than one:
					// this should not happen but neverthless provide a 'stack horizontally' and
					// 'stack vertically' grid options, by the order specified by building a "fake"
					// multi-value-param which assigns an incremental index to each plot

					// assure SVPs are at least one:
					while (singleValueParamNames.length < 1){
						singleValueParamNames.push(addParam(false));
					}
					// create MVP:
					multiValueParamNames.push(addParam(true));
					
					// set the two combinations of the SVP and the MVP as only choosable grid options
					// (providing a 'stack horizontally and 'stack vertically' generic names):
					paramNames = [singleValueParamNames[0], multiValueParamNames[0]];
					gridlayouts['&harr; stack horizontally'] = [paramNames[1], paramNames[0]];
					gridlayouts['&varr; stack vertically'] = [paramNames[0], paramNames[1]];
					selectedgridlayout = '&varr; stack vertically';
				}
			}else{
				
				// assure SVPs are at least two:
				while (singleValueParamNames.length < 2){
					singleValueParamNames.push(addParam(false));
				}

				// take the multi value param and first single-value param:
				paramNames = multiValueParamNames.concat(singleValueParamNames[0]).concat(singleValueParamNames[1]);
				gridlabels2show = Array.from(multiValueParamNames);

				// always provide a grid option selecting a single plot: when chosen, the MVPs will be set
				// as this.selectedParams and displayed in one or more single <select> on top of the plots 
				gridlayouts['single plot'] = [singleValueParamNames[0], singleValueParamNames[1]];

				if (multiValueParamNames.length == 1){
					
					// case 3 (see DEFINITIONS above): N>=0 SVPs and 1 MVP: basically same as
					// case 2 above but we do not need to create a fake multi-value param, 
					// we use what we have providing the parameter name in the grid options
					// (horizontal vs vertical) with the parameter name
					// instead of generic 'stack horizontally' or 'stack vertically'

					var svp = singleValueParamNames[0];
					var mvp = multiValueParamNames[0];
					gridlayouts[`&harr; ${mvp}`] = [mvp, svp];
					gridlayouts[`&varr; ${mvp}`] = [svp, mvp];
					selectedgridlayout = `&varr; ${mvp}`;
				}else{
					
					// case 4 (see DEFINITIONS above): N>=0 SVPs and M>1 MVPs: build a choosable grid
					// with all combinations of the given MVPs times 2, as for each couple of P1, P2
					// we can display the grid as P1xP2 or P2xP1
					
					for (var prm1 of multiValueParamNames){
						for (var prm2 of multiValueParamNames){
							if (prm1 === prm2){
								continue;
							}
							gridlayouts[`&harr; ${prm1} vs. &varr; ${prm2}`] = [prm1, prm2];
							if (!selectedgridlayout){ // take the first combination as selected one:
								selectedgridlayout = `&harr; ${prm1} vs. &varr; ${prm2}`;
							}
						}
					}
				}
			}
			// replace sets with sorted Arrays (vuejs wants Arrays, not Sets), and remove proeprties that are 'empty'
			// (either empty array or have a single falsy element (empty string, null)):
			var params = {};
			for(var key of paramNames){
				var values = Array.from(allparams[key]);
				// now sort values. Note that javascript array sort converts to string first (WTF!!!??), so
				// use a particular sort function for numbers only (see https://stackoverflow.com/a/1063027):
				if (typeof values[0] === 'number'){
					values.sort((a, b) => a - b);
				}else{
					values.sort();
				}
				params[key] = values;
			}
			// set defaults:
			this.gridlayouts = gridlayouts;
			this.selectedgridlayout = selectedgridlayout;
			this.paramnames2showongrid = new Set(gridlabels2show);
			this.params = params;
			// update grid layouts:
			this.gridLayoutChanged();
		},
		gridLayoutChanged(){
			var params = this.params;
			var [gridx, gridy] = this.gridlayouts[this.selectedgridlayout];
			var selectedParams = {};
			for(var paramName of Object.keys(params)){
				if (paramName == gridx || paramName == gridy || params[paramName].length <= 1){
					continue;
				}
				// if value is in this.selectedParams, keep that value, otherwise
				// take the first one:
				var val = (paramName in this.selectedParams) ? this.selectedParams[paramName] : params[paramName][0];
				// set as selected param the first value:
				selectedParams[paramName] = val;
			}
			this.selectedParams = selectedParams;
		},
		setupAxisDefaults(){
			// sets up the axis default for each plot and in the VueJs settings
			// modifies each plot xaxis / yaxis data and `this.axis` Object
			//
			// Remember that:
			// 1. `plots` is a subset of `this.plots` and it is an Array of plots,
			// i.e. Objects of the form:
			// plot= {
			//	 traces: [] //list of Plotly Objects representing traces
			//	 xaxis: {} //Plotly Object representing x axis
			//	 yaxis: Plotly Object representing y axis
			// }, ..
			//
			// The Vue Object controlling axis settings is of the form:
			// axis: {
			//	 x: {
			//		 log: {value:undefined, disabled:false},  // undefined: infer from plots, null: disable the option, otherwise boolean
			//		 sameRange: {value:undefined, disabled: false} // same as above
			//	 },
			//	 y: { same as above }
			// },

			var keys = ['axis.x.log.value',
						'axis.y.log.value',
						'axis.x.sameRange.value',
						'axis.y.sameRange.value'];
			this.watchOff(...keys);

			// Set "private" variable in the xaxis and yaxis Objects used to
			// remember some defaults, if set.
			// Currently, we set _range and _type, which are the counterparts
			// of 'range' and 'type', respectively. The latter are Plotly reserved
			// keyswords and apparently it's harmless to add our custom (underscored)
			// counterparts
			this.plots.forEach(plot => {
				if (!plot.xaxis){
					plot.xaxis={};
				}
				if (!plot.yaxis){
					plot.yaxis={};
				}
				var [rangex, rangey] = this.getPlotBounds(plot.traces || []);  // note that hidden traces count
				plot.xaxis._range = rangex;
				plot.yaxis._range = rangey;

				plot.xaxis._type = !(plot.xaxis.type) || (plot.xaxis.type == 'log') ? '' : plot.xaxis.type;
				plot.yaxis._type = !(plot.yaxis.type) || (plot.yaxis.type == 'log') ? '' : plot.yaxis.type;
			});

			// setup default values:
			for (var key of ['x', 'y']){
				var axis = this.axis[key];  // the key for this,.axis ('x' or 'y')
				var plotkey = key + 'axis';  //  the key for each plot axis: 'xaxis' or 'yaxis'
				// axis.sameRange.disabled = false;
				axis.sameRange.value = false;
				// get if all axis have the same bounds:
				var pltBounds = this.plots[0][plotkey]._range;
				if (this.plots.every(plot => plot[plotkey]._range.every((elm, index) => elm === pltBounds[index]))){
					// axis.sameRange.disabled = true;
					axis.sameRange.value = true;
				}
				// log scale:
				axis.log.value = this.plots.every(plot => plot[plotkey].type === 'log');
				// set log scale disabled if the traces do not have 'log' as type and there are axis bound <=0:
				//axis.log.disabled = !axis.log.value && plots.some(plot => plot[plotkey]._range.some(n => isNaN(n) || n <= 0));
			}

			// restart watching: 
			for (var key of keys){
				// watch each prop separately because with 'deep=true' react is called more than once ...
				this.watchOn(key, function(newval, oldval){
					this.react();
				});
			}
		},
		newPlot(){
			/**
			 * Filters the plots to display according to current parameters and grid choosen, and
			 * calls Plotly.newPlot on the plotly <div>
			 */
			var divElement = document.getElementById(this.plotdivid);
			this.$nextTick(() => {
				var [hover, drag] = ['mouseMode.hovermode', 'mouseMode.dragmode'];
				this.watchOff(hover, drag);
				var [data, layout] = this.createPlotlyDataAndLayout(divElement);
				this.execute(function(){
					// console.log(this.getElmSize(divElement));
					Plotly.purge(divElement);  // Purge plot. FIXME: do actually need this?
					Plotly.newPlot(divElement, data, layout, this.defaultplotlyconfig);
					this.watchOn(hover, function (newval, oldval) {
						this.setMouseModes(newval, undefined);  // hovermode, mousemode
					});
					this.watchOn(drag, function(newval, oldval){
						this.setMouseModes(undefined, newval);  // hovermode, mousemode
					});
				}, {delay: 300});  // this delay is increased because we might have the animation
				// of the form closing to be finished: overlapping waitbar and form closing is
				// sometimes not nice
			});
		},
		react(){
			/**
			 * Same as this.newPlot above, and can be used in its place to create a plot,
			 * but when called again on the same <div> will update it far more efficiently
			 */
			var divElement = document.getElementById(this.plotdivid);
			this.$nextTick(() => {
				this.execute(function(){
					var [data, layout] = this.createPlotlyDataAndLayout(divElement);
					// console.log(this.getElmSize(divElement));
					Plotly.react(divElement, data, layout);
				});
			});
		},
		execute(callback, options){
			// Executes asynchronously the given callback
			// (with this component as 'this' argument) showing a waitbar meanwhile.
			// 'options' is an Object with two optional properties:
			// options.msg (the waitbar message, defaults to self.waitbar.msg)
			// and delay (the delay to execute the given callback, defaults to self.waitbar.delay: 200)
			var delay = (options || {}).delay || 200;
			this.waitbar.msg = (options || {}).msg || this.waitbar.DRAWING;
			var self = this;
			this.drawingPlots=true;
			setTimeout(function(){
				callback.call(self);
				self.drawingPlots=false;
			}, delay);
		},
		createPlotlyDataAndLayout(divElement){
			var plots = this.plots;
			var params = this.params;
			
			// filter plots according to selectedParams keys, i.e. the parameter names
			// which are mapped to mupliple values AND are not currently set to be displayed on the
			// grid x or grid y (basically, the parameters which will show up in a combo box on top of the whole plot)
			// The number of these parameters might be zero: in this case the filter below has no effect and we
			// still have all plots after the loop. Note also that the filter returns a copy of the original array.
			for (var key of Object.keys(this.selectedParams)){
				var val = this.selectedParams[key];
				plots = plots.filter(plot => plot.params[key] == val);
			}

			// console.log('creating plots');
			this.setupPlotAxisData(plots);

			var [gridxparam, gridyparam] = this.gridlayouts[this.selectedgridlayout];
			var gridxvalues = params[gridxparam];
			var gridyvalues = params[gridyparam];
			var gridXval2index = new Map(gridxvalues.map((elm, idx) => [elm, idx]));
			var gridYval2index = new Map(gridyvalues.map((elm, idx) => [elm, idx]));
			// now build an array the same length as plots with each element the grids position [index_x, index_y]
			var plotsGridIndices = [];
			for (var plot of plots){
				var plotXGridIndex = gridXval2index.get(plot.params[gridxparam]);
				var plotYGridIndex = gridYval2index.get(plot.params[gridyparam]);
				plotsGridIndices.push([plotXGridIndex, plotYGridIndex]);
			}

			var layout = Object.assign({}, this.defaultlayout);
			this.configureLayout(layout);
			// synchronize hovermode and hovermode
			// between the layout and this.mouseMode:
			['hovermode', 'dragmode'].forEach(elm => {
				if (elm in layout){
					this.mouseMode[elm] = layout[elm];
				}else{
					layout[elm] = this.mouseMode[elm];
				}
			});
			// set font (if not present):
			if (!('font' in layout)){
				layout.font = {};
			}
			// setup font as the body font, and size as set in the object properties, since the font size
			// is used to calculate spaces it cannot be changed in configureLayout:
			layout.font.family = window.getComputedStyle(document.getElementsByTagName('body')[0]).getPropertyValue('font-family');
			layout.font.size = this.plotfontsize;
			// copy layout annotations cause it's not a "primitive" type and thus we want to avoid old annotation to be re-rendered
			layout.annotations = layout.annotations ? Array.from(this.defaultlayout.annotations) : [];
			
			var data = [];
			var xdomains = new Array(gridxvalues.length);  // used below to place correctly the x labels of the GRID
			var ydomains = new Array(gridyvalues.length);  // used below to place correctly the x labels of the GRID
			var annotation = this.getAnnotation;
			var legendgroups = new Set();
			for (var i = 0; i < plots.length; i++){
				var [plot, [gridxindex, gridyindex]] = [plots[i], plotsGridIndices[i]];
				var [axisIndex, xaxis, yaxis, xdomain, ydomain] = this.getAxis(divElement, gridyindex, gridxindex, gridyvalues.length, gridxvalues.length);
				xdomains[gridxindex] = xaxis.domain;  // used below to place correctly the x labels of the GRID
				ydomains[gridyindex] = yaxis.domain;  // used below to place correctly the y labels of the GRID
				// merge plot xaxis defined in getData with this.defaultxaxis, and then with xaxis.
				// Priority in case of conflicts goes from right (xaxis) to left (this.defaultxaxis)
				layout[`xaxis${axisIndex}`] = xaxis = Object.assign({}, this.defaultxaxis, plot.xaxis, xaxis);
				// merge plot yaxis defined in getData with this.defaultyaxis, and then with yaxis.
				// Priority in case of conflicts goes from right (yaxis) to left (this.defaultyaxis)
				layout[`yaxis${axisIndex}`] = yaxis = Object.assign({}, this.defaultyaxis, plot.yaxis, yaxis);
				// Now edit the traces in plot.traces. Each trace is basically an Object of the
				// form T = {x: ..., y: ...}. These trace properties need to be modified EACH TIME:
				// 1. T.xaxis and T.yaxis (i.e., basically on which subplot the trace has to be displayed), and
				// 2. T.showlegend. The latter is set to true for the FIRST trace found for a given legendgroup
				// in order to avoid duplicated legend names. (T.legendgroup = T.name is the GSIM name, and it allows
				// toggling visibility simultaneously on all subplots for every trace with the same legendgroup, when 
				// clicking on the legend's GSIM name)
				plot.traces.forEach(function(element){
					element.xaxis = `x${axisIndex}`;
					element.yaxis = `y${axisIndex}`;
					if ('legendgroup' in element){
						element.showlegend = !legendgroups.has(element.legendgroup);
						legendgroups.add(element.legendgroup);
					}
					data.push(element);
				});
				// write x and y labels: we might simply set xaxis.title= 'my label' (same for y axis) but:
				// 1. plotly reserves too much space between the axis line and the axis label (the space is out of control)
				// 2. Plotly does some hard coded calculation and moves the labels, and we want control over it:
				// for instance when two ploits are stacked vertically,
				// the bottom one has the legend moved up to be included in the plot area)
				
				// So, get xaxis.title and yaxis.title (if any) and put them as annotations:
				if (xaxis.title){
					layout.annotations.push(annotation({
						x: (xaxis.domain[1]+xaxis.domain[0])/2,
						y: ydomain[0],
						xanchor: 'center',
						yanchor: 'bottom',
						text: xaxis.title
					}));
					// delete xaxis title otherwise plotly draws the label:
					delete xaxis.title;
				}
				// and ylabel: (why this? can't I set the tile to the xaxis object?)
				if (yaxis.title){
					layout.annotations.push(annotation({
						x: xdomain[0],
						y: (yaxis.domain[1]+yaxis.domain[0])/2,
						xanchor: 'left',
						yanchor: 'middle',
						textangle: '-90',
						text: yaxis.title
					}));
					// delete xaxis title otherwise plotly draws the label:
					delete yaxis.title;
				}
		  }
		  // Grid X labels: (horizontally on top)
		  if (this.displayGridLabels_('x', gridxparam)){
			  // determine the maximum y of all plot frames:
			  // var y = Math.max(...ydomains.map(elm => elm[1]));
			  // create the x labels of the vertical grid:
			  for (var [domain, gridvalue] of xdomains.map((elm, index) => [elm, gridxvalues[index]])){
				  layout.annotations.push(annotation({
					  x: (domain[1] + domain[0])/2,
					  y: 1,
					  xanchor: 'center', /* DO NOT CHANGE THIS */
					  yanchor: 'top',
					  text: `${gridxparam}: ${gridvalue}`
				}));
			  }
		  }
		  // Grid Y labels: (vertically on the right)
		  if (this.displayGridLabels_('y', gridyparam)){
			  // determine the maximum x of all plot frames:
			  // var x = Math.max(...xdomains.map(elm => elm[1]));
			  // create the y labels of the vertical grid:
			  for (var [domain, gridvalue] of ydomains.map((elm, index) => [elm, gridyvalues[index]])){
				  layout.annotations.push(annotation({
					  x: 1,
					  y: (domain[1] + domain[0])/2,
					  xanchor: 'right',
					  yanchor: 'middle', /* DO NOT CHANGE THIS */
					  text: `${gridyparam}: ${gridvalue}`,
					  textangle: '-270'
				}));
			  }
		  }
		  return [data, layout];
		},
		setupPlotAxisData(plots){
			// sets up the plotly axis data on the plots to be plotted, according to
			// the current axis setting and the plot data

			// set the plot xaxis and yaxis type:
			for (var key of ['x', 'y']){
				var axis = this.axis[key];  // the key for this,.axis ('x' or 'y')
				var plotkey = key + 'axis';  //  the key for each plot axis: 'xaxis' or 'yaxis'
				plots.forEach(plot => {
					plot[plotkey].type = axis.log.value ? 'log' : plot[plotkey]._type;
					// we might have falsy plot type, meaning that the non-log type was unspecified
					// thus remove:
					if (!plot[plotkey].type){
						delete plot[plotkey].type;  // reset to default, whatever it is
					}
				});
				axis.log.disabled = false;  // enabled log chekbox, plotly seems to handle it. Previous code was:
				// axis.log.disabled = !axis.log.value && plots.some(plot => plot[plotkey]._range.some(n => isNaN(n) || n <= 0));
			}

			var [sign, log10] = [Math.sign, Math.log10];
			// displaybars tells us if we are displaying (at least one) bar: this changes the behaviour
			// of the margin for custom-defined ranges (see below)
			var displaybars = plots.every(plot => plot.traces.some(trace => trace.type === 'bar'));
			for (var key of ['x', 'y']){
				var axis = this.axis[key];  // the key for this,.axis ('x' or 'y')
				var plotkey = key + 'axis';  //  the key for each plot axis: 'xaxis' or 'yaxis'

				// set same Range disabled, preventing the user to perform useless click:
				// Note that this includes we are shoing only one plot:
				var pltBounds = plots[0][plotkey]._range;
				axis.sameRange.disabled =
					(plots.every(plot => plot[plotkey]._range.every((elm, index) => elm === pltBounds[index])));
				if (!axis.sameRange.value || axis.sameRange.disabled){
					plots.forEach(plot => {
						delete plot[plotkey].range;
					});
					continue;
				}
				// here deal with the case we have 'sameRange' clicked (and enabled):
				var range = [NaN, NaN];
				plots.forEach(plot => {
					range = this.nanrange(...range, ...plot[plotkey]._range);
				});
				// calculate margins. Do not add them IF:
				// 1. log scale and adding/removing margin causes value <=0
				// 2. if range[0], Is displaybars, range  if: no log displayed or bound+- margin still positive,
				// no bar displayed OR signum min
				var margin = Math.abs(range[1] - range[0]) / 50;
				if (displaybars && sign(range[0]) >= 0 && sign(range[1]) >= 0){
					// do not add margin to the minimum
				}else if (!axis.log.value || range[0] - margin > 0){
					range[0] -= margin;
				}
				if (displaybars && sign(range[0]) <= 0 && sign(range[1]) <= 0){
					// do not add margin to the maximum
				}else if (!axis.log.value || range[1] + margin > 0){
					range[1] += margin;
				}
				if (range.every(elm => !isNaN(elm))){
					plots.forEach(plot => {
						// plotly wants range converted to log if axis type is 'log':
						plot[plotkey].range = plot[plotkey].type === 'log' ? [log10(range[0]), log10(range[1])] : range;
					});
				}
			}
		},
		displayGridLabels_(axis, paramName){
			if (this.paramnames2showongrid.has(paramName)){
				return this.displayGridLabels(axis, paramName, this.params[paramName]);
			}
			return false;
		},
		getAxis(divElement, row, col, rows, cols){
			// computes the sub-plot area according to the row and col index
			// returns the array [axisIndex, xaxis, yaxis, xdomain, ydomain]
			// where xaxis and yaxis are the Objects to be passed to plotly's layout, xdomain = [x1, x2] and
			// ydomain = [y1, y2] are the two-element arrays denoting the enclosing area of the sub-plot
			var [uwidth, uheight] = this.getElmEmUnits(divElement, this.plotfontsize);
			var [gridxparam, gridyparam] = this.gridlayouts[this.selectedgridlayout];
			if (!this.displayGridLabels_('x', gridxparam)){
				gridxparam = '';
			}
			if (!this.displayGridLabels_('y', gridyparam)){
				gridyparam = '';
			}
			var tt = gridxparam ? 1.5 * uheight : 0;
			var rr = gridyparam ? 3 * uwidth : 0;
			// the legend, if present, is not included in the plot area, so we can safely ignore it. Comment this line:
			// rr += 0. * uwidth * Math.max(...Object.keys(this.plotTraceColors).map(elm => elm.length)) ;
			var axisIndex = 1 + row * cols + col;
			// assure the dimensions are at least a minimum, otherwise plotly complains (assuming 10px as font-minimum):
			var [minuwidth, minuheight] = this.getElmEmUnits(divElement, 10);
			// calculate plot width and height:
			var colwidth = Math.max(minuwidth, (1-rr) / cols);
			var rowheight = Math.max(minuheight, (1-tt) / rows);
			// determine the xdomain [x0, x1] defining the enclosing plot frame width (including ylabel):
			var xdomain = [col*colwidth, (1+col)*colwidth];
			// determine the ydomain [y0, y1] defining the enclosing plot frame height (including xlabel):
			var ydomain = [(rows-row-1)*rowheight, (rows-row)*rowheight]; // (y coordinate 0 => bottom , 1 => top)
			// define now the plotly x and y domains, which do NOT include x and y labels. Define paddings:
			var b = 3 * uheight;
			var t = 1 * uheight;
			var l = 4.5 * uwidth;
			var r = 1 * uwidth;
			// now define domains:
			var xaxisdomain = [xdomain[0]+l, xdomain[1]-r];
			var yaxisdomain = [ydomain[0]+b, ydomain[1]-t];
			// check that the domains are greater than a font unit:
			if (xaxisdomain[1] - xaxisdomain[0] < minuwidth){
				xaxisdomain = xdomain;
			}
			// check that the domains are greater than a font unit:
			if (yaxisdomain[1] - yaxisdomain[0] < minuheight){
				yaxisdomain = ydomain;
			}
			var xaxis = {domain: xaxisdomain, anchor: `y${axisIndex}`};
			var yaxis = {domain: yaxisdomain, anchor: `x${axisIndex}`};
			//console.log('xdomain:' + xdomain); console.log('ydomain:' + ydomain);
			return [axisIndex, xaxis, yaxis, xdomain, ydomain];
		},
		getElmEmUnits(domElement, fontsize){
			// returns [uwidth, uheight], the units of a 1em in percentage of the given dom element,
			// which must be shown on the browser
			// Both returned units should be < 1 in principle
			var [width, height] = this.getElmSize(domElement);
			return [fontsize/width, fontsize/height];
		},
		getElmSize(domElement){
			// returns the Array [width, height] of the given dom element size
			return [domElement.offsetWidth, domElement.offsetHeight];
		},
		getAnnotation(props){
			return Object.assign({
				xref: 'paper',
				yref: 'paper',
				showarrow: false,
				font: {size: this.plotfontsize}
		  }, props || {});
		},
		traceVisibilityChanged(traceName){
			var indices = [];
			var plotlydata = this.getPlotlyDataAndLayout()[0];
			var legend = this.legend;
			var visible = legend[traceName].visible;
			plotlydata.forEach(function(data, i){
				var plotlyVisible = ('visible' in data) ? !!data.visible : true;
				if (data.legendgroup === traceName && visible !== plotlyVisible){
					data.visible = visible;
					indices.push(i);
				}
			});
			if(indices.length){
				this.execute(function(){
					Plotly.restyle(this.plotdivid, {visible: visible}, indices);
				});
			}
		},
		getPlotlyDataAndLayout(){
			/**
			 * returns [data, layout] (Array an Object),
			 * i.e. the Plotly data and layout used to draw the plot
			 */
			var elm = document.getElementById(this.plotdivid);
			return elm ? [elm.data || [], elm.layout || {}] : [[], {}];
		},
		getPlotBounds(traces){
			// gets the bounds min max of all the traces of 'plot', which must be an
			// element of this.plots. Returns [rangeX, rangeY] where each range has two numeric elements
			// pmin, max] which might be NaN
			var [rangeX, rangeY] = [[NaN, NaN], [NaN, NaN]];
			for (var trace of traces){
				if (trace.x){
					var rangex = this.nanrange(...trace.x);
					rangeX = this.nanrange(...rangeX, ...rangex);
				}
				if (trace.y){
					var rangey = this.nanrange(...trace.y);
					rangeY = this.nanrange(...rangeY, ...rangey);
				}
			}
			return [rangeX, rangeY];
		},
		nanrange(...values){
			values = values.filter(elm => typeof elm === 'number' && !isNaN(elm));
			var m = Math;
			return values.length? [m.min(...values), m.max(...values)] : [NaN, NaN];
		},
		setMouseModes(hovermode, dragmode){
			var [data, layout] = this.getPlotlyDataAndLayout();
			var relayout = false;
			if (this.mouseMode.hovermodes.includes(hovermode)){
				layout.hovermode = hovermode;
				relayout = true;
			}
			if (this.mouseMode.dragmodes.includes(dragmode)){
				layout.dragmode = dragmode;
				relayout = true;
			}
			if (relayout){
				this.execute(function(){
					Plotly.relayout(this.plotdivid, layout);
				}, {msg: this.waitbar.UPDATING});
			}
		},
		createColorMap(){
			// Return a new ColorMap class extending `Map` and mapping a given key
			// to a color. Given a key (e.g. legend name), then `colorMap.get(key)`
			// automatically returns a color (hex string) assuring the same
			// color for the same key. The class extends `Map` and has also a
			// `transparentize` method (see below)

			// defines ColorMap class:
			class ColorMap extends Map {
				constructor() {
					super();
					this._defaults = {
							index: 0,
							colors: [
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
							]
					}
				}
				get(key){
					// sets a color mapping `key` if `key` is not in this Map
					// (the color will be set incrementally based on `this._defauls.colors`).
					// Eventually, it returns the color (hex string) mapped to `key`, as the superclass does
					var color = super.get(key);
					if (color === undefined){
						var colors = this._defaults.colors;
						color = colors[(this._defaults.index++) % colors.length];
						this.set(key, color);
					}
					return color;
				}
				transparentize(hexcolor, alpha) {
					// Returns the corresponding 'rgba' string of `hexcolor` with the given alpha channel ( in [0, 1], 1:opaque)
					// If `hexcolor` is an integer, it indicates the index of the default color to be converted
					if (typeof hexcolor == 'number'){
						hexcolor = this._defaults.colors[parseInt(hexcolor) % this._defaults.colors.length];
					}
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
			return new ColorMap();
		},
		createDownloadActions(){
			// Populate with the data to be downloaded as non-image formats:
			var downloadActions = this.$httpClient.createDownloadActions(this.downloadUrl, this.data);
			// image formats:
			// create a function factory to avoid closure inside loops (classic approach):
			var createCallback = (ext) => {
				return () => {
					var [data, layout] = this.getPlotlyDataAndLayout();
					var parent = document.getElementById(this.plotdivid).parentNode.parentNode.parentNode;
					var [width, height] = this.getElmSize(parent);
					data = data.filter(elm => elm.visible || !('visible' in elm));
					postData = {data:data, layout:layout, width:width, height:height};
					var url = this.downloadUrl + '.' + ext;
					this.$httpClient.download(url, postData);
				};
			};
			for (var ext of ['png', 'eps', 'pdf', 'svg']){
				downloadActions.push([`${ext} (visible plots only)`, createCallback(ext)]);
			}
			return downloadActions;
		}
	}
};