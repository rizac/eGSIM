Vue.component('trellisplotdiv', {
    extends: _PLOT_DIV,  // defined in plotdiv.js
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

            // setup  label texts:
            var data = responseObject;
            var plots = [];
            for (var fig of data['figures']){
                var params = {};
                // params.xlabel = data['xlabel'];
                params.imt = fig.ylabel;
                params.magnitude = fig.magnitude;
                params.distance = fig.distance;
                params.vs30 = fig.vs30;
                
                var traces = Object.keys(fig.yvalues).map(function(name){
                    // FIXME: check if with arrow function we can avoid apply and this
                    // to test that plots are correctly placed, uncomment this:
                    // var name = `${name}_${params.magnitude}_${params.distance}_${params.vs30}`;
                    var trace = {
                            x: data.xvalues,
                            y: fig.yvalues[name],
                            type: 'scatter',
                            mode: (data.xvalues.length == 1 ? 'markers' : 'lines'),
                            name: name
                    };
                    var color = this.addLegend(trace, name);  // Sets also trace.legendgroup = name
                    if (data.xvalues.length == 1){
                        trace.marker = {color: color};
                    }else{
                        trace.line = {color: color};
                    }
                    return trace;
                }, this);
                plots.push({
                    traces: traces,
                    params: params,
                    xaxis: {
                        title: data['xlabel']
                    },
                    yaxis: {
                        title: params.imt, type: 'log'
                    }
                });
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
        /**configureLayout is the same as the super class 'plotdiv' and thus not overwritten.**/
        // END OF OVERRIDABLE METHODS
    }
});