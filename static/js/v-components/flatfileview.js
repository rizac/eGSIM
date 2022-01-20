/**
 * Registers globally a Vue component. The name of the component
 * (first argument of 'Vue.component' below must be equal to this file's name 
 * (without extension)
 */
Vue.component('flatfileview', {
    //https://vuejs.org/v2/guide/components-props.html#Prop-Types:
    props: {
        form: Object,
        url: String,
        response: {type: Object, default: () => {return {}}}
    },
    data: function () {
        return {
            responseData: this.response,
        }
    },
    watch: {  // no-op
    },
    methods: {
        submit: function(){
            var form = this.form;
            const formData = new FormData();

            formData.append('file', file)
            const config = {
                headers: {
                    'content-type': 'multipart/form-data'
                }
            }
            return  post(url, formData,config)

            EGSIM.post(this.url, formData, config).then(response => {  // defined in `vueutil.js`
                if (response && response.data){
                    this.responseData = response.data;
                } 
            });
        }
    },
    template: `<div class='flexible d-flex flex-column'>
        <div class='mb-3'>
            <egsim-form novalidate @submit.prevent="submit" class='d-flex flex-column' method='post'
                  enctype="multipart/form-data">
                <div class="d-flex flex-row flexible align-items-end">

                    <flatfile-select :field="form.flatfile" :selexpr-field='form.selexpr'
                                     class='d-flex flex-row align-items-baseline'>
                    </flatfile-select>
                    <field-input :field='form.x' class='ml-3'></field-input>
                    <field-input :field='form.y' class='ml-3'></field-input>

                    <button type="submit" class="ml-3 btn btn-primary mt-2">
                        Display plot
                    </button>

                </div>
            </egsim-form>
        </div>
        <flatfile-plot-div :data="responseData" class='flexible'></flatfile-plot-div>
    </div>`
});


Vue.component('flatfile-plot-div', {
    mixins: [PLOT_DIV],
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
            /* Return true / false to specify if the given parameter should be displayed
            as grid parameter along the specified axis. In the default implementation
            (see plot-div.js), return true if `paramValues.length > 1`.
            Function arguments:
                `axis`: string, either 'x' or 'y'
                `paramName`: the string denoting the parameter name along the given axis
                `paramValues`: Array of the values of the parameter keyed by 'paramName'
            */
            return true;  // we have  single param (sort of title on the x axis), alswya show
        },
        /**configureLayout is the same as the super class 'plot-div' and thus not overwritten.**/
        // END OF OVERRIDABLE METHODS
    }
});


Vue.component('flatfile-select', {
    props: {
        field: {type: Object},
        selexprField: {type: Object}
    },
    data(){
        // fieldProxy is a bridge between user input and final value: it has global 'choices'
        // (<option>s) so that all <flatfile-select> are updated after a flatfile upload,
        // and the flatfile field value will then be built from the input value and the
        // uploaded flatfiles as as either a string or a File object (see `watch`)
        var fieldProxy = Object.assign({}, this.field);
        return {
            flatfiles: this.field.choices,
            fieldProxy: fieldProxy,
            columns: this.field['data-columns']
        }
    },
    watch: { // https://siongui.github.io/2017/02/03/vuejs-input-change-event/
        'fieldProxy.value': function(newVal, oldVal){
            // Set the field values as either a string (predefined flatfile) or a File
            // Object
            for (var ff of this.flatfiles){
                if (ff.name == newVal){
                    if (ff.file){
                        newVal = file;
                    }
                    break
                }
            }
            this.field.value = newVal;
        },
        'field.error': function(newVal, oldVal){
            this.fieldProxy.error = newVal;
        },
        'field.disabled': function(newVal, oldVal){
            this.fieldProxy.disabled = newVal;
        },
        flatfiles: {
            deep: true,
            immediate: true,
            handler: function(newVal, oldVal){
                this.fieldProxy.choices = Array.from(newVal.map(elm => [elm.name, elm.label]));
            }
        }
    },
    computed: {
        flatfileURL(){
            var val = this.fieldProxy.value;
            for (var ff of this.flatfiles){
                if (ff.name == val){
                    return ff.url;
                }
            }
            return undefined;
        }
    },
    methods:{
        filesUploaded: function(files){
            var flatfiles = this.flatfiles;
            this.fieldProxy.error="";
            for (var file of files){
                for (var i=0; i<flatfiles.length; i++){
                    var flatfile = flatfiles[i];
                    if (flatfile.name == file.name){
                        if (!flatfile.file){
                            // predefined flatfile with the same name as uploaded one:
                            this.fieldProxy.error='Please rename "${file.name}" before uploading (name conflict)';
                            return;
                        }
                        flatfile.file = file;
                        file = null;
                        break;
                    }
                }
                if (file != null){
                    flatfiles.push({
                        name: file.name, label: `${file.name} (uploaded)`, file: file
                    });
                }
            }
        }
    },
    template:`<div>
        <div class='d-flex flex-row align-items-end'>
            <field-input :field="fieldProxy"></field-input>
            <a target="_blank" class='ml-1' v-show="!!flatfileURL" :href="flatfileURL">Ref.</a>
            <button type="button" class="btn btn-primary ml-1" onclick="this.nextElementSibling.click()"
                    aria-label="Upload a user defined flatfile. Please click on help for details"
                    data-balloon-pos="down" data-balloon-length="small">
                upload
            </button>
            <input type="file" class='ml-1' v-show="false" @change="filesUploaded($event.target.files)"/>
            <button class='btn ml-1 btn-outline-dark border-0' type="button"
                    onclick="this.nextElementSibling.firstElementChild.style.display=''">
                <i class="fa fa-question-circle"></i>
            </button>
            <div style="position:relative">
                <div style="position:absolute;left:-3rem;width:33vw;max-height:50vh;top:0.1rem;display:none;overflow:auto;z-index:10;"
                     class='form-control shadow'>
                    <i class="fa fa-times-circle ml-2" style='font-size:125%;float:right;cursor:pointer' title='close'
                       onclick="this.parentNode.style.display='none'"></i>
                    <div>
                       To upload a user-defined flatfile, provide a plain-text or zipped CSV file
                       where each row denotes an observed record and each column a record attribute.
                       The number of flatfile columns required depends on the ground shaking intensity
                       models used for comparison, because different models require different
                       attributes. Non-required flatfile columns will be ignored but can be used for
                       filtering records (see selection expression). However,
                       <b>please try to implement the minimum
                       required amount of columns to improve memory consumption and upload time</b>.
                       <br><br>
                       Flatfile possible columns inferred by all models required attributes:
                       <ul>
                           <li>event_id: event identifier (string or numeric): two event id are equal if and only if they refer to the same seismic event. Several rows can - and usually should - share the same event id</li>
                           <li v-for="colelm in columns"> {{ colelm[0] }}: {{ colelm[1] }}</li>
                       </ul>
                    </div>
                </div>
            </div>
        </div>
        <div class='d-flex flex-row align-items-end'>
            <field-input :field='selexprField' class='ml-3'></field-input>
            <button class='btn ml-1 btn-outline-dark border-0' type="button"
                    onclick="this.nextElementSibling.firstElementChild.style.display=''">
                <i class="fa fa-question-circle"></i>
            </button>
            <div style="position:relative">
                <div style="position:absolute;left:-3rem;width:33vw;max-height:50vh;top:0.1rem;display:none;overflow:auto;z-index:10;"
                     class='form-control shadow'>
                    <i class="fa fa-times-circle" style='font-size:125%;float:right;cursor:pointer' title='close'
                       onclick="this.parentNode.style.display='none'"></i>
                    Filter matching rows typing an expression that operates on arbitrary
                    flatfile columns, e.g.:
                    <pre><code>magnitude>5</code></pre>
                    Valid comparison operators are <b>== != &gt; &lt; &gt;= &lt;=</b>
                    <br>Logical operators are <b>&</b> (and) <b>|</b> (or) <b>!</b> (not), e.g.:
                    <pre><code>(magnitude >= 5) & (vs30 > 760)</code></pre>
                    Use <b>notna([column])</b> to match rows where the column value is
                    given, i.e. not "not available" (na). For instance:
                    <pre><code>(magnitude>5) & (notna(rjb) | notna(repi))</code></pre>
                </div>
            </div>
        </div>
    </div>`
});