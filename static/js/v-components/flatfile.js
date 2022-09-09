/* Flatfile components */

Vue.component('flatfile', {
    //https://vuejs.org/v2/guide/components-props.html#Prop-Types:
    props: {
        forms: Array,
        urls: Array
        // response: {type: Object, default: () => {return {}}}
    },
    data: function () {
        var compNames = ['flatfile-compilation', 'flatfile-plot'];  //, 'flatfile-inspection', 'flatfile-plot'];
        var compProps = {};
        compNames.forEach((elm, index) => {
            compProps[elm] = {
                form: this.forms[index],
                url: this.urls[index]
            };
        }, this);
        var compLabels = {
            'flatfile-compilation': 'Compilation',
            'flatfile-plot': 'Inspection plot'
        };
        return {
            componentNames: compNames,
            componentLabels: compLabels,
            componentProps: compProps,
            selComponentName: compNames[0],
        }
    },
    computed: {
    },
   template: `
    <div class='d-flex flex-column' style='flex: 1 1 auto'>
        <ul class="nav nav-tabs">
            <li class="nav-item" v-for="compName in componentNames">
                <a class="nav-link" :class="selComponentName==compName ? 'active' : ''"
                   @click='selComponentName=compName'
                   :aria-current="compName" href="#">{{ componentLabels[compName] }}</a>
            </li>
        </ul>

        <transition name="fade" mode="out-in">
        <keep-alive>
            <!-- https://vuejs.org/v2/guide/components-dynamic-async.html#keep-alive-with-Dynamic-Components -->
            <component v-bind:is="selComponentName" v-bind="componentProps[selComponentName]"></component>
        </keep-alive>
        </transition>
    </div>`
});


Vue.component('flatfile-compilation', {
    mixins: [BASE_FORM],
    //https://vuejs.org/v2/guide/components-props.html#Prop-Types:
    props: {
        form: Object,
        url: String,
        response: {type: Object, default: () => {return {}}}
    },
    data: function () {
        this.form.gsim.value = this.form.gsim.choices.map(elm => elm.value);
        return {
            responseData: this.response,
            imts: {
                value: ['SA(0.1)', 'SA(0.2)', 'SA(0.3)', 'SA(0.5)',  'SA(1.0)', 'PGA', 'PGV'],
                error: '',
                choices: ['SA', 'PGA', 'PGV'],
                label: 'Intensity Measure Type(s)'
            },
            columnsCustomizerVisible: false,
            csvSep: ',',
            flatfileContent: '',
            flatfileHeader: []
        }
    },
    watch: {
        responseData: function(newVal, oldVal){
            this.updateFlatfile();
        },
        'imts.value':  function(newVal, oldVal){
            this.updateFlatfile();
        },
        csvSep: function(newVal, oldVal){
            this.updateFlatfile();
        },
    },
    template: `<form novalidate class='d-flex flex-column' style='flex: 1 1 auto'>
        <div class='d-flex flex-row' style='flex: 1 1 auto; justify-content: center'>
            <div class='d-flex flex-column' style='max-width: 50rem'>

                <p class='text-justify'>
                Flatfiles are parametric tables required in Model-to-data comparison and testing,
                and must be uploaded as uncompressed or zipped
                <a target="_blank" href="https://en.wikipedia.org/wiki/Comma-separated_values">CSV files</a>,
                with each row representing a manually processed waveform, and the waveform metadata and intensity measures
                arranged in columns.

                To help the compilation of your flatfile, from scratch or existing sources,
                here you can create a template with the smallest set of columns <b>required</b> by
                the models and intensity measures that you want to analyze (see "Selection").

                <div class='d-flex flex-row align-items-baseline'>
                    <div v-show="!columnsCustomizerVisible">
                        <b>Flatfile template</b> ({{ flatfileHeader.length }} columns)
                    </div>
                    <div style='flex: 1 1 auto'></div>
                    <div class='ml-3' v-show="!columnsCustomizerVisible">CSV separator</div>
                    <input v-show="!columnsCustomizerVisible" type="text" v-model="csvSep" class='ml-1' style='max-width:2rem'>
                    <div v-show="!columnsCustomizerVisible" class='ml-3'>Selection</div>
                    <button type='button' @click='columnsCustomizerVisible=!columnsCustomizerVisible' class='ml-1 btn btn-primary'>
                        {{ columnsCustomizerVisible ? 'Show Flatfile' :
                           form.gsim.value.length + ' model' + (form.gsim.value.length == 1 ? ', ': 's, ') +
                           imts.value.length + ' intensity measure' + (imts.value.length.length == 1 ? '': 's')
                        }}
                    </button>
                </div>

                <textarea v-show="!columnsCustomizerVisible"
                          v-model='flatfileContent' class='mt-3'
                          style='flex:1 1 auto; white-space: pre; font-family:monospace; background-color:darkslategray; color:#e1e1e1'>
                </textarea>

                <div class='d-flex flex-row my-2' v-show='columnsCustomizerVisible'  style='flex:1 1 auto;'>
                    <gsim-select :field='form.gsim' @gsim-selected='gsimSelected'></gsim-select>
                    <div class='mr-3'></div>
                    <div class='d-flex flex-column'>
                        <imt-select :field='imts' style='flex: 1 1 auto'></imt-select>
                    </div>
                </div>

                <div class='mt-2 text-muted'>
                Hint: For performance reasons <b>try to keep uploaded flatfiles size within few tens of Megabytes</b>
                </div>

            </div>
        </div>
    </form>`,
    methods: {
        gsimSelected(){
            // query the server and store in response data the metadata columns
            // required for the current GSIM selection
            this.$nextTick(() => {
                this.submit().then(response => {
                    this.responseData = response.data;
                });
            });
        },
        updateFlatfile(){
            var metadataColumns = this.getMetadataColumns();
            var imtColumns = this.getImtColumns();
            var columns = metadataColumns.concat(imtColumns);
            // calculate depths (characters length of each column):
            var helpHeaders = ['Column:', 'Type:', 'Data type:', 'Description:'];
            var depths = helpHeaders.map(elm => elm.length);
            var header = [];
            var max = Math.max;
            for (var val of columns){
                header.push(val[0]);
                depths = val.map((elm, index) => max(elm.length, depths[index]));
            }
            this.flatfileHeader = header;
            var flatfileContent = [
                header.join(this.csvSep), '',
                '# This block comment is not part of the CSV but contains column information to help the compilation:',
            ];
            for (var val of [helpHeaders].concat(columns)){
                var row = val.map((elm, index) => elm + " ".repeat(depths[index] - elm.length)).join(" | ");
                flatfileContent.push(`# ${row}`);
            }
            var numGsim = this.form.gsim.value.length;
            var listGsim = this.form.gsim.value.join(' ');
            flatfileContent.push(`# The metadata columns above are required in eGSIM by ${numGsim} selected model(s):  ${listGsim}`);
            flatfileContent.push('');
            this.flatfileContent = flatfileContent.join("\n");
        },
        getMetadataColumns(){  // -> Array[Array[str, str, str, str]]
            // return a list of metadata columns from the response data
            var data = this.responseData;
            // the columns are objects that are empty if the column is not needed in the flatfile:
            var namesOk = Object.keys(data).filter(name => !!Object.keys(data[name]).length);
            var namesNo = Object.keys(data).filter(name => !Object.keys(data[name]).length);
            var ret = [];
            for (var name of namesOk.sort()){
                var [dtype, help] = [data[name].dtype, data[name].help];
                if (Array.isArray(dtype)){
                    help += `. Specify a value from: ${dtype.join(", ")}`;
                    dtype = "categorical";
                }
                ret.push([name, "Metadata", dtype, help]);
            }
            return ret;
        },
        getImtColumns(){  // -> Array[Array[str, str, str, str]]
            var desc = (imt) => {
                if (imt.startsWith('SA')){
                    return 'Spectral Acceleration, in g (computed at the given period, in s)'
                }else if (imt == 'PGA'){
                    return 'Peak Ground Acceleration, in cm/s*s'
                }else if (imt == 'PGV'){
                    return 'Peak Ground Velocity, in cm/s'
                }
                return '';
            }
            return this.imts.value.map(elm => [elm, 'Intensity measure', 'float', desc(elm)]);
        }
    }
});


Vue.component('flatfile-plot', {
    mixins: [BASE_FORM],  // will have props Form, url, and all methods for issuing post requests
    props: {
        form: Object,
        url: String,
        response: {type: Object, default: () => {return {}}}
    },
    data() {
        return {
            responseData: this.response,
        }
    },
    watch: {
//        no-op
    },
    methods: {
        request(){
            var form = this.form;
            Vue.post(this.url, form).then(response => {  // defined in `vueutil.js`
                if (response && response.data){
                    this.responseData = response.data;
                }
            });
        },
        flatfileSelected(file){
            var vals = Object.keys(file.columns).map(col => [col, `${col} ${file.columns[col]}`]);
            this.form.x.choices = this.form.x.choices.slice(0, 1).concat(vals);
            this.form.y.choices = this.form.y.choices.slice(0, 1).concat(vals);
        },
        submitMe(){
            this.submit().then(response => {this.responseData = response.data});
        }
    },
    template: `<div class='d-flex flex-column' style='flex: 1 1 auto'>
        <div class='mb-3'>
           <form novalidate @submit.prevent="submitMe">
                <div class="d-flex flex-row align-items-end" style='flex: 1 1 auto'>
                    <flatfile-select :field="form.flatfile" @flatfile-selected="flatfileSelected" />
                    <span class='mr-3'></span>
                    <flatfile-selexpr-input :field="form.selexpr" class='mt-3'/>
                    <span class='mr-3'></span>
                    <field-input :field='form.x'/>
                    <span class='mr-3'></span>
                    <field-input :field='form.y'/>
                    <span class='mr-3'></span>
                    <button type="submit" class="btn btn-primary mt-2">
                        Display plot
                    </button>
                </div>
           </form>
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
            if (jsondict.xlabel && jsondict.ylabel){
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
            }else if(jsondict.xlabel){
                var trace = {
                    x: jsondict.xvalues,
                    type: 'histogram',
                  };
            }else{
                var trace = {
                    y: jsondict.yvalues,
                    type: 'histogram',
                  };
            }

            // modify here the defaut layout:
            // this.defaultlayout.title = `Magnitude Distance plot (${trace.x.length} records in database)`;
            var data = [ trace ];
            var xaxis = {
                // type: 'log',
                title: jsondict.xlabel || 'Count'
            };
            var yaxis = {
                title: jsondict.ylabel || 'Count'
            };
            // build the params. Setting just a single param allows us to
            // display a sort of title on the x axis:
//            var numFormatted = trace.x.length.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ","); //https://stackoverflow.com/a/2901298
//            var title = `${numFormatted} records`;
//            if (jsondict.nan_count){
//                title += ' (' + jsondict.nan_count + ' NaN records not shown)';
//            }
            var params = {};  // {'Magnitude Distance plot': title};
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
        }
        /**configureLayout is the same as the super class 'plot-div' and thus not overwritten.**/
        // END OF OVERRIDABLE METHODS
    }
});


Vue.component('flatfile-select', {
    props: {
        field: {type: Object},
        doc: {
            type: String,
            default: `Upload a user-defined flatfile (CSV or zipped CSV).
                      Please consult also the tab "Flatfiles" to inspect your flatfile before usage.
                      An uploaded flatfile will be available in all tabs of this web page`
        }
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
    emits: ['flatfile-selected'],
    watch: { // https://siongui.github.io/2017/02/03/vuejs-input-change-event/
        'fieldProxy.value': function(newVal, oldVal){
            // called when we select a flatfile. newVal and oldVal are the indices
            // of the flatfiles. But the field expects either a string (flatfile name)
            // or a File Object (see BASE_FORM). So:
            var selFile = this.flatfiles[parseInt(newVal)] || null;
            // if (selFile == null){ return; }
            this.field.value = selFile.file || selFile.name;
            this.$emit('flatfile-selected', selFile);
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
                this.fieldProxy.choices = Array.from(newVal.map((elm, idx) => [idx, elm.label]));
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
        filesUploaded(files){
            var flatfiles = this.flatfiles;
            var newflatfiles = [];
            for (let file of files){
                var label = `${file.name} (Uploaded: ${new Date().toLocaleString()})`;
                var append = true;
                for (let flatfile of flatfiles){
                    if (!flatfile.file){  // pre-defined flatfile
                        continue;
                    }
                    if (flatfile.name == file.name){
                        this.upload(file).then(response => {
                            flatfile.file = file;
                            flatfile.label = label;  // update label on <select>
                            flatfile.columns = response.data.columns;
                        });
                        append = false;
                        break;
                    }
                }
                if (append){
                    this.upload(file).then(response => {
                        var cols = response.data.columns;
                        flatfiles.push({ name: file.name, label: label, file: file, columns: cols });
                    });
                }
            }
        },
        upload(file){  // return a Promise
            var formData = new FormData();
            formData.append("flatfile", file);
            return EGSIM.post(this.field.url, formData, {
                headers: {
                  'Content-Type': 'multipart/form-data'
                }
            });
        }
    },
    template:`<div class='d-flex flex-column'>
        <field-label :field="fieldProxy"/>
        <div class='d-flex flex-row align-items-baseline'>
            <field-input :field="fieldProxy"/>
            <div class='d-flex flex-row align-items-baseline'>
                <a title='flatfile reference (opens in new tab)' target="_blank" class='ml-1' v-show="!!flatfileURL" :href="flatfileURL"><i class="fa fa-link"></i></a>
                <button type="button" class="btn btn-primary ml-1" onclick="this.nextElementSibling.click()"
                        :aria-label='doc' data-balloon-pos="down" data-balloon-length="large">
                    upload
                </button>
                <!- THIS MUST ALWAYS BE NEXT TO THE BUTTON ABOVE: ->
                <input type="file" v-show="false" @change="filesUploaded($event.target.files)"/>
            </div>
        </div>
    </div>`
});


Vue.component('flatfile-selexpr-input', {
    props: {
        field: {type: Object},
        doc: {
            type: String,
            default: `Type an expression that operates on arbitrary flatfile columns to select
                      only rows matching the expression, e.g.: "magnitude>5" (quote characters "" excluded).
                      Valid comparison operators are == != > < >= <=.
                      Logical operators are & (and) | (or) ! (not), e.g.:
                      "(magnitude >= 5) & (vs30 > 760)".
                      Use notna([column]) to match rows where the column value is given,
                      i.e. not 'not available' (na). For instance, to get records where at rjb or
                      repi is available:
                      "(magnitude>5) & (notna(rjb) | notna(repi))"
                      (notna works for numeric and string columns only)
                      `
        }
    },
    template: `<div class='d-flex flex-column'
             :aria-label="doc" data-balloon-pos="down" data-balloon-length="xlarge">
            <field-label :field='field'/>
            <field-input :field='field' style='flex:1 1 auto'/>
        </div>`
});
