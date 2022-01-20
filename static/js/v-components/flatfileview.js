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
    template: `<div class='d-flex flex-column' style='flex: 1 1 auto'>
        <div class='mb-3'>
            <base-form class='d-flex flex-row align-items-end'>
                <slot>
                    <div class="d-flex flex-row align-items-end mr-3" style='flex: 1 1 auto'>
                        <flatfile-select :field="form.flatfile"></flatfile-select>
                        <flatfile-selexpr-input :field="form.selexpr" class='ml-3' style='flex:1 1 auto'></flatfile-selexpr-input>
                        <field-input :field='form.x' class='ml-3'></field-input>
                        <field-input :field='form.y' class='ml-3'></field-input>
                    </div>
                </slot>
            </base-form>
        </div>
        <flatfile-plot-div :data="responseData" style='flex: 1 1 auto'></flatfile-plot-div>
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
            for (var file of files){
                for (var i=0; i<flatfiles.length; i++){
                    var flatfile = flatfiles[i];
                    if ((flatfile.name == file.name) && (flatfile.file)){
                        // `flatfile.file` assures we are modifying an user uploaded flatfile
                        flatfile.file = file;
                        file = null;
                        break;
                    }
                }
                if (file != null){
                    flatfiles.push({
                        name: file.name, label: `${file.name} (uploaded: ${new Date().toLocaleString()})`, file: file
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
                    onclick="this.parentNode.nextElementSibling.firstElementChild.style.display=''">
                <i class="fa fa-question-circle"></i>
            </button>
        </div>
        <div style="position:relative">
            <div style="position:absolute;left:0;right:0;max-height:45vh;top:0.1rem;display:none;overflow:auto;z-index:10;font-family:sans-serif"
                 class='form-control shadow'>
                <i class="fa fa-times-circle ml-2" style='font-size:110%;float:right;cursor:pointer' title='close'
                   onclick="this.parentNode.style.display='none'"></i>
                <div>
                   <p>
                   To upload a user-defined flatfile, please upload it as uncompressed or zipped CSV file.
                   Each CSV row must denotes an observed record and each column a record attribute.
                   The file must have at least one column denoting an observed Intensity measure
                   to compare (PGA, PGV or SA typed with their period in parentheses, e.g. "Sa(0.1), Sa(0.2)"),
                   and the columns of the parameters required by the ground shaking intensity models
                   that are meant to be used, e.g., magnitude, vs30 (scroll down for a complete list).
                   Any flatfile column non required by any model will be ignored but can be used for
                   filtering records (see selection expression). However,
                   <b>please try to provide the strict minimum of columns in order to improve
                   memory consumption and upload time</b>.
                   </p>
                   <table class="table table-sm">
                       <tr>
                           <th>Flatfile column</th><th>Description</th><th>Data type</th></tr>
                       <tr>
                           <td>event_id</td>
                           <td>a <b>mandatory</b> record event id: <i>two event id must be
                               equal if and only if they refer to the same seismic event</i>. Several
                               rows can - and usually should - share the same event id. Many
                               event web services provide their own ID which serves the purpose
                               effortless
                           </td>
                           <td>str or int</td>
                       </tr>
                       <tr v-for="cname in Object.keys(columns)">
                            <td>{{ cname }} </td><td> {{ columns[cname][1] }} </td><td> {{ columns[cname][0] }}</td>
                       </tr>
                   </table>
                </div>
            </div>
        </div>
    </div>`
});


Vue.component('flatfile-selexpr-input', {
    props: {
        field: {type: Object}
    },
    template:`<div>
        <div class='d-flex flex-row align-items-end'>
            <field-input :field='field' style='flex:1 1 auto'></field-input>
            <button class='btn ml-1 btn-outline-dark border-0' type="button"
                    onclick="this.parentNode.nextElementSibling.firstElementChild.style.display=''">
                <i class="fa fa-question-circle"></i>
            </button>
        </div>
        <div style="position:relative">
            <div style="position:absolute;left:0;right:0;max-height:45vh;top:0.1rem;display:none;overflow:auto;z-index:10;font-family:sans-serif"
                 class='form-control shadow'>
                <i class="fa fa-times-circle" style='font-size:110%;float:right;cursor:pointer' title='close'
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
    </div>`
});
