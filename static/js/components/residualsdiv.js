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
            // setup  label texts:
            var data = responseObject;
            var plots = [];
            for (var gsim of Object.keys(data)){
                for (var imt of Object.keys(data[gsim])){
                    for (var type of Object.keys(data[gsim][imt])){
                        var histdata = data[gsim][imt][type];
                        var hist = {
                                x: histdata.x,
                                y: histdata.y,
                                type: 'bar',
                                name: type
                        };
                        var color = this.addLegend(hist, hist.name); //sets also hist.legendgroup
                        hist.marker = {
                                color: color,  // FIXME: we might add alpha channel, it's nicer
                                line: {
                                    color: color,
                                    width: 2
                                }
                        };
                        var x = resample(histdata.x);
                        var normdistline = {
                                x: x,
                                y: normdist(x, histdata.mean, histdata.stddev),
                                type: 'line',
                                name: 'Normal distribution'
                        };
                        var color = this.addLegend(normdistline, normdistline.name, '#000000');
                        normdistline.line = {color: color};
                        
                        var refnormdistline = {
                                x: x,
                                y: normdist(x, 0, 1),
                                type: 'line',
                                name: 'Normal distribution (μ=0, σ=1)'
                        };
                        var color = this.addLegend(refnormdistline, refnormdistline.name, '#999999');
                        refnormdistline.line = {color: color};

                        var plotdata = [hist, normdistline, refnormdistline];
                        var plotparams = {gsim: gsim, imt: imt, 'histogram type': type};
                        plots.push({'traces': plotdata, 'params': plotparams, xaxis:{title: `Z (${imt})`}, yaxis:{title:'Frequency'}});
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
            return ['gsim', 'histogram type'];
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