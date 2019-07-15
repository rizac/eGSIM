Vue.component('gmdbplotdiv', {
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
            var jsondict = responseObject;
            // set plotly data from jsondict:
            var trace = {
                    x: jsondict.xvalues,
                    y: jsondict.yvalues,
                    mode: 'markers',
                    type: 'scatter',
                    text: jsondict.labels || [],
                    marker: { size: 10, color: this.colorMap.transparentize(0, .5) },
                    // <extra></extra> hides the second tooltip (white):
                    hovertemplate: `${jsondict.xlabel}=%{x}<br>${jsondict.ylabel}=%{y}`+
                        `<extra></extra>`
                  };
            // modify here the defaut layout:
            // this.defaultlayout.title = `Magnitude Distance plot (${trace.x.length} records in database)`;
            var data = [ trace ];
            var xaxis = {
                type: 'log',
                title: jsondict.xlabel
            };
            var yaxis = {
                title: jsondict.ylabel
            };
            // build the params. Setting just a single param allows us to
            // display a sort of title on the x axis:
            var numFormatted = trace.x.length.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ","); //https://stackoverflow.com/a/2901298
            var title = `${numFormatted} records`;
            if (jsondict.nan_count){
                title += ' (' + jsondict.nan_count + ' NaN records not shown)';
            }
            var params = {'Magnitude Distance plot': title};
            return [{traces: [trace], params: params, xaxis: xaxis, yaxis: yaxis}];
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
            return true;  // we have  single param (sort of title on the x axis), alswya show
        },
        /**configureLayout is the same as the super class 'plotdiv' and thus not overwritten.**/
        // END OF OVERRIDABLE METHODS
    }
});