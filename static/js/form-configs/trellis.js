var TRELLIS = new Vue({
    el: '#trellis',
    data: {
        // NOTE: do not prefix data variable with underscore: https://vuejs.org/v2/api/#data
        plots: [], //array of [data, layout], where data is an array of dicts (one dict per trace) and layout is a dict
        plotmargins: Object.freeze({l: 75, r: 5, b: 30, t: 25, pad: 1}),
        // https://stackoverflow.com/a/44727682:
        defColors: Object.freeze(['#1f77b4',  // muted blue
                                  '#ff7f0e',  // safety orange
                                  '#2ca02c',  // cooked asparagus green
                                  '#d62728',  // brick red
                                  '#9467bd',  // muted purple
                                  '#8c564b',  // chestnut brown
                                  '#e377c2',  // raspberry yogurt pink
                                  '#7f7f7f',  // middle gray
                                  '#bcbd22',  // curry yellow-green
                                  '#17becf']),   // blue-teal
        traceColorIndex: 0,
        traceColors: {},  // map of trellis trace (name) to its color
        paramNames: Object.freeze(['xlabel', 'ylabel', 'vs30', 'magnitude', 'distance']), // a list of default parameter names
        params: {},  // a dict of property names mapped to an array of possible (string) values
        selectedParams: {}, //a dict of property names mapped to a string (scalar) denoting the selected value
                            // that the parameter has to be shown along the 'X' or 'y' axis of the grid
        gridxparam: 'xlabel',  // a key in params denoting the xgrid labels
        gridyparam: 'ylabel',  // a key in params denoting the ygrid labels
        grid: []
        
    },
    created: function() { // https://vuejs.org/v2/api/#created
        // no-op (for the moment)
    },
    methods: {
        init: function(response){
            // reset colors:
            this.$set(this, 'traceColorIndex', 0);
            this.$set(this, 'traceColors', {});
            // convert data:
            var [plots, params] = this.getTrellisData(response);
            this.$set(this, 'plots', plots);
            this.$set(this, 'params', params);
            // update selection, taking into account previously selected stuff:
            this.updateSelection();
        },
        getTrellisData: function(response){
            // we use strings only in params value. Function converting undefined or null to '':
            var str = val => (val === null || val === undefined) ? '' : val+'';
            // setup  label texts:
            var params = {};
            for (var label of this.paramNames){
                params[label] = new Set();
            }
            var data = response.data; //FIXME: how to get data??
            var traceColor = this.traceColor; //instantiate tracecolor once
            var plots = [];
            for (var fig of data['figures']){
                var plotParams = {};
                plotParams.xlabel = str(data['xlabel']);
                plotParams.ylabel= str(fig.ylabel);
                plotParams.magnitude = str(fig.magnitude);
                plotParams.distance = str(fig.distance);
                plotParams.vs30 = str(fig.vs30);

                params.xlabel.add(plotParams.xlabel);
                params.ylabel.add(plotParams.ylabel);
                params.magnitude.add(plotParams.magnitude);
                params.distance.add(plotParams.distance);
                params.vs30.add(plotParams.vs30);
                
                var plotData = Object.keys(fig.yvalues).map(function(name){
                    return {x: data.xvalues, y: fig.yvalues[name], mode: 'lines', name: name,
                                     line: {color: traceColor.apply(this, [name])}};
                });
                var plotLayout = {showlegend: false, margin: this.plotmargins,
                                  xaxis: {title: plotParams.xlabel},
                                  yaxis: {title: plotParams.ylabel, type: 'log'}};
                plots.push({'data': plotData, 'layout': plotLayout, 'params': plotParams});
            }
            // replace sets with sorted Arrays, remove proeprties that are 'empty'
            // (either empty array or ['']):
            for(var key of Object.keys(params)){
                var val = Array.from(params[key]).sort();
                if(!val.length || (val.length==1 && !val[0])){
                    delete params[key];
                    continue;
                }
                params[key] = val;
            }
            return [plots, params];
        },
        updateSelection: function(){
            var params = this.params;
            var gridxlabels = [];
            var gridylabels = [];
            // set default grid for x and y if not found in the new params:
            if (!(this.grixparam in params)){
                this.$set(this, 'gridxparam', 'xlabel'); // xlabel surely in params
            }
            if (!(this.griyparam in params)){
                this.$set(this, 'gridyparam', 'ylabel');  // ylabel surely in params
            }
            var selectedParams = {};
            for (var key of Object.keys(params)){
                var values = params[key];
                var selectedValue = this.selectedParams[key];
                if (!values.includes(selectedValue)){
                    selectedValue = values[0];
                }
                selectedParams[key] = selectedValue;
            }
            this.$set(this, 'selectedParams', selectedParams);
            this.updateGrid();
        },
        updateGrid: function(){
            var [xvalues, yvalues] = [[], []];
            var [xlabel, ylabel] = ['', ''];
            var plots = this.plots;
            var [gridxparam, gridyparam] = [this.gridxparam, this.gridyparam];
            // filter plots (excluding values of param whose names are set for xgrid and ygrid):
            for (var key of Object.keys(this.params)){
                if (key != gridxparam && key != gridyparam){
                    var val = this.selectedParams[key];
                    plots = plots.filter(plot => plot.params[key] == val);
                }
            }
            var [gridxvalues, gridyvalues] = [this.params[gridxparam], this.params[gridyparam]];
            // build the grid:
            var grid = gridyvalues.map((elm) => new Array(gridxvalues.length));
            // map labels to indices (might be done thorugh binary search also, build object of
            // labels mapped to their index is faster):
            var gridxindices = new Map(gridxvalues.map((elm, idx) => [elm, idx]));
            var gridyindices = new Map(gridyvalues.map((elm, idx) => [elm, idx]));
            
            // place plots into the grid:
            plots.forEach(function(plot){
                var gridxindex = gridxindices.get(plot.params[gridxparam]); // plot horizontal index on the grid 
                if(gridxindex !== undefined){
                    var gridyindex = gridyindices.get(plot.params[gridyparam]);  //plot vertical index on the grid
                    if(gridyindex !== undefined){
                        grid[gridyindex][gridxindex] = [plot.data, plot.layout];
                    }
                }
            });
            this.$set(this, 'grid', grid);
            this.$nextTick(this.displayPlots);
        },
        displayPlots: function(){
            //var hidexlabel = this.gridxparam == 'xlabel';
            //var hideylabel = this.gridyparam == 'ylabel';
            var plotly = Plotly;
            for(var row = 0; row < this.grid.length; row++){
                var plotrow = this.grid[row];
                for(var col = 0; col < plotrow.length; col++){
                    var [data, layout] = plotrow[col];
                    var layout = JSON.parse(JSON.stringify(layout)); // copy object
//                    if (hidexlabel){
//                        delete layout.xaxis.title;
//                    }
//                    if (hideylabel){
//                        delete layout.yaxis.title;
//                    }
                    plotly.newPlot(`plot_${row}_${col}`, data, layout);
                }
            }
        },
        styleForAxis: function(axis='x'){
            var count = axis == 'y' ? this.params[this.gridyparam].length : this.params[this.gridxparam].length;
            return {'flex-basis': `${100.0/count}% !important`}
        },
        traceColor: function(traceName){
            var color = this.traceColors[traceName];
            if (!color){
                this.traceColorIndex = (this.traceColorIndex+1) % this.defColors.length;
                color = this.defColors[this.traceColorIndex];
                this.traceColors[traceName] = color;
            }
            return color;
        },
//        isParamChoosable: function(key){
//            return Object.keys(this.params[key]).length > 1;
//        }
    },
    mounted: function() { // https://stackoverflow.com/questions/40714319/how-to-call-a-vue-js-function-on-page-load
        // no -op
    },
    watch: {
        selectedParams: {
            handler: function (newval, oldval) {
                this.updateGrid();
            },
            deep: true  // https://vuejs.org/v2/api/#vm-watch
        },
        gridxparam: function(newval, oldval){
            if (newval == this.gridyparam){
                this.$set(this, 'gridyparam', oldval);
            }
            this.updateGrid();
        },
        gridyparam: function(newval, oldval){
            if (newval == this.gridxparam){
                this.$set(this, 'gridxparam', oldval);
            }
            this.updateGrid();
        }
    },
    computed: {
        selectableParams: function(){
            var ret = {};
            for (var key of Object.keys(this.selectedParams)){
                if (key != this.gridxparam && key !=this.gridyparam &&  Object.keys(this.params[key]).length > 1){
                    ret[key] = this.params[key];
                }
            }
            return ret;
        }
        // https://stackoverflow.com/a/47044150
        // no -op
    }
});