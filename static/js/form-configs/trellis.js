var TRELLIS = new Vue({
    el: '#trellis',
    data: {
        // NOTE: do not prefix data variable with underscore: https://vuejs.org/v2/api/#data
        plots: [], //array of [{data, params}], where data is an array of dicts (one dict per trace) and params is a dict
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
        //defAxisProps: {mirror: true, linewidth: 1},  //, titlefont: {size: 12}},
        traceColorIndex: 0,
        traceColors: {},  // map of trellis trace (name) to its color
        paramNames: Object.freeze(['xlabel', 'ylabel', 'vs30', 'magnitude', 'distance']), // a list of default parameter names
        params: {},  // a dict of property names mapped to an array of possible (string) values
        selectedParams: {}, //a dict of property names mapped to a string (scalar) denoting the selected value
                            // that the parameter has to be shown along the 'X' or 'y' axis of the grid
        gridxparam: 'xlabel',  // a key in params denoting the xgrid labels
        gridyparam: 'ylabel',  // a key in params denoting the ygrid labels
        plotlyplots: [],
        plotDivId: 'trellis-plots-container',
        plotFontSize: 11
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
                plotParams.xlabel = data['xlabel'];
                plotParams.ylabel= fig.ylabel;
                plotParams.magnitude = fig.magnitude;
                plotParams.distance = fig.distance;
                plotParams.vs30 = fig.vs30;

                params.xlabel.add(plotParams.xlabel);
                params.ylabel.add(plotParams.ylabel);
                params.magnitude.add(plotParams.magnitude);
                params.distance.add(plotParams.distance);
                params.vs30.add(plotParams.vs30);
                
                var plotData = Object.keys(fig.yvalues).map(function(name){
                    return {x: data.xvalues, y: fig.yvalues[name], mode: (data.xvalues.length == 1 ? 'scatter' : 'lines'),
                        name: name, line: {color: traceColor.apply(this, [name])}};
                });
                plots.push({'data': plotData, 'params': plotParams});
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
            this.$set(this, 'plotlyplots', plots);
            this.$nextTick(this.displayPlots);
        },
        displayPlots: function(){
            // diplsays subplot in the main plot. This method does some calculation that plotly
            // does not, such as font-size dependent margins, and moreover fixes a bug whereby the xaxis.title
            // annotation texts are misplaced (thus let's place them manually here)
            var [gridxparam, gridyparam] = [this.gridxparam, this.gridyparam];
            var [gridxvalues, gridyvalues] = [this.params[gridxparam], this.params[gridyparam]];
            // map labels to indices (might be done thorugh binary search also, build object of
            // labels mapped to their index is faster):
            var gridxindices = new Map(gridxvalues.map((elm, idx) => [elm, idx]));
            var gridyindices = new Map(gridyvalues.map((elm, idx) => [elm, idx]));
            var data = [];
            var getAxis = this.getAxis;
            var xdomains = new Array(gridxvalues.length);
            var ydomains = new Array(gridyvalues.length);
            var annotation = this.getAnnotation;
            var layout = this.getLayout();
            for (var plot of this.plotlyplots){
                var gridxvalue = plot.params[gridxparam];
                var gridxindex = gridxindices.get(gridxvalue); // plot horizontal index on the grid 
                if(gridxindex === undefined){continue;}
                var gridyvalue = plot.params[gridyparam];
                var gridyindex = gridyindices.get(gridyvalue);  //plot vertical index on the grid
                if(gridyindex === undefined){continue;}
                var [axisIndex, xaxis, yaxis, xdomain, ydomain] = getAxis(gridyindex, gridxindex, gridyvalues.length, gridxvalues.length);
                xdomains[gridxindex] = xaxis.domain;
                ydomains[gridyindex] = yaxis.domain;
                yaxis.type = 'log';
                layout[`xaxis${axisIndex}`] = xaxis;
                layout[`yaxis${axisIndex}`] = yaxis;
                plot.data.forEach(function(element){
                    element.xaxis = `x${axisIndex}`;
                    element.yaxis = `y${axisIndex}`;
                    data.push(element);
                });
                // write xlabel:
                layout.annotations.push(annotation({
                    x: (xaxis.domain[1]+xaxis.domain[0])/2,
                    y: ydomain[0],
                    xanchor: 'center',
                    yanchor: 'bottom',
                    text: plot.params.xlabel
                }));
                // and ylabel:
                layout.annotations.push(annotation({
                    x: xdomain[0],
                    y: (yaxis.domain[1]+yaxis.domain[0])/2,
                    xanchor: 'left',
                    yanchor: 'middle',
                    textangle: '-90',
                    text: plot.params.ylabel
                }));
          }
          // write xgridparams and ygridparams
          var [gridxparam, gridyparam] = this.getDisplayGridParams();
          if (gridxparam){
              for (var domain of xdomains){
                  layout.annotations.push(annotation({
                      x: (domain[1] + domain[0])/2,
                      y: 1,
                      xanchor: 'center',
                      yanchor: 'top',
                      text: `${gridxparam}: ${gridxvalues[index]}`
                }));
              }
          }
          if (gridyparam){
              for (var domain of ydomains){
                  layout.annotations.push(annotation({
                      x: 1,
                      y: (domain[1] + domain[0])/2,
                      xanchor: 'right',
                      yanchor: 'middle',
                      text: `${gridyparam}: ${gridyvalues[index]}`,
                      textangle: '-270'
                }));
              }
          }
            Plotly.newPlot(this.plotDivId, data, layout);
        },
        getLayout: function(){
            return {autosize: true, font: {size: this.plotFontSize}, titlefont: {size: 11}, showlegend: false,
                margin: {r: 0, b: 0, t: 0, l:0, pad:0}, annotations: []};
        },
        getAxis: function(row, col, rows, cols){
            // computes the sub-plot area according to the row and col index
            // returns the array [axisIndex, xaxis, yaxis, xdomain, ydomain]
            // where xaxis and yaxis are the Objects to be passed to plotly's layout, xdomain = [x1, x2] and
            // ydomain = [y1, y2] are the two-element arrays denoting the enclosing area of the sub-plot
            var fontsize = this.plotFontSize;
            var [width, height] = this.getPlotDivSize();
            var [uwidth, uheight] = [fontsize/width, fontsize/height];
            var b = 3 * uheight;
            var t = 1.5 * uheight;
            var l = 5 * uwidth;
            var r = 1.5*uwidth;
            var [gridxparam, gridyparam] = this.getDisplayGridParams();
            var tt = gridxparam ? 2 * uheight : 0;
            var rr = gridyparam ? 2 * uwidth : 0;
            var axisIndex = 1 + row * cols + col;
            var colwidth = (1-rr) / cols;
            var rowheight = (1-tt) / rows;
            var xdomain = [col*colwidth, (1+col)*colwidth];
            var ydomain = [(rows-1-row)*rowheight, (rows-row)*rowheight];
            var xaxis = {mirror: true, linewidth: 1, domain: [xdomain[0]+l, xdomain[1]-r], anchor: `y${axisIndex}`};
            var yaxis = {mirror: true, linewidth: 1, domain: [ydomain[0]+b, ydomain[1]-t], anchor: `x${axisIndex}`};
            return [axisIndex, xaxis, yaxis, xdomain, ydomain];
        },
        getAnnotation(props){
            return Object.assign({
                xref: 'paper',
                yref: 'paper',
                showarrow: false
          }, props || {});
        },
        getPlotDivSize: function(){
            var elm = document.getElementById(this.plotDivId);
            return [elm.offsetWidth, elm.offsetHeight];
        },
        styleForAxis: function(axis='x'){
            var count = axis == 'y' ? this.params[this.gridyparam].length : this.params[this.gridxparam].length;
            return {'flex-basis': `${100.0/count}% !important`}
        },
        getDisplayGridParams: function(){
            var gridxparam = this.gridxparam == 'xlabel' || this.gridxparam == 'ylabel' ? '' : this.gridxparam;
            var gridyparam = this.gridyparam == 'xlabel' || this.gridyparam == 'ylabel' ? '' : this.gridyparam;
            return [gridxparam, gridyparam];
        },
        traceColor: function(traceName){
            var color = this.traceColors[traceName];
            if (!color){
                this.traceColorIndex = (this.traceColorIndex+1) % this.defColors.length;
                color = this.defColors[this.traceColorIndex];
                this.traceColors[traceName] = color;
            }
            return color;
        }
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
    computed: {  // https://stackoverflow.com/a/47044150
        selectableParams: function(){
            var ret = {};
            for (var key of Object.keys(this.selectedParams)){
                if (key != this.gridxparam && key != this.gridyparam && Object.keys(this.params[key]).length > 1){
                    ret[key] = this.params[key];
                }
            }
            return ret;
        },
        groupableParams: function(){
            var me = this;
            return Object.keys(this.selectedParams).filter(function(key){
                return key == 'xlabel' || key == 'ylabel' || Object.keys(me.params[key]).length > 1;
            });
        }
    }
});

class Colors {
    constructor() {
        // https://stackoverflow.com/a/44727682:
        this.$colors = Object.freeze(['#1f77b4',  // muted blue
                '#ff7f0e',  // safety orange
                '#2ca02c',  // cooked asparagus green
                '#d62728',  // brick red
                '#9467bd',  // muted purple
                '#8c564b',  // chestnut brown
                '#e377c2',  // raspberry yogurt pink
                '#7f7f7f',  // middle gray
                '#bcbd22',  // curry yellow-green
                '#17becf']);   // blue-teal
        this.$index = 0;
    }
    color(name) {
        if (!(name in this)){
            this.$index = (this.$index+1) % this.$colors.length;
            this[name] = this.$colors[this.$index];
        }
        return this[name];
    }
}