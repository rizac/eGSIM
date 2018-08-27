var PLOTSDIV = Vue.component('plotsdiv', {
    props: {
        'url': String,
        'eventbus': {default: null},
        'plotfontsize': {type: Number, default: 12}  // this is used to calculate plot areas and set it in the default layout
    },
    data: function(){
        // unique id based on the component name (note that if this is called by a subclass, then this.$options.name is the subclass name)
        var id = this.$options.name + new Date().getTime().toString();
        return {
            plotdivid: id,
            // NOTE: do not prefix data variable with underscore: https://vuejs.org/v2/api/#data
            initialized: false,
            legend: {}, // an Object of names -> html color (string) values
            plots: [], //array of [{traces, params}], where traces is an Array of Objects representing the plot traces, and params is an Object
            params: {},  // a dict of property names mapped to an array of possible (string) values
            selectedParams: {}, //a dict of property names mapped to a string (scalar) denoting the selected value
                                // that the parameter has to be shown along the 'X' or 'y' axis of the grid
            gridxparam: '',  // a key in params denoting the xgrid labels. 
            gridyparam: '',  // a key in params denoting the ygrid labels
            plotlydata: [],  // the `data` argument passed to Plotly.newPlot(data, ...) holding the traces
            // this default objects will be copied into the layout, xaxis, and yaxis objects (the latter two are instantiated
            // for each sub-plot, the former only once per plot). The values can anyway be overridden, provide here only
            // common defaults:
            defaultlayout: {autosize: true,
                // font: {family: "Encode Sans Condensed, sans-serif", size: 12}, // this will be overridden
                showlegend: false,
                margin: {r: 0, b: 0, t: 0, l:0, pad:0}, annotations: []},
            defaultxaxis: {mirror: true, zeroline: false, linewidth: 1},  // domain and anchor properties will be overridden
            defaultyaxis: {mirror: true, zeroline: false, linewidth: 1},  // domain and anchor properties will be overridden
            colorMap: Vue.colorMap(),  // defined in vueutil.js,
            freezewatchers: true  // does what it says: it freezes watchers. Used when initializing to avoid fire Vue's re-layout
        }
    },
    template: `<div v-show='initialized' class='flex-direction-row'>
        
        <div class='flexible flex-direction-col'>
            <div v-if="Object.keys(selectableParams).length" class='flex-direction-row justify-content-around mt-1 mb-1'>
                <div v-for='(values, key) in selectableParams' class='flex-direction-row flexible align-items-baseline'>
                    <span class='text-nowrap mr-1'>{{ key }}</span>
                    <select class='flexible form-control' v-model="selectedParams[key]">
                        <option v-for='value in params[key]'>
                            {{ value }}
                        </option>
                    </select>
                </div>
            </div>
            <div class='flexible position-relative'>
                <div class='position-absolute pos-0' :id="plotdivid"></div>
            </div>
        </div>
    
        <div class='flex-direction-col p-2 pl-3'
            v-if="Object.keys(legend).length || Object.keys(selectableParams).length || showGridControls">

            <slot :eventbus="eventbus" :url="url"></slot>
            
            <div v-if='Object.keys(legend).length' class='flexible mt-3 border-top'>
                <h5 class='mt-2 mb-2'>Legend</h5>
                <div v-for="(value, key) in legend">
                    <label v-bind:style="{color: value}">
                        <input type='checkbox' v-bind:checked="isTraceVisible(key)" v-on:click="toggleTraceVisibility(key)">
                        {{ key }}
                    </label>
                </div>
            </div>

            <div v-if="showGridControls" class='mt-3 border-top'>
                <h5 class='mt-2 mb-2'>Subplots layout</h5>

                <div>Group vertically by:</div>
                <select class='form-control' v-model='gridyparam'>
                    <option v-for='key in Object.keys(params)' v-bind:value="key">
                        {{ key }}
                    </option>
                </select>

                <div class='mt-1' >Group horizontally by:</div>
                <select class='form-control' v-model='gridxparam'>
                    <option v-for='key in Object.keys(params)' v-bind:value="key">
                       {{ key }}
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
        },
        defaultGridParams: function(params){
            // this optional method can be implemented to return an array [xKey, yKey] representing
            // the default param names of the grid along the x and y axis, respectively.
            // xKey and yKey should be keys of the params argument (js Object).
            // If not implemented, by default this method returns the first 2 values of `Object.keys(params)`
            var keys = Object.keys(params);
            return [keys[0], keys[1]];
        },
        displayGrid: function(paramName, axis){
            // this optional method can be implemented to hide particular grid labels IN THE PLOT along the
            // specified axis ('x' or 'y'). If not implemented, by default this method returns true
            return true;
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
        addLegend: function(trace, key, defaultColor){  //defaultColor is optional. If given, it is in the form '#XXXXXX'
            var color;
            var colorMap = this.colorMap;
            if (defaultColor !== undefined && !colorMap.has(key)){
                colorMap.set(key, defaultColor);
                color = defaultColor;
            }else{
                color = colorMap.get(key);  // sets also the key if not existing
            }
            this.legend[key] = color;
            trace.legendgroup = key;
            return color;
        },
        init: function(jsondict){
            this.$set(this, 'initialized', true);
            this.$set(this, 'freezewatchers', true);
            this.$set(this, 'legend', {});
            // convert data:
            var plots = this.getData(jsondict);
            this.$set(this, 'plots', plots);
            // this.$set(this, 'params', params);
            // update selection, taking into account previously selected stuff:
            this.setupSelection();
            this.relayout();
        },
        relayout: function(divId){ // In most cases call relayout(), i.e. with divId=undefined which will use the default div Id
            if (divId === undefined){
                divId = this.plotdivid;
            }
            var plotlyplots = this.getPlotsToDisplay();
            this.$nextTick(() => {this.displayPlots(divId, plotlyplots);});
        },
        getPlotsToDisplay: function(){
            var plots = this.plots;
            var [gridxparam, gridyparam] = [this.gridxparam, this.gridyparam];
            // filter plots (excluding values of param whose names are set for xgrid and ygrid):
            for (var key of Object.keys(this.params)){
                if (key != gridxparam && key != gridyparam){
                    var val = this.selectedParams[key];
                    plots = plots.filter(plot => plot.params[key] == val);
                }
            }
            return plots;
        },
        setupSelection: function(){
            // sets up selectable params, including those choosable as 'x grid' or 'y rid'.
            // called once from 'init'
            var plots = this.plots;
            var params = {};
            plots.forEach(plotElement => {
               var plotParams = plotElement.params;
               for (key of Object.keys(plotParams)){
                   if(!(key in params)){
                       params[key] = new Set();
                   }
                   params[key].add(plotParams[key]);
               }
            });
            // store param names:
            var paramNames = Object.keys(params);
            // selected params is basically params where each key will be mapped to their first value:
            var selectedParams = {};
            // replace sets with sorted Arrays (vuejs wants Arrays, not Sets), and remove proeprties that are 'empty'
            // (either empty array or have a single falsy element (empty string, null)):
            for(var key of paramNames){
                var val = Array.from(params[key]);
                if(!val.length || (val.length==1 && !val[0] && val[0]!==0)){
                    delete params[key];
                    continue;
                }
                // now sort values. Note that javascript array sort converts to string first (WTF!!!??), so
                // use a particular sort function for numbers only (see https://stackoverflow.com/a/1063027):
                if (typeof val[0] === 'number'){
                    val.sort((a, b) => a - b);
                }else{
                    val.sort();
                }
                params[key] = val;
                selectedParams[key] = val[0];
            }
            var [gridxparam, gridyparam] = this.defaultGridParams(params);
            // set defaults:
            this.$set(this, 'gridxparam', gridxparam);
            this.$set(this, 'gridyparam', gridyparam);
            this.$set(this, 'selectedParams', selectedParams);
            this.$set(this, 'params', params);
        },
        displayPlots: function(divId, plotlyplots){
            var layout = Object.assign({}, this.defaultlayout);
            this.configureLayout(layout);
            if (!('font' in layout)){
                layout.font = {};
            }
            // setup font as the body font, and size as set in the object properties, since the font size
            // is used to calculate spaces it cannot be changed in configureLayout:
            layout.font.family = window.getComputedStyle(document.getElementsByTagName('body')[0]).getPropertyValue('font-family');
            layout.font.size = this.plotfontsize;
            // copy layout annotations cause it's not a "primitive" type and thus we want to avoid old annotation to be re-rendered
            layout.annotations = layout.annotations ? Array.from(this.defaultlayout.annotations) : [];
            // Purge plot. Check if we do actually need this:
            Plotly.purge(divId);
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
            var xdomains = new Array(gridxvalues.length);  // used below to place correctly the x labels of the GRID
            var ydomains = new Array(gridyvalues.length);  // used below to place correctly the x labels of the GRID
            var annotation = this.getAnnotation;
            var legendgroups = new Set();
            for (var plot of plotlyplots){
                var gridxvalue = plot.params[gridxparam];
                var gridxindex = gridxindices.get(gridxvalue); // plot horizontal index on the grid 
                if(gridxindex === undefined){continue;}
                var gridyvalue = plot.params[gridyparam];
                var gridyindex = gridyindices.get(gridyvalue);  //plot vertical index on the grid
                if(gridyindex === undefined){continue;}
                var [axisIndex, xaxis, yaxis, xdomain, ydomain] = this.getAxis(divId, gridyindex, gridxindex, gridyvalues.length, gridxvalues.length);
                xdomains[gridxindex] = xaxis.domain;  // used below to place correctly the x labels of the GRID
                ydomains[gridyindex] = yaxis.domain;  // used below to place correctly the y labels of the GRID
                // merge plot xaxis defined in getData with this.defaultxaxis, and then with xaxis.
                // Priority in case of conflicts goes from right (xaxis) to left (this.defaultxaxis)
                layout[`xaxis${axisIndex}`] = xaxis = Object.assign({}, this.defaultxaxis, plot.xaxis, xaxis);
                // merge plot yaxis defined in getData with this.defaultyaxis, and then with yaxis.
                // Priority in case of conflicts goes from right (yaxis) to left (this.defaultyaxis)
                layout[`yaxis${axisIndex}`] = yaxis = Object.assign({}, this.defaultyaxis, plot.yaxis, yaxis);
                // Now edit the traces in plot.traces. Each trace is basically an Object of the
                // form T = {x: ..., y: ...}. These trace properties need to be modified EACH TIME:
                // 1. T.xaxis and T.yaxis (i.e., basically on which subplot the trace has to be displayed), and
                // 2. T.showlegend. The latter is set to true for the FIRST trace found for a given legendgroup
                // in order to avoid duplicated legend names. (T.legendgroup = T.name is the GSIM name, and it allows
                // toggling visibility simultaneously on all subplots for every trace with the same legendgroup, when 
                // clicking on the legend's GSIM name)
                plot.traces.forEach(function(element){
                    element.xaxis = `x${axisIndex}`;
                    element.yaxis = `y${axisIndex}`;
                    if ('legendgroup' in element){
                        element.showlegend = !legendgroups.has(element.legendgroup);
                        legendgroups.add(element.legendgroup);
                    }
                    data.push(element);
                });
                // wrtie x and y labels: we might simply set xaxis.title= 'my label' (same for y axis) but:
                // 1. plotly reserves too much space between the axis line and the axis label (the space is out of control)
                // 2. Plotly does some hard coded calculation and moves the labels, and we want control over it:
                // for instance when two ploits are stacked vertically,
                // the bottom one has the legend moved up to be included in the plot area)
                
                // So, get xaxis.title and yaxis.title (if any) and put them as annotations:
                if (xaxis.title){
                    layout.annotations.push(annotation({
                        x: (xaxis.domain[1]+xaxis.domain[0])/2,
                        y: ydomain[0],
                        xanchor: 'center',
                        yanchor: 'bottom',
                        text: xaxis.title
                    }));
                    // delete xaxis title otherwise plotly draws the label:
                    delete xaxis.title;
                }
                // and ylabel: (why this? can't I set the tile to the xaxis object?)
                if (yaxis.title){
                    layout.annotations.push(annotation({
                        x: xdomain[0],
                        y: (yaxis.domain[1]+yaxis.domain[0])/2,
                        xanchor: 'left',
                        yanchor: 'middle',
                        textangle: '-90',
                        text: yaxis.title
                    }));
                    // delete xaxis title otherwise plotly draws the label:
                    delete yaxis.title;
                }
          }
          // Grid X labels: (horizontally on top)
          if (this.displayGrid(gridxparam, 'x')){
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
          if (this.displayGrid(gridyparam, 'y')){
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
          this.$set(this, 'freezewatchers', false);
        },
        getLayout: function(){
            return {autosize: true, font: {family: "Encode Sans Condensed, sans-serif", size: this.plotfontsize},
                showlegend: true,
                margin: {r: 0, b: 0, t: 0, l:0, pad:0}, annotations: []};
        },
        getAxis: function(divId, row, col, rows, cols){
            // computes the sub-plot area according to the row and col index
            // returns the array [axisIndex, xaxis, yaxis, xdomain, ydomain]
            // where xaxis and yaxis are the Objects to be passed to plotly's layout, xdomain = [x1, x2] and
            // ydomain = [y1, y2] are the two-element arrays denoting the enclosing area of the sub-plot
            var [uwidth, uheight] = this.getEmUnits(divId, this.plotfontsize);
            var gridxparam = this.displayGrid(this.gridxparam, 'x') ? this.gridxparam : '';
            var gridyparam = this.displayGrid(this.gridyparam, 'y') ? this.gridyparam : '';
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
            var xaxis = {domain: xaxisdomain, anchor: `y${axisIndex}`};
            var yaxis = {domain: yaxisdomain, anchor: `x${axisIndex}`};
            //console.log('xdomain:' + xdomain); console.log('ydomain:' + ydomain);
            return [axisIndex, xaxis, yaxis, xdomain, ydomain];
        },
        getEmUnits: function(divId, fontsize){
            // returns [uwidth, uheight], the units of a 1em in percentage of the plot div, which must be shown on the browser
            // Both returned units should be < 1 in principle
            var fontsize = this.plotfontsize;
            var [width, height] = this.getPlotDivSize(divId);
            return [fontsize/width, fontsize/height];
        },
        getAnnotation(props){
            return Object.assign({
                xref: 'paper',
                yref: 'paper',
                showarrow: false,
                font: {size: this.plotfontsize}
          }, props || {});
        },
        getPlotDivSize: function(divId){
            var elm = document.getElementById(divId);
            return [elm.offsetWidth, elm.offsetHeight];
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
                if (visible === undefined){
                    // if undefined, visible was not defined on any plotly data Object => it's visible
                    visible = true;
                }
                Plotly.restyle(this.plotdivid, {visible: !visible}, indices);
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
        }
    },
    mounted: function() { // https://stackoverflow.com/questions/40714319/how-to-call-a-vue-js-function-on-page-load
        // no -op
    },
    watch: {
        selectedParams: {
            handler: function (newval, oldval) {
                if (!this.freezewatchers){  // prevent firing if we are modifying values while parsing input for rendering the plots
                    this.relayout();
                }
            },
            deep: true  // https://vuejs.org/v2/api/#vm-watch
        },
        gridxparam: function(newval, oldval){
            if (this.freezewatchers){  // prevent firing if we are modifying values while parsing input for rendering the plots
                return;
            }
            if (newval == this.gridyparam){  // swap selection:
                this.$set(this, 'gridyparam', oldval);
                return;
            }
            this.relayout();
        },
        gridyparam: function(newval, oldval){
            if (this.freezewatchers){  // prevent firing if we are modifying values while parsing input for rendering the plots
                return;
            }
            if (newval == this.gridxparam){  // swap selection:
                this.$set(this, 'gridxparam', oldval);
                return;
            }
            this.relayout();
        }
    },
    computed: {  // https://stackoverflow.com/a/47044150
        selectableParams: function(){
            var ret = {};
            for (var key of Object.keys(this.selectedParams)){
                if (key != this.gridxparam && key != this.gridyparam && this.params[key].length > 1){
                    ret[key] = this.params[key];
                }
            }
            return ret;
        },
        showGridControls: function(){
            // returns if grid controls to select the grid x and y should be visible. Basically, controls are shown if there
            // is somthing to be grouped along the x and y axis (plots.length > 1)
            return this.plots.length && this.plots.length > 1;
        }
    }
});