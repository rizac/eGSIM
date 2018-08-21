Vue.component('gmdbmagdistdiv', {
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
            var jsondict = responseObject;
            // set plotly data from jsondict:
            var trace = {
                    x: jsondict['x'],
                    y: jsondict['y'],
                    mode: 'markers',
                    type: 'scatter',
                    text: jsondict['labels'] || [],
                    marker: { size: 10 }
                  };
            // modify here the defaut layout:
            // this.defaultlayout.title = `Magnitude Distance plot (${trace.x.length} records in database)`;
            var data = [ trace ];
            var xaxis = {
                type: 'log',
                title: jsondict['xlabel']
            };
            var yaxis = {
                title: jsondict['ylabel']
            };
            // build the params. This is a hack to display a plot title. See also `defaultGridParams`
            // Note that the 'y' key can be mapped to any string value because it will not be displayed.
            // (however, the value cannot be the empty string otherwise the key will be removed
            // and this causes a problem because we need at least two params for the grid)
            var params = {'Magnitude Distance plot': `${trace.x.length} records in database`, 'y': 'y'};
            return [{traces: [trace], params: params, xaxis: xaxis, yaxis: yaxis}];
        },
        defaultGridParams: function(params){
            // this optional method can be implemented to return an array [xKey, yKey] representing
            // the default param names of the grid along the x and y axis, respectively.
            // xKey and yKey should be keys of the params argument (js Object).
            // If not implemented, by default this method returns the first 2 values of `Object.keys(params)`
            var keys = Object.keys(params);
            return keys[0] == 'y' ? [keys[1], keys[0]] : [keys[0], keys[1]];
        },
        displayGrid: function(paramName, axis){
            // this optional method can be implemented to hide particular grid labels IN THE PLOT along the
            // specified axis ('x' or 'y'). If not implemented, by default this method returns true

            // display only the x grid:
            return axis == 'x';
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