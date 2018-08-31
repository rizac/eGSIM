Vue.component('residualsdiv', {
    extends: PLOTSDIV,  // defined in plotsdiv.js
    methods: {
        // methods to be overridden:
        getData: function(responseObject){
            // this method needs to be implemented in order to initialize the response object into
            // an Array of sub-plots, and return that Array: each Array element (or "sub-plot")
            // need to be a js Object of the form:
            // {traces: Array, params: Object, xaxis: Object, yaxis: Object} where:
            //
            // traces:
            // an Array of valid representable plotly objects e.g. {x: Array, y: Array, name: string}
            // (providing a `name` key makes the name showing when hovering over the trace with
            // the mouse. For other keys, refer to plotly doc for details). The object keys
            // `xaxis`, 'yaxis', 'showlegend' needs not to be specified as they will be overridden.
            // NOTE: To add a unique color mapped to a trace id (e.g. the trace name) and
            // setup the legendgroup and automatically map the trace to a legend item toggling
            // the trace visibility, use `this.addLegend(trace, key)`, e.g.:
            //
            //   var trace = {x: Array, y: Array, name: 'mytrace'}
            //   var color = this.addLegend(trace, trace.name)
            //   trace.line = {color: color}  // set the trace color to the legend assigned color
            //
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
            // (e.g. {magnitude: 5, 'xlabel: 'PGA'}). This object should have always the same keys
            // and at least two keys in order to map them to the x and y grid (see `defaultGridParams`)
            //
            // xaxis:
            // a dict of x axis properties. Example: {title: 'plottitle', type: 'log'}
            // The properties 'domain' and 'anchor' needs not to be specified as they will be overridden. 
            // The Object returned here will be merged with the properties defined this.defaultxaxis
            // (in case of conflicts, the properties of this.defaultxaxis will be overridden)
            //
            // yaxis:
            // a dict of y axis properties. Example: {title: 'plottitle', type: 'log'}
            // The properties 'domain' and 'anchor' needs not to be specified as they will be overridden. 
            // The Object returned here will be merged with the properties defined this.defaultyaxis
            // (in case of conflicts, the properties of this.defaultyaxis will be overridden)

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
            var resample = function(array, granularity=5){
                var newarray = array;
                if (granularity > 1 && array.length > 1){
                    newarray = [];
                    for (var i=1; i< array.length; i++){
                        var step = (array[i] - array[i-1])/granularity;
                        for(var j=0; j<granularity; j++){
                            newarray.push(array[i-1] + step*j);
                        }
                    }
                    newarray.push(array[array.length-1]);
                }
                return newarray;
            };
            var endpoints = function(array){
                var [min, max] = [undefined, undefined];
                if (array.length > 0){
                    min = max = array[0];
                }
                for(var i=1; i < array.length; i++){
                    var val = array[i];
                    if (val < min){
                        min = val;
                    }else if (val > max){
                        max = val;
                    }
                }
                return [min, max];
            };
            // setup  plots:
            var data = responseObject;
            var plots = [];
            for (var gsim of Object.keys(data)){
                for (var imt of Object.keys(data[gsim])){
                    for (var type of Object.keys(data[gsim][imt])){
                        var plotdata = data[gsim][imt][type];
                        var scatterPlot = 'intercept' in plotdata && 'slope' in plotdata;
                        var mainTrace = {
                                x: plotdata.x,
                                y: plotdata.y,
                                type: scatterPlot ? 'scatter' : 'bar',
                                name: type
                        };
                        var color = this.addLegend(mainTrace, mainTrace.name); //sets also mainTrace.legendgroup
                        // set the marker color (marker is visually a bar if mainTrace.type is 'bar'):
                        mainTrace.marker = {color: color};
                        // add other stuff (normal distributions, regression lines, ...):
                        if (scatterPlot){
                            mainTrace.mode = 'markers';  // hide connecting lines
                            mainTrace.marker.size = 10;
                            // show linear regression according to slope and intercept:
                            var [min, max] = endpoints(plotdata.x);
                            var [slope, intercept] = [plotdata.slope, plotdata.intercept];
                            var linregtrace = {
                                    x: [min, max],
                                    y: [min*slope+intercept, max*slope+intercept],
                                    type: 'line',
                                    name: 'Linear regression'
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
                            // show normal distribution and reference normal dist. (mean=0 sigma=1)
                            var x = resample(plotdata.x);
                            var normdistline = {
                                    x: x,
                                    y: normdist(x, plotdata.mean, plotdata.stddev),
                                    type: 'line',
                                    name: 'Normal distribution'
                            };
                            var color = this.addLegend(normdistline, normdistline.name, '#331100');
                            normdistline.line = {color: color};
                            
                            var refnormdistline = {
                                    x: x,
                                    y: normdist(x, 0, 1),
                                    type: 'line',
                                    name: 'Normal distribution (μ=0, σ=1)'
                            };
                            var color = this.addLegend(refnormdistline, refnormdistline.name, '#999999');
                            refnormdistline.line = {color: color};
    
                            var traces = [mainTrace, normdistline, refnormdistline];
                        }
                        var plotparams = {gsim: gsim, imt: imt, 'residual type': type};
                        plots.push({'traces': traces, 'params': plotparams, xaxis:{title: plotdata.xlabel}, yaxis:{title: plotdata.ylabel}});
                    }
                }
            }
            return plots;
        },
        defaultGridParams: function(params){
            // this optional method can be implemented to return an array [xKey, yKey] representing
            // the default param names of the grid along the x and y axis, respectively.
            // xKey and yKey should be keys of the params argument (js Object).
            // If not implemented, by default this method returns the first 2 values of `Object.keys(params)`
            
            // provide different defaults (see `getData` above):
            return ['gsim', 'residual type'];
        },
        displayGrid: function(paramName, axis){
            // this optional method can be implemented to hide particular grid labels IN THE PLOT along the
            // specified axis ('x' or 'y'). If not implemented, by default this method returns true
            
            // show grid params except when the param name is 'imt':
            return paramName != 'imt';
        },
        configureLayout: function(layout){
            // this optional method can be implemented to remove or add properties to the plotly `layout`
            // Object, which is passed as shallow copy of `this.defaultlayout` (defined in `plotsdiv`).
            // If not implemented, this method by default does nothing and returns.
            // Note that the layout font size and family will be set according to `this.plotfontsize`
            // and the <body> font family, because the font size is used to calculate plots area
            // and cannot be changed. 

            return
        },
        // END OF OVERRIDABLE METHODS
    }
});