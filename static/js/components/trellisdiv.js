Vue.component('trellisdiv', {
    props: {
        'url': String,
        'eventbus': {default: null}
    },
    data: function(){
        return {
            // NOTE: do not prefix data variable with underscore: https://vuejs.org/v2/api/#data
            initialized: false,
            plots: [], //array of [{data, params}], where data is an array of dicts (one dict per trace) and params is a dict
            paramNames: Object.freeze(['xlabel', 'ylabel', 'vs30', 'magnitude', 'distance']), // a list of default parameter names
            params: {},  // a dict of property names mapped to an array of possible (string) values
            selectedParams: {}, //a dict of property names mapped to a string (scalar) denoting the selected value
                                // that the parameter has to be shown along the 'X' or 'y' axis of the grid
            gridxparam: 'xlabel',  // a key in params denoting the xgrid labels
            gridyparam: 'ylabel',  // a key in params denoting the ygrid labels
            plotlyplots: [],  // subset of plots, with only the currently displayed plots
            plotlydata: [],  // the `data` argument passed to Plotly.newPlot(data, ...) holding the traces
            plotDivId: 'trellis-plots-container',
            plotFontSize: 12,
            colorMap: Vue.colorMap(),  // defined in vueutil.js
        }
    },
    template: `<div id='trellisdiv' v-show='initialized'>
        
        <div class='flexible position-relative'>
            <div class='position-absolute pos-0' id='trellis-plots-container'></div>
        </div>
    
        <div class='trellis-right-panel flex-direction-col p-2 pl-3'>
            <div>
                <button @click="toggleShowInputForm">params</button>
            </div>
            <h5 class='pt-3'>Legend</h5>
            <div class='flexible pt-3'>
                <div v-for="(value, key) in colorMap.asObject">
                    <label v-bind:style="{color: value}">
                        <input type='checkbox' v-bind:checked="isTraceVisible(key)" v-on:click="toggleTraceVisibility(key)">
                        {{ key }}
                    </label>
                </div>
            </div>
            <h5 class='pt-3'>Display</h5>
            <div>
                <div v-for='(values, key) in selectableParams'>
                    <div>{{ key }}:</div>
                    <select class='form-control' v-model="selectedParams[key]">
                        <option v-for='value in params[key]'>
                            {{ value }}
                        </option>
                    </select>
                </div>
            </div>
            <div>
                <div>Group vertically by:</div>
                <select class='form-control' v-model='gridyparam'>
                    <option v-for='key in groupableParams' v-bind:value="key">
                        {{ key == 'ylabel' ? 'imt' : key }}
                    </option>
                </select>
            </div>
            <div>
                <div>Group horizontally by:</div>
                <select class='form-control' v-model='gridxparam'>
                    <option v-for='key in groupableParams' v-bind:value="key">
                       {{ key == 'ylabel' ? 'imt' : key }}
                    </option>
                </select>
            </div>
        </div>
     
    </div>`,
    created: function() { // https://vuejs.org/v2/api/#created
        if (this.eventbus){
            this.eventbus.$on('postresponse', (response, isError) => {
                if (response.config.url == this.url && !isError){
                    this.init.call(this, response.data);
                }
            });
        }
    },
    methods: {
        init: function(jsondict){
            this.$set(this, 'initialized', true);
            // convert data:
            var [plots, params] = this.getTrellisData(jsondict);
            this.$set(this, 'plots', plots);
            this.$set(this, 'params', params);
            // update selection, taking into account previously selected stuff:
            this.updateSelection();
        },
        getTrellisData: function(data){
            // we use strings only in params value. Function converting undefined or null to '':
            var str = val => (val === null || val === undefined) ? '' : val+'';
            // setup  label texts:
            var params = {};
            for (var label of this.paramNames){
                params[label] = new Set();
            }
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
                    var [x, y] = [data.xvalues, fig.yvalues[name]];
                    // to test that plots are correctly placed, uncomment this:
                    // var name = `${name}_${plotParams.magnitude}_${plotParams.distance}_${plotParams.vs30}`;
                    return {x: x, y: y, mode: (data.xvalues.length == 1 ? 'scatter' : 'lines'),
                        visible: true,
                        legendgroup: name, name: name, line: {color: this.colorMap.get(name)}};
                }, this);
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
            if (!(this.gridxparam in params)){
                this.$set(this, 'gridxparam', 'xlabel'); // xlabel surely in params
            }
            if (!(this.gridyparam in params)){
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
        displayPlots: function(divId){  //divId optional, it defaults to this.plotDivId if missing
            var layout = this.getLayout();  // instantiate first cause we will change its showlegend value below:
            if(divId === undefined){
                divId = this.plotDivId;
                layout.showlegend = false;
            }
            Plotly.purge(divId);  // do we need this?
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
            var xdomains = new Array(gridxvalues.length);
            var ydomains = new Array(gridyvalues.length);
            var annotation = this.getAnnotation;
            var legendgroups = new Set();
            for (var plot of this.plotlyplots){
                var gridxvalue = plot.params[gridxparam];
                var gridxindex = gridxindices.get(gridxvalue); // plot horizontal index on the grid 
                if(gridxindex === undefined){continue;}
                var gridyvalue = plot.params[gridyparam];
                var gridyindex = gridyindices.get(gridyvalue);  //plot vertical index on the grid
                if(gridyindex === undefined){continue;}
                var [axisIndex, xaxis, yaxis, xdomain, ydomain] = this.getAxis(divId, gridyindex, gridxindex, gridyvalues.length, gridxvalues.length);
                xdomains[gridxindex] = xaxis.domain;
                ydomains[gridyindex] = yaxis.domain;
                yaxis.type = 'log';
                layout[`xaxis${axisIndex}`] = xaxis;
                layout[`yaxis${axisIndex}`] = yaxis;
                // Now edit the traces in plot.data. Each trace is basically an Object of the
                // form T = {x: ..., y: ...}. The trace properties below need to be modified EACH TIME:
                // 1. T.xaxis and T.yaxis (i.e., basically on which subplot the trace has to be displayed), and
                // 2. T.showlegend. The latter is set to true for the FIRST trace found for a given legendgroup
                // in order to avoid duplicated legend names. (T.legendgroup = T.name is the GSIM name, and it allows
                // toggling visibility simultaneously on all subplots for every trace with the same legendgroup, when 
                // clicking on the legend's GSIM name)
                plot.data.forEach(function(element){
                    element.xaxis = `x${axisIndex}`;
                    element.yaxis = `y${axisIndex}`;
                    element.showlegend = !legendgroups.has(element.legendgroup);
                    legendgroups.add(element.legendgroup);
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
          // Grid X labels: (horizontally on top)
          var [gridxparam, gridyparam] = this.getDisplayGridParams();
          if (gridxparam){
              // determine the maximum y of all plot frames:
              // var y = Math.max(...ydomains.map(elm => elm[1]));
              // create the x labels of the vertical grid:
              for (var [domain, gridvalue] of xdomains.map((elm, index) => [elm, gridxvalues[index]])){
                  layout.annotations.push(annotation({
                      x: (domain[1] + domain[0])/2,
                      y: 1,
                      xanchor: 'center', /* DO NOT CHANGE THIS */
                      yanchor: 'top',
                      text: `${gridxparam}: ${gridvalue}`
                }));
              }
          }
          // Grid Y labels: (vertically on the right)
          if (gridyparam){
              // determine the maximum x of all plot frames:
              // var x = Math.max(...xdomains.map(elm => elm[1]));
              // create the y labels of the vertical grid:
              for (var [domain, gridvalue] of ydomains.map((elm, index) => [elm, gridyvalues[index]])){
                  layout.annotations.push(annotation({
                      x: 1,
                      y: (domain[1] + domain[0])/2,
                      xanchor: 'right',
                      yanchor: 'middle', /* DO NOT CHANGE THIS */
                      text: `${gridyparam}: ${gridvalue}`,
                      textangle: '-270'
                }));
              }
          }
          this.$set(this, 'plotlydata', data);
          Plotly.newPlot(divId, data, layout);
        },
        getLayout: function(){
            return {autosize: true, font: {family: "Encode Sans Condensed, sans-serif", size: this.plotFontSize},
                showlegend: true,
                margin: {r: 0, b: 0, t: 0, l:0, pad:0}, annotations: []};
        },
        getAxis: function(divId, row, col, rows, cols){
            // computes the sub-plot area according to the row and col index
            // returns the array [axisIndex, xaxis, yaxis, xdomain, ydomain]
            // where xaxis and yaxis are the Objects to be passed to plotly's layout, xdomain = [x1, x2] and
            // ydomain = [y1, y2] are the two-element arrays denoting the enclosing area of the sub-plot
            var [uwidth, uheight] = this.getEmUnits(divId, this.plotFontSize);
            var [gridxparam, gridyparam] = this.getDisplayGridParams();
            var tt = gridxparam ? 1.5 * uheight : 0;
            var rr = gridyparam ? 3 * uwidth : 0;
            // the legend, if present, is not included in the plot area, so we can safely ignore it. Comment this line:
            // rr += 0. * uwidth * Math.max(...Object.keys(this.plotTraceColors).map(elm => elm.length)) ;
            var axisIndex = 1 + row * cols + col;
            // assure the width is at least a font unit assuming 10px as minimum):
            var [minuwidth, minuheight] = this.getEmUnits(divId, 10);
            // calculate plot width and height:
            var colwidth = Math.max(minuwidth, (1-rr) / cols);
            var rowheight = Math.max(minuheight, (1-tt) / rows);
            // determine the xdomain [x0, x1] defining the enclosing plot frame width (including ylabel):
            var xdomain = [col*colwidth, (1+col)*colwidth];
            // determine the ydomain [y0, y1] defining the enclosing plot frame height (including xlabel):
            var ydomain = [(rows-row-1)*rowheight, (rows-row)*rowheight]; // (y coordinate 0 => bottom , 1 => top)
            // define now the plotly x and y domains, which do NOT include x and y labels. Define paddings:
            var b = 3 * uheight;
            var t = 1 * uheight;
            var l = 4.5 * uwidth;
            var r = 1 * uwidth;
            // now define domains:
            var xaxisdomain = [xdomain[0]+l, xdomain[1]-r];
            var yaxisdomain = [ydomain[0]+b, ydomain[1]-t];
            // check that the domains are greater than a font unit:
            if (xaxisdomain[1] - xaxisdomain[0] < minuwidth){
                xaxisdomain = xdomain;
            }
            // check that the domains are greater than a font unit:
            if (yaxisdomain[1] - yaxisdomain[0] < minuheight){
                yaxisdomain = ydomain;
            }
            var xaxis = {mirror: true, linewidth: 1, domain: xaxisdomain, anchor: `y${axisIndex}`};
            var yaxis = {mirror: true, linewidth: 1, domain: yaxisdomain, anchor: `x${axisIndex}`};
            //console.log('xdomain:' + xdomain); console.log('ydomain:' + ydomain);
            return [axisIndex, xaxis, yaxis, xdomain, ydomain];
        },
        getEmUnits: function(divId, fontsize){
            // returns [uwidth, uheight], the units of a 1em in percentage of the plot div, which must be shown on the browser
            // Both returned units should be < 1 in principle
            var fontsize = this.plotFontSize;
            var [width, height] = this.getPlotDivSize(divId);
            return [fontsize/width, fontsize/height];
        },
        getAnnotation(props){
            return Object.assign({
                xref: 'paper',
                yref: 'paper',
                showarrow: false,
                font: {size: this.plotFontSize}
          }, props || {});
        },
        getPlotDivSize: function(divId){
            var elm = document.getElementById(divId);
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
        toggleTraceVisibility: function(traceName){
            var indices = [];
            var visible = undefined;
            for(var i=0; i< this.plotlydata.length; i++){
                var data = this.plotlydata[i];
                if(data.legendgroup != traceName){
                    continue;
                }
                indices.push(i);
                if(visible === undefined){
                    visible = data.visible;  // only first time
                }
            }
            if(indices.length){
                Plotly.restyle(this.plotDivId, {visible: !visible}, indices);
            }
        },
        isTraceVisible: function(traceName){  // could be optimized avoiding for loop...
            for(var i=0; i< this.plotlydata; i++){
                var data = this.plotlydata[i];
                if(data.legendgroup != traceName){
                    continue;
                }
                return data.visible;
            }
            return true;
        },
        toggleShowInputForm: function(){
            if(this.eventbus){
                this.eventbus.$emit('toggletrellisformvisibility');
            }
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