/**
 * Registers globally a Vue component. The name of the component
 * (first argument of 'Vue.component' below must be equal to this file's name 
 * (without extension)
 */
Vue.component('flatfile', {
    //https://vuejs.org/v2/guide/components-props.html#Prop-Types:
    props: {
        forms: Array,
        urls: Array
        // response: {type: Object, default: () => {return {}}}
    },
    data: function () {
        var compNames = ['flatfile-columns'];  //, 'flatfile-inspection', 'flatfile-plot'];
        var compProps = {};
        compNames.forEach((elm, index) => {
            compProps[elm] = {
                form: this.forms[index],
                url: this.urls[index]
            };
        }, this);
        var compLabels = {
            'flatfile-columns': 'Help',
            'flatfile-inspection': 'Inspection',
            'flatfile-plot': 'Plot'
        };
        return {
            componentNames: compNames,
            componentLabels: compLabels,
            componentProps: compProps,
            selComponentName: compNames[0],
        }
    },
    computed: {
        tableRows: function(){
            var colNames = this.tableColumns;
            if (!colNames.length){ return []; }
            var firstColObj = this.responseData.columns[colNames[0]];
            return Object.keys(firstColObj);
        },
        tableColumns: function(){
            return Object.keys(this.responseData.columns).sort();
        }
    },
    template: `
    <div class='d-flex flex-column' stle='flex: 1 1 auto'>
        <ul class="nav nav-tabs">
            <li class="nav-item" v-for="compName in componentNames">
                <a class="nav-link" :class="selComponentName==compName ? 'active' : ''"
                   :click='selComponentName=compName'
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


Vue.component('flatfile-columns', {
    mixins: [BASE_FORM],
    //https://vuejs.org/v2/guide/components-props.html#Prop-Types:
    props: {
        form: Object,
        url: String,
        response: {type: Object, default: () => {return {}}}
    },
    data: function () {
        return {
            responseData: this.response
        }
    },
    computed: {
        columns(){
            var data = this.responseData;
            var namesOk = Object.keys(data).filter(name => !!Object.keys(data[name]).length);
            var namesNo = Object.keys(data).filter(name => !Object.keys(data[name]).length);
            var ret = [];
            for (var name of namesOk.sort()){
                ret.push([name, data[name].help, data[name].dtype]);
            }
            return ret;
        }
    },
    template: `<form novalidate @submit.prevent="submit" class='d-flex flex-column align-items-end' style='flex: 1 1 auto'>
        <div class='d-flex flex-row' style='flex: 1 1 auto'>
            <div class='d-flex flex-column' style='flex: 1 1 40%'>
                <div style='font-family:sans-serif'>
                    Flatfiles must be uploaded as uncompressed or zipped CSV file with
                    rows representing manually processed waveforms and columns denoting:
                    <ul>
                    <li>The intensity measures of interest (supported are PGA, PGV
                    or SA with periods in brackets, e.g. "SA(0.1)")</li>
                    <li>The metadata required by the models used. Select
                    your models below to see the required flatfile columns in the right table:</li>
                    </ul>
                </div>
                <div class='d-flex' style='flex:1 1 auto'>
                    <gsim-select :field='form.gsim' @gsim-selected='gsimSelected'></gsim-select>
                </div>
            </div>
            <div class='d-flex flex-column ml-3' style="flex: 1 1 60%">
                <div>Flatfile metadata columns ({{ columns.length }})</div>
                <div style="flex: 1 1 auto; position:relative;overflow:auto">
                    <table class="table" style='position:absolute;top:0;bottom:0;right:0;left:0'>
                      <tr v-for="colObj in columns">
                        <td v-html="col2HTML(colObj)"></td>
                      </tr>
                    </table>
                </div>
            </div>
        </div>
        <div class='mt-3' style='font-family:sans-serif'>
            Note: In general, there are no restriction on the number of columns of a flatfile, as
            any column provided can eventually be used in selection expressions
            for filtering records. <b>However, please
            try to provide the strict minimum of columns in order to improve
            memory consumption and upload time</b>
        </div>
    </form>`,
    methods: {
        gsimSelected(){
            // delegate submit after the component has been rndered
            this.$nextTick(() => {
                this.submit().then(responseData => {
                    this.responseData = responseData;
                });
            });
        },
        col2HTML(colObject){
            var name = colObject[0];
            var desc = colObject[1];
            var dtype = colObject[2];
            if (desc === null){
                return `<span class="text-muted small">${name}</span>`;
            }
            if (Array.isArray(dtype)){
                dtype = `Data type: categorical, a value from ${dtype.join(", ")}`;
            }else{
                dtype = `Data type: ${dtype}`;
            }
            if (desc){ desc = ": " + desc;}
            return `<b>${name}</b>${desc}<br><span class='text-muted'>(${dtype})</span>`;
        }
    }
});

/*
Vue.component('flatfile-columns', {
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
    computed: {
        tableRows: function(){
            var colNames = this.tableColumns;
            if (!colNames.length){ return []; }
            var firstColObj = this.responseData.columns[colNames[0]];
            return Object.keys(firstColObj);
        },
        tableColumns: function(){
            return Object.keys(this.responseData.columns).sort();
        }
    },
    template: `<div class='d-flex flex-column' style='flex: 1 1 auto'>
        <div class='mb-3'>
            <base-form :form="form" :url="url" class='d-flex flex-row align-items-end'
                        @form-successfully-submitted="responseData=arguments[0]">
                <slot>
                    <div class="d-flex flex-row align-items-end mr-3" style='flex: 1 1 auto'>
                        <flatfile-select :field="form.flatfile"></flatfile-select>
                        <flatfile-selexpr-input :field="form.selexpr" class='ml-3' style='flex:1 1 auto'></flatfile-selexpr-input>
                        <!-- <field-input :field='form.x' class='ml-3'></field-input>
                             <field-input :field='form.y' class='ml-3'></field-input> -->
                    </div>
                </slot>
            </base-form>
        </div>
        <div class='d-flex flex-column' style="flex:1 1 auto; position: relative">
            <div class='d-flex flex-row' style='flex: 1 1 auto'>
                <div class='d-flex flex-column' style='flex: 1 1 40%'>
                    <div style='font-family:sans-serif'>
                        <p>Flatfiles must be uploaded as uncompressed or zipped CSV file with
                        rows representing manually processed waveforms and columns denoting the
                        waveform intensity measures and metadata.
                        <p>
                        The required intensity measures are user-dependent and can be PGA, PGV
                        or SA with periods in brackets, e.g. "SA(0.1)", the required metadata
                        depend on the models of interest which can be selected
                        from the list below (the metadata flatfile columns will update accordingly).
                        </p>
                    </div>
                    <div class='d-flex' style='flex:1 1 auto'>
                        <gsim-select :field='form.gsim'></gsim-select>
                    </div>
                </div>
                <div class='d-flex flex-column ml-3' style="flex: 1 1 60%">
                    <div class='mb-2'> Flatfile Metadata columns: </div>
                    <div style="flex: 1 1 auto; position:relative;overflow:auto">
                        <table class="table" style='position:absolute;top:0;bottom:0;right:0;left:0'>
                          <tr v-for="(cell, i) in form.flatfile['data-columns'][0]" v-if="i>0">
                            <td v-html="colHTML(i)"></td>
                          </tr>
                        </table>
                    </div>
                </div>
            </div>
            <div class='mt-3' style='font-family:sans-serif'>
                Note: In general, there are no restriction on the number of columns of a flatfile, as
                        any column provided can eventually be used in selection expressions
                        for filtering records. <b>However, please
                        try to provide the strict minimum of columns in order to improve
                        memory consumption and upload time</b>
            </div>
        </div>
        <div v-if="!!Object.keys(responseData).length" style="overflow:auto">
            <div> Flatfile records (number of rows): {{ responseData.rows }}. Data details per column:</div>
            <div> Missing columns: {{ responseData.missing_columns }} (these columns need to be implemented only if the models requiring them are used)</div>
            <table class='table'>
                <thead>
                    <tr><td></td><td v-for="col in tableColumns">{{ col }}</td></tr>
                </thead>
                <tbody>
                    <tr v-for="row in tableRows">
                        <td><b> {{ row }} </b> </td>
                        <td v-for="col in tableColumns" :title="responseData.columns[col][row]">{{ val(col, row) }}</td>
                    </tr>
                </tbody>
            </table>
        </div>
        <!-- <flatfile-plot-div :data="responseData" style='flex: 1 1 auto'></flatfile-plot-div> -->
    </div>`,
    methods: {
        colHTML(index){
            var ff = this.form.flatfile['data-columns'];
            var name = ff[0][index];
            var desc = ff[1][index];
            var dtype = ff[2][index];
            if (Array.isArray(dtype)){
                dtype = `Categories: ${dtype.join(", ")}`;
            }else{
                dtype = `Data type: ${dtype}`;
            }
            if (desc){ desc = ": " + desc;}
            return `<b>${name}</b> <span class='text-muted'>(${dtype})</span>${desc}`;
        },
        val(col, row){
            var val = this.responseData.columns[col][row];
            if ((typeof val == 'number') && (parseInt(val) != val) && (val > 0.00001)){
                val = val.toFixed(5);
            }
            return val;
        }
    }
});
*/

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
        doc: {
            type: String,
            default: `Upload a user-defined flatfile (CSV or zipped CSV).
                      IMPORTANT: please read compile instructions (tab "Flatfiles > Compile")
                      and try to inspect your flatfile before usage (tab "Flatfiles > Inspect").
                      An uploaded flatfile size should be kept within few Mb. Any uploaded
                      flatfile will be available in all page tabs`
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
    watch: { // https://siongui.github.io/2017/02/03/vuejs-input-change-event/
        'fieldProxy.value': function(newVal, oldVal){
            // Set the field values as either a string (predefined flatfile) or a File
            // Object
            for (var ff of this.flatfiles){
                if (ff.name == newVal){
                    if (ff.file){
                        newVal = ff.file;
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
                var label = `${file.name} (${new Date().toLocaleString()})`;
                for (var i=0; i<flatfiles.length; i++){
                    var flatfile = flatfiles[i];
                    if ((flatfile.name == file.name) && (flatfile.file)){
                        // `flatfile.file` assures we are modifying an user uploaded flatfile
                        flatfile.file = file;
                        flatfile.label = label;  // update label to show we overwrote the file
                        file = null;
                        break;
                    }
                }
                if (file != null){
                    flatfiles.push({
                        name: file.name, label: label, file: file
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
                    :aria-label='doc' data-balloon-pos="down" data-balloon-length="large">
                upload
            </button>
            <input type="file" class='ml-1' v-show="false" @change="filesUploaded($event.target.files)"/>
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
                      "(magnitude>5) & (notna(rjb) | notna(repi))"`
        }
    },
    template:`<div>
        <div class='d-flex flex-row align-items-end'
             :aria-label="doc" data-balloon-pos="down" data-balloon-length="xlarge">
            <field-input :field='field' style='flex:1 1 auto'></field-input>
        </div>
    </div>`
});
