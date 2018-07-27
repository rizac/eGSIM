Vue.component('gmdbmagdistdiv', {
    props: {
        'url': String,
        'eventbus': {default: null}
    },
    data: function(){
        return {
            // NOTE: do not prefix data variable with underscore: https://vuejs.org/v2/api/#data
            initialized: false,
            data: [], //array of [{data, params}], where data is an array of dicts (one dict per trace) and params is a dict
            plotlydata: [],  // the `data` argument passed to Plotly.newPlot(data, ...) holding the traces
            plotlylayout: {},  // the `layout` argument passed to Plotly.newPlot(..., layout, ...) holding the layout stuff
            plotDivId: 'gmdbmagdiv-plot-container',
            plotFontSize: 12,
            colorMap: Vue.colorMap(),  // defined in vueutil.js
        }
    },
    template: `<div id='magdistdiv' v-show='initialized'>
        
        <div class='flexible position-relative'>
            <div class='position-absolute pos-0' :id="plotDivId"></div>
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
            this.$set(this, 'data', jsondict);
            // set plotly data from jsondict:
            var trace = {
                    x: jsondict['x'],
                    y: jsondict['y'],
                    mode: 'markers',
                    type: 'scatter',
                    text: jsondict['labels'] || [],
                    marker: { size: 10 }
                  };
            var data = [ trace ];
            var layout = {
                    title: `Magnitude Distance plot (${trace.x.length} records in database)`,
                    xaxis: {
                        type: 'log',
                        linecolor: 'gray',
                        zeroline: false,
                        linewidth: 1,
                        mirror: true,
                        title: jsondict['xlabel']
                    },
                    yaxis: {
                        linecolor: 'gray',
                        zeroline: false,
                        linewidth: 1,
                        mirror: true,
                        title: jsondict['ylabel']
                    },
                    //title:'Data Labels Hover'
                  };
            this.$set(this, 'plotlydata', data);
            this.$set(this, 'plotlylayout', layout);
            // call plot when everything has been rendered ($nextTick):
            this.$nextTick(this.displayPlots);
        },
        displayPlots: function(divId){  //divId optional, it defaults to this.plotDivId if missing
            var layout = this.getLayout();  // instantiate first cause we will change its showlegend value below:
            if(divId === undefined){
                divId = this.plotDivId;
                layout.showlegend = false;
            }
            layout = Object.assign(layout, this.plotlylayout);
            Plotly.purge(divId);  // do we need this?
            Plotly.newPlot(divId, this.plotlydata, layout);
        },
        getLayout: function(){
            return {autosize: true, font: {family: "Encode Sans Condensed, sans-serif", size: this.plotFontSize},
                showlegend: true,
                margin: {r: 10, b: 120, t: 50, l: 50, pad:0}, annotations: []};
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
        
    },
    computed: {  // https://stackoverflow.com/a/47044150
        
    }
});