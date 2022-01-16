/**
 * Registers globally the trellis component (model-to-model comparison).
 * The component name must be a name of a `TAB` Enum in egsim.gui.__init__.py
 */
Vue.component('trellis', {
    extends: _BASE_FORM,  // defined in base-form.js
    data: function () {
        return {
            predefinedSA: false,  // whether we have selected spectra as plot type
            responseData: {},
            formHidden: false,
            scenarioKeys: Object.keys(this.form).filter(key => key!='gsim' && key!='imt' && key!='plot_type' && key!='stdev')
        }
    },
    computed: {
        scenarioHasErrors: function(){
            var form = this.form;
            return this.scenarioKeys.some(key => !!form[key].err);
        }
    },
    watch: {
        'form.plot_type.value': {
            // watch the selected plot type and enable/disable the imt <select> accordingly
            immediate: true,
            handler: function(newVal, oldVal){
                var enabled = newVal !== 's' && newVal !== 'ss';
                this.form.imt.disabled = !enabled;
                this.predefinedSA = !enabled;
            }
        }
    },
    template: `
<div class='d-flex flex-column position-relative' style="flex: 1 1 auto">
    <!-- v-bind="$props" passes all of the props on to the "parent" component -->
    <!-- https://stackoverflow.com/a/40485023 -->
    <base-form v-show="!formHidden" v-bind="$props"
              @responsereceived="responseData = arguments[0]; formHidden = true"
              @closebuttonclicked="formHidden = true">

        <template v-slot:left-column>
            <gsim-select :field="form['gsim']" :imtField="form['imt']" style="flex:1 1 auto"/>
        </template>

        <template v-slot:right-column>
            <div style="position:relative">
                <imt-select :field="form['imt']"></imt-select>
                <div v-show='predefinedSA' class="form-control small text-muted"
                     style="position:absolute;bottom:1rem;right:1rem;width:13rem;text-align:justify">
                    <i class='text-warning fa fa-info-circle'></i>
                    Intensity Measure will default to 'SA' with a set of pre-defined periods
                </div>
            </div>
            <div class="form-control mt-4"
                 :class="{'border-danger': scenarioHasErrors}"
                 style="flex: 1 1 0;background-color:transparent;overflow-y:auto">

                <field-input v-for="(name, index) in scenarioKeys" :key="name"
                             :field='form[name]' :class="{ 'mt-2': index > 0 }">
                </field-input>
            </div>

            <div class="mt-4" style="background-color:transparent">
                <field-input :field='form["plot_type"]' size="3"></field-input>
                <field-input :field='form["stdev"]' class='mt-1'></field-input>
            </div>
        </template>
    </base-form>

    <trellis-plot-div :data="responseData"
                      :download-url="urls.downloadResponse"
                      class='position-absolute pos-0' style='z-index:1'>
        <slot>
            <button @click='formHidden=false' class='btn btn-sm btn-primary'>
                <i class='fa fa-list-alt'></i> Configuration
            </button>
        </slot>
    </trellis-plot-div>
</div>`
});


Vue.component('trellis-plot-div', {
    extends: _PLOT_DIV,  // defined in plot-div.js
    methods: {
        // methods to be overridden:
        getData: function(responseObject){
            /* Return from the given response object an Array of Objects representing
            the sub-plot to be visualized. Each sub-plot Object has the form:
            {traces: Array, params: Object, xaxis: Object, yaxis: Object}
            where:

            `traces`: Array of valid representable Trace Objects e.g.:
                {x: Array, y: Array, name: string}.
                A list of keys of each Object is available at https://plot.ly/javascript/reference/
                Consider that some layout-related keys will be set automatically
                and overwritten if present: `xaxis` (string), 'yaxis' (string),
                'showlegend' (boolean). See plot-div.js
                NOTE1: Providing a `name` key to a Trace Object makes the name showing
                when hovering over the plot trace with the mouse.
                NOTE2: To add a unique color mapped to a trace id (e.g. the trace name),
                setup the legendgroup and automatically map the trace to a legend item
                toggling the trace visibility, use `this.addLegend(trace, key)`, e.g.:
                var trace = {x: Array, y: Array, name: 'mytrace'}
                var color = this.addLegend(trace, trace.name)
                trace.line = {color: color}  // set the trace color as the legend color
               `addLegend(trace, key)` assign an automatic color to the given key such as
                subsequent calls to addLegend(..., key) return the same color. To specify
                an explicit color color for non yet mapped key, call:
                addLegend(trace, key, color)` where color is a string in the HEX-form
                '#XXXXXX'. See `colorMap` in `plotDoc` for details.

            `params`: Object identifying the plot properties (Object keys) and their
                value, e.g. {magnitude: 5, xlabel: 'PGA}. The Object keys can then be
                used in the GUI in order to select or layout plots on a grid, grouping
                plots according to the selected keys values. Consequently, all `params`
                Objects of all returned sub-plots must have the same keys. If `params` is
                always composed of the same single key and the same value, then in this
                case it's used to display the main plot title as "<key>: <value>".

            `xaxis`: Object of x axis properties, e.g.: {title: 'A title', type: 'log'}.
                The final Axis properties will be built by merging `this.defaultxaxis`
                and the values provided here. For a list of possible keys, see:
                https://plot.ly/javascript/reference/#layout-xaxis, but consider that
                some layout-related keys will be set automatically and overwritten if
                present: `domain` and `anchor`.

            `yaxis` is a dict of y axis properties. See 'xaxis' above for details.
            */
            var ln10 = Math.log(10);
            var mathlog = Math.log;
            function log10(val) {  // https://stackoverflow.com/a/3019290
                return mathlog(val) / ln10;
            }
            var mathpow = Math.pow;
            var pow10 = elm => mathpow(10, elm);

            // get the current colorMap (will be used to set transparency on stdev
            // areas, if given):
            var colorMap = this.colorMap;  // defined in plot-div.js
            var data = responseObject;
            var plots = [];
            // setup  label texts:
            for (var imt of data.imts){
                var figures = data[imt];
                for (var fig of figures){
                    var params = {};
                    params.imt = imt;
                    params.magnitude = fig.magnitude;
                    params.distance = fig.distance;
                    params.vs30 = fig.vs30;
                    var traces = [];
                    Object.keys(fig.yvalues).map(function(name){
                        // FIXME: check if with arrow function we can avoid apply and this
                        // to test that plots are correctly placed, uncomment this:
                        // var name = `${name}_${params.magnitude}_${params.distance}_${params.vs30}`;
                        var yvalues = fig.yvalues[name];
                        var trace = {
                                x: data.xvalues,
                                // <extra></extra> hides the second tooltip (white):
                                hovertemplate: `${name}<br>${data.xlabel}=%{x}<br>` +
                                    `${fig.ylabel}=%{y}<extra></extra>`,
                                y: yvalues,
                                type: 'scatter',
                                mode: (data.xvalues.length == 1 ? 'markers' : 'lines'),
                                name: name
                        };
                        var color = this.addLegend(trace, name);  // Sets also trace.legendgroup = name
                        if (data.xvalues.length == 1){
                            trace.marker = {color: color};
                        }else{
                            trace.line = {color: color, width: 3};
                        }

                        var _traces = [trace];
                        // add stdev if present:
                        var stdev = (fig.stdvalues || {})[name];
                        if (stdev && stdev.length){
                            //copy the trace Object (shallow except the 'y' property, copied deeply):
                            var _traces = [
                                trace,
                                Object.assign({}, trace, {y:  yvalues.slice()}),
                                Object.assign({}, trace, {y:  yvalues.slice()})
                            ];
                            // put new values:
                            stdev.forEach((std, index) => {
                                if (std === null || _traces[1].y[index] === null){
                                    _traces[1].y[index] = null;
                                    _traces[2].y[index] = null;
                                }else{
                                    _traces[1].y[index] = pow10(log10(_traces[1].y[index]) + std);
                                    _traces[2].y[index] = pow10(log10(_traces[2].y[index]) - std);
                                }
                            });
                            // Values are now ok, now arrange visual stuff:
                            var colorT = colorMap.transparentize(color, 0.2);
                            for (var i of [2]){
                                _traces[i].fill = 'tonexty'; // which actually fills to PREVIOUS TRACE!
                            }
                            for (var i of [1, 2]){
                                _traces[i].line = {width: 0, color: color};  // the color here will be used in the label on hover
                                _traces[i].fillcolor = colorT;
                                var info = i==1 ? `value computed as 10<sup>log(${imt})+σ</sup>` : `value computed as 10<sup>log(${imt})-σ</sup>`;
                                _traces[i].hovertemplate = `${name}<br>${data.xlabel}=%{x}<br>${fig.ylabel}=%{y}` +
                                    `<br><i>(${info})</i><extra></extra>`;
                            }
                        }

                        // put traces into array:
                        for (var t of _traces){
                            traces.push(t);
                        }

                    }, this);
                    plots.push({
                        traces: traces,
                        params: params,
                        xaxis: {
                            title: data.xlabel
                        },
                        yaxis: {
                            title: fig.ylabel, type: 'log'
                        }
                    });
                }
            }
            return plots;
        },
        displayGridLabels: function(axis, paramName, paramValues){
            /* Return true / false to specify if the given parameter should be displayed
            as grid parameter along the specified axis. In the default implementation
            (see plot-div.js), return true if `paramValues.length > 1`.
            Function arguments:
                `axis`: string, either 'x' or 'y'
                `paramName`: the string denoting the parameter name along the given axis
                `paramValues`: Array of the values of the parameter keyed by 'paramName'
            */
            return paramValues.length > 1 && paramName != 'imt';
        },
        /** method `configureLayout` is not overwritten (see 'plot-div' for details) **/
        // END OF OVERRIDABLE METHODS
    }
});