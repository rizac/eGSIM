Vue.component('residualsdiv', {
    extends: PLOTSDIV,  // defined in plotsdiv.js
    props: {  // props are merged thus plotsdivid will override superclass: we just provide a less general div id to avoid conflicts
        'plotdivid': {type:String, default: 'residualsdiv-plots-container-div'},
    },
    methods: {
        // methods to be overridden:
        getData: function(responseObject){
            // initializes the response object into an Array of [[traces, params, xaxis, yaxis], ... ] element, and returns the Array.
            // each element [traces, params, xaxis, yaxis] represents a (sub)Plot and must be:
            // traces: an Array of valid representable plotly objects, each Object might be e.g.:
            //         {x: Array, y: Array, name: string}.
            //     plus any other attribute necessary to display the trace.
            //     NOTE: To add a unique color mapped to a trace id (e.g. the trace name), setup the legendgroup and
            //     automatically map the trace to a legend item toggling the trace visibility, use color = this.addLegend(name), e.g.:
            //         var trace = {x: Array, y: Array, name: 'mytrace'}
            //         var color = this.addLegend(trace.name)  // this sets also trace.legendgroup=traceName
            //         trace.line = {color: color}  // set the trace color to the legend assigned color
            // params: an Object of selectable params (string) mapped to the plot specific values (e.g. {magnitude: 5, 'xlabel: 'PGA'})
            //     each element's params Object should have the same keys
            // xaxis: a dict of x axis properties. Example: {title: 'plottitle', type: 'log'}
            //     The properties 'domain' and 'anchor' will be overridden. 
            //     The Object returned here will be merged with the properties defined this.defaultxaxis (in case of conflicts,
            //     the properties of this.defaultxaxis will be overridden)
            // yaxis: a dict of y axis properties. Example: {title: 'plottitle', type: 'log'}
            //     The properties 'domain' and 'anchor' will be overridden. 
            //     The Object returned here will be merged with the properties defined this.defaultyaxis (in case of conflicts,
            //     the properties of this.defaultyaxis will be overridden)

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
                                type: 'bar'
                        };
                        var color = this.addLegend(gsim, hist); //sets also plotData.legendgroup
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
                                type: 'line'
                        };
                        var color = this.addLegend('Normal distribution', normdistline);
                        normdistline.line = {color: color};
                        
                        var refnormdistline = {
                                x: x,
                                y: normdist(x, 0, 1),
                                type: 'line'
                        };
                        var color = this.addLegend('Normal distribution (mean=0, stddev=1)', refnormdistline);
                        refnormdistline.line = {color: color};

                        var plotdata = [hist, normdistline, refnormdistline];
                        var plotparams = {gsim: gsim, imt: imt, 'histogram type': type};
                        plots.push({'data': plotdata, 'params': plotparams, xaxis:{title: `Z (${imt})`}, yaxis:{title:'Frequency'}});
                    }
                }
            }
            return plots;
        },
        displayGridX: function(label){
            // this method can be overridden to hide particular grid labels IN THE PLOT along the x axis. By default it returns true
            return label != 'imt'; // && label != 'gsim';
        },
        displayGridY: function(label){
            // this method can be overridden to hide particular grid labels IN THE PLOT along the y axis. By default it returns true
            return label != 'imt'; // && label != 'gsim';
        },
        configureLayout: function(layout){
            // remove or add properties to the plotly layout Object, which is passed here as argument as a shallow copy of
            // this.defaultlayout.
            // Note that the layout font size and family will be set according to this.plotfontsize and the <body> font
            // family, because the font size
            // is used to calculate plots area and cannot be changed. By default, this function does nothing and returns
            return
        },
        // END OF OVERRIDABLE METHODS
    }
});