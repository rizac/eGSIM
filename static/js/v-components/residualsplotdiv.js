Vue.component('residualsplotdiv', {
    extends: _PLOT_DIV,  // defined in plot-div.js
    methods: {
        // methods to be overridden:
        getData: function(responseObject){
            // this method needs to be implemented in order to initialize the response object into
            // an Array of sub-plots, and return that Array: each Array element (or "sub-plot")
            // need to be a js Object of the form:
            // {traces: Array, params: Object, xaxis: Object, yaxis: Object} where:
            //
            // traces:
            // an Array of valid representable plotly objects e.g. {x: Array, y: Array, name: string}.
            // It is basically the 'data' argument passed to Plotly
            // (https://plot.ly/javascript/plotlyjs-function-reference/#plotlynewplot). A list of
            // valid keys / properties of each Object is available at
            // https://plot.ly/javascript/reference/ for details, but consider that this class will
            // dynamically create some of them for correctly placing plots on the grid: thus
            // the keys `xaxis` (string), 'yaxis' (string), 'showlegend' (boolean) will be ignored
            // (overwritten) if specified.
            // NOTE1: Providing a `name` key makes the name showing when hovering over the trace with
            // the mouse
            // NOTE2: To add a unique color mapped to a trace id (e.g. the trace name) and
            // setup the legendgroup and automatically map the trace to a legend item toggling
            // the trace visibility, use `this.addLegend(trace, key)`, e.g.:
            //     var trace = {x: Array, y: Array, name: 'mytrace'}
            //     var color = this.addLegend(trace, trace.name)
            //     trace.line = {color: color}  // set the trace color to the legend assigned color
            // `addLegend(trace, K)` maps the returned color to the key K provided;
            // subsequent calls to this.addLegend(..., K) return the same color.
            // The returned color is a color assigned to K by cycling through an internal color
            // array (copied from plotly). If you want to specify a default
            // color for non-mapped keys avoiding the default assignement, call:
            // `addLegend(trace, key, color)` with an optional color string in the form '#XXXXXX'.
            // `addLegend` also sets trace.legendgroup=K.
            //
            // params:
            // an Object of selectable params (string) mapped to the plot specific values
            // (e.g. {magnitude: 5, 'xlabel: 'PGA'}). All possible values and all possible keys
            // will be processed to build the parameters whereby it is possible to filter/select
            // specific plots, as single view or on a XY grid (for the latter, at least two keys
            // must be provided). Note that if only one
            // key is provided, then the string "<key>: <value>" will be used as plot title (statically,
            // as there are no grid parameter to be tuned). E.g., returning always
            // {'plot title': '1'} will display 'plot title: 1' as plot title.
            // 
            // xaxis:
            // a dict of x axis properties. Example: {title: 'plottitle', type: 'log'}.
            // It is basically the 'layout.xaxis<N>' Object (where N is an integer which
            // depends on the plot placement on the grid), where 'layout' is the layout argument
            // passed to Plotly (https://plot.ly/javascript/plotlyjs-function-reference/#plotlynewplot).
            // 'layout.xaxis<N>' will be built by merging `this.defaultxaxis` and the values
            // provided here. A list of valid keys / properties of this Object is available at
            // https://plot.ly/javascript/reference/#layout-xaxis for details, but consider that this class will
            // dynamically create some of them for correctly placing plots on the gird: thus
            // the keys 'domain' and 'anchor' will be ignored (overwritten) if specified.
            //
            // yaxis:
            // a dict of y axis properties. See documentation for 'xaxis'
            // above for details, just replace 'xaxis' with 'yaxis'.

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
                        var color = this.addLegend(mainTrace, mainTrace.name); //sets also mainTrace.legendgroup
                        // set the marker color (marker is visually a bar if mainTrace.type is 'bar'):
                        mainTrace.marker = {color: this.colorMap.transparentize(color, .5)};
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
                            var color = this.addLegend(linregtrace, linregtrace.name, '#331100');
                            linregtrace.line = {color: color};
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
                                var color = this.addLegend(normdistline, normdistline.name, '#331100');
                                normdistline.line = {color: color};
                                
                                var refnormdistline = {
                                    x: x,
                                    y: normdist(x, 0, 1),
                                    type: 'scatter',
                                    mode: 'lines',
                                    name: 'Normal distribution (μ=0, σ=1)',
                                    hovertemplate: `Standard normal distribution (μ=0, σ=1)` +
                                    	`<br>${xlbl}=%{x}<br>${ylbl}=%{y}<extra></extra>`
                                };
                                var color = this.addLegend(refnormdistline, refnormdistline.name, '#999999');
                                refnormdistline.line = {color: color};
        
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
                                var color = this.addLegend(medianline, medianline.name, '#331100');
                                medianline.line = {color: color, dash: 'dot'};
                                
                                var traces = [mainTrace, medianline];
                            }
                        }
                        var plotparams = {gsim: gsim, imt: imt, 'residual type': type};
                        plots.push({
                            traces: traces,
                            params: plotparams,
                            xaxis: { title: plotdata.xlabel },
                            yaxis: { title: plotdata.ylabel }
                        });
                    }
                }
            }
            return plots;
        },
        displayGridLabels: function(axis, paramName, paramValues){
            // this optional method can be implemented to hide the labels of 'paramName' when it is
            // set as grid parameter along the specified axis ('x' or 'y'). If not implemented,
            // by default this method returns true if `paramValues.length > 1` because display the
            // only parameter value on the grid would be redundant and space consuming
            //
            // params:
            // 
            // axis: string, either 'x' or 'y'
            // paramName: the string denoting the parameter name along the given axis
            // paramValues: Array of the values of the parameter keyed by 'paramName'
            return paramValues.length > 1 && paramName != 'imt';  // imt is already shown as y label
        },
        /**configureLayout is the same as the super class 'plot-div' and thus not overwritten.**/
        // END OF OVERRIDABLE METHODS
    },
    computed: {  // "override" compiuted property from superclass
        legendNames: function(){
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