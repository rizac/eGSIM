Vue.component('trellisdiv', {
    extends: PLOTSDIV,  // defined in plotsdiv.js
    props: {  // props are merged thus plotsdivid will override superclass: we just provide a less general div id to avoid conflicts
        'plotdivid': {type:String, default: 'trellisdiv-plots-container-div'},
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

            // setup  label texts:
            var data = responseObject;
            var plots = [];
            for (var fig of data['figures']){
                var params = {};
                params.xlabel = data['xlabel'];
                params.imt = fig.ylabel;
                params.magnitude = fig.magnitude;
                params.distance = fig.distance;
                params.vs30 = fig.vs30;
                
                var plotData = Object.keys(fig.yvalues).map(function(name){
                    // FIXME: check if with arrow function we can avoid apply and this
                    // to test that plots are correctly placed, uncomment this:
                    // var name = `${name}_${params.magnitude}_${params.distance}_${params.vs30}`;
                    var trace = {
                            x: data.xvalues,
                            y: fig.yvalues[name],
                            mode: (data.xvalues.length == 1 ? 'scatter' : 'lines'),
                            name: name
                    };
                    var color = this.addLegend(name, trace);  // Sets also trace.legendgroup = name
                    if (data.xvalues.length == 1){
                        trace.marker = {color: color};
                    }else{
                        trace.line = {color: color};
                    }
                    return trace;
                }, this);
                plots.push({data: plotData, params: params, xaxis: {title: params.xlabel},
                    yaxis: {title: params.imt, type: 'log'}});
            }
            return plots;
        },
        displayGridX: function(label){
            // this method can be overridden to hide particular grid labels IN THE PLOT along the x axis. By default it returns true
            return label != 'xlabel' && label != 'imt';
        },
        displayGridY: function(label){
            // this method can be overridden to hide particular grid labels IN THE PLOT along the y axis. By default it returns true
            return label != 'xlabel' && label != 'imt';
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