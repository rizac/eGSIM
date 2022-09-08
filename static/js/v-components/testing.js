/**
 * Registers globally the testing component (model-to-data testing).
 * The component name must be a name of a `TAB` Enum in egsim.gui.__init__.py
 */
Vue.component('testing', {
    props :{
        form: Object,
        url: String,
        urls: Object, // object with to props: downloadRequest, downloadResponse (both string)
    },
    data: function () {
        return {
            formVisibilityToggle: true,  // switch form visibility on/off
            responseData: {}
        }
    },
    watch: {
    },
    computed: {
        isEDRSelected(){
            var val = this.form.fit_measure.value;
            edr = val && val.length && val.some(v => v.toLowerCase() == 'edr');
            // if disabled, data is not sent to the server (for safety):
            this.form.edr_bandwidth.disabled = !edr;
            this.form.edr_multiplier.disabled = !edr;
            return edr;
        }
    },
    template: `
<div class='d-flex flex-column position-relative' style="flex: 1 1 auto">
    <egsim-form :form="form" :url="url" :download-url="urls.downloadRequest"
                :visibilityToggle="formVisibilityToggle"
                @submitted="responseData=arguments[0].data">

        <template v-slot:left-column>
            <gsim-select :field="form.gsim" :imtField="form.imt" style="flex:1 1 auto"/>
        </template>

        <template v-slot:right-column>
            <imt-select :field="form.imt" size="6"></imt-select>

            <div class="mt-4 form-control pb-3 pt-2" style="background-color:transparent">
                <flatfile-select :field="form.flatfile"></flatfile-select>
                <flatfile-selexpr-input :field="form.selexpr" class='mt-3'></flatfile-selexpr-input>
            </div>
            
            <div class="mt-4" style="background-color:transparent">
                <field-input :field='form.fit_measure' size="5"></field-input>
                <base-input v-show="isEDRSelected" class='mt-1'
                            v-model="form.edr_bandwidth.value"
                            :disabled="form.edr_bandwidth.disabled"
                            :error="!!form.edr_bandwidth.error">
                    {{ form.edr_bandwidth.name }}
                </base-input>
                <base-input v-show="isEDRSelected" class='mt-1'
                            v-model="form.edr_multiplier.value"
                            :disabled="form.edr_multiplier.disabled"
                            :error="!!form.edr_multiplier.error">
                    {{ form.edr_multiplier.name }}
                </base-input>
            </div>
        </template>
    </egsim-form>

    <testing-table :data="responseData" :download-url="urls.downloadResponse"
                   class='position-absolute pos-0' style='z-index:1'>
        <slot>
            <button @click='formVisibilityToggle=!formVisibilityToggle' class='btn btn-sm btn-primary'>
                <i class='fa fa-list-alt'></i> Configuration
            </button>
        </slot>
    </testing-table>
</div>`
});


// register the grid component
Vue.component('testing-table', {
    props: {
        data: {type: Object, default: () => { return{} }},
        filename: {type: String},
        downloadUrl: String  // base url for download actions
    },
    data: function () {
        var colnames = ['Measure of fit', 'IMT', 'GSIM', 'Value'];
        return {
            downloadActions: [],  // populated when data is there, see watch.data
            visible: false,
            filterNames: colnames.slice(0, colnames.length-1),
            filterValues: {},  // Object of filterNames -> list of possible values for the filter name
            filterSelectedValues: {}, // Object of filterNames -> list of chosen values for the filter name
            tableData: [],
            gsimsRecords: [], // array of [gsim, records] elements (string, int)
            gsimsSkipped: {}, //Object of gsims (strings) mapped to its error (e.g., 0 records found)
            MAX_NUM_DIGITS: 5,  // 0 or below represent the number as it is
            MAX_ARRAY_SIZE: 4,  // arrays longer than this will be truncated in their string represenation (in the table)
            COL_MOF: colnames[0],
            COL_IMT: colnames[1],
            COL_GSIM: colnames[2],
            COL_VAL: colnames[3],
            colnames: colnames, //this stores the indices
            columns: {}  // this stores columns data (Object) keyed by each colname. See `init`
        }
    },
    created: function(){
        this.createFilterValues([]);
    },
    watch: {
        data: {
            immediate: true,
            handler(newval, oldval){
                this.visible = (typeof newval === 'object') && !!(Object.keys(newval).length);
                if (this.visible){
                    this.downloadActions = this.createDownloadActions();
                    this.gsimsRecords = newval['Db records'];
                    this.gsimsSkipped = newval['Gsim skipped'];
                    this.tableData = this.init.call(this, newval['Measure of fit']);
                }else{
                    this.gsimsRecords = [];
                    this.gsimsSkipped = [];
                    this.tableData = [];
                }
            }
        }
    },
    computed: {
        filteredSortedEntries: function () {  // (filtering actually not yet implemented)
            var [sortCol, sortOrder] = this.sortKeyAndOrder();
            var tData = this.tableData;
            var columns = this.columns;
            var colnames= this.colnames;
            var [COL_MOF, COL_IMT, COL_GSIM] = [this.COL_MOF, this.COL_IMT, this.COL_GSIM]; //this is not passed in the func below
            var isSorting = sortCol && sortOrder!=0;
            if (isSorting){
                tData = tData.slice()  // we need copy of data (by ref, shouldn't be too heavy)
                // we need to sort:
                var isSortingValues =  isSorting && (sortCol === this.COL_VAL);
                tData = tData.sort(function(elm1, elm2) {
                    // try to sort by the sortColumn first:
                    // (NOTE: JavaScript compares arrays bu first element):
                    var [val1, val2] = [elm1[sortCol], elm2[sortCol]];
                    var sortResult = (val1 > val2 ? 1 : (val1 < val2 ? -1: 0 )) * sortOrder;

                    if (!isSortingValues && sortResult == 0){ // we are not sorting by values: if sortResult is in (-1, 1)
                        // great, no need to get herein, Otherwise, use other columns to calculate a non-zero sort
                        // Order (there MUST be one)
                        for (var colname of colnames){
                            if (colname == sortCol){
                                continue;
                            }
                            var colvalues = columns[colname].values;
                            var [val1, val2] = [colvalues.indexOf(elm1[colname]), colvalues.indexOf(elm2[colname])];
                            sortResult = (val1 > val2 ? 1 : (val1 < val2 ? -1: 0 ));
                            if (sortResult !== 0){
                                return sortResult;
                            }
                        }

                    }else if (isSortingValues){
                        // we are sorting by values. Most likely, the sortResult is in (-1,1), but we want
                        // too kepp sorting GRROUPED BY [MOF, and IMT]. So, first SORT
                        // by those columns (thre might NOT be a different value) and return the sort result
                        // if it's not zero. If zero, return the sortResult we calculated above
                        for (var colname of [COL_MOF, COL_IMT]){
                            var colvalues = columns[colname].values;
                            var [val1, val2] = [colvalues.indexOf(elm1[colname]), colvalues.indexOf(elm2[colname])];
                            var sortResult2 = (val1 > val2 ? 1 : (val1 < val2 ? -1: 0 ));
                            if (sortResult2 !== 0){
                                return sortResult2;
                            }
                        }
                    }
                    return sortResult;
                });
            }
            // filter:
            var fsv = this.filterSelectedValues;
            var filterNames = Object.keys(fsv);
            isTableEntryVisible =
                (entry) =>  filterNames.every(key => !fsv[key].length || fsv[key].includes(entry[key]));
            tData = tData.filter(entry => isTableEntryVisible(entry));

            // the sort groups are defined by [COL_MOF, COL_IMT] unless
            // sortCol == COL_GSIM or sortCol == COL_IMT
            var oddeven = 1;
            tData.forEach((item, idx, items) => {
                var mofDiffers = idx == 0 || (item[COL_MOF] !== items[idx-1][COL_MOF]);
                var imtDiffers = idx == 0 || (item[COL_IMT] !== items[idx-1][COL_IMT]);
                var gsimDiffers = idx == 0 || (item[COL_GSIM] !== items[idx-1][COL_GSIM]);
                if (isSorting && (sortCol == COL_GSIM)){
                    groupChanged = gsimDiffers;
                }else if (isSorting && (sortCol == COL_IMT)){
                    groupChanged = imtDiffers;
                }else{
                    groupChanged = mofDiffers || imtDiffers;
                }
                if (groupChanged){
                    oddeven = 1-oddeven;
                }
                item._group = oddeven;
            });
            return tData;
        }
    },
    // for sort keys and other features, see: https://vuejs.org/v2/examples/grid-component.html
    template: `<div v-show="visible" class="d-flex flex-row">
        <div class='d-flex flex-column' style="flex: 1 1 auto">
            <div class='testing-table border-primary' style='flex: 1 1 auto;overflow-y: auto;'>
                <table class='table testing-table' style="flex: 1 1 auto">
                    <thead>
                        <tr>
                            <th v-for="colname in colnames" @click="sortBy(colname)"
                                class='btn-primary align-text-top'
                                :class="{'text-right': colname === COL_VAL}">
                                {{ colname }}
                                <br>
                                <i v-if='isSortKey(colname) && columns[colname].sortOrder > 0' class="fa fa-chevron-down"></i>
                                <i v-else-if='isSortKey(colname) && columns[colname].sortOrder < 0' class="fa fa-chevron-up"></i>
                                <i v-else> &nbsp;</i> <!--hack for preserving height when no arrow icon is there. tr.min-height css does not work -->
                            </th>
                        </tr>
                    </thead>
                    <tbody>
                        <template v-for="(entry, index) in filteredSortedEntries">
                            <tr :style="entry._group ? 'background-color: rgba(0,0,0,.05)':  ''">
                                <template v-for="colname in colnames">
                                    <td v-if="colname === COL_VAL" class='align-top text-right'>
                                        {{ entry[colname] | numCell2Str(MAX_NUM_DIGITS, MAX_ARRAY_SIZE) }}
                                    </td>
                                    <td v-else class='align-top'>{{ entry[colname] }}</td>
                                </template>
                            </tr>
                        </template>
                    </tbody>
                </table>
            </div>
            <span class='small text-muted mt-1'>
                <i class="fa fa-info-circle"></i>
                Click on the table headers to sort. Note that "{{ COL_VAL }}" will not sort
                rows globally but within each group of equal ({{ COL_MOF }}, {{ COL_IMT }}).
            </span>
        </div>

        <div class='d-flex flex-column pl-4'>

            <slot></slot> <!-- slot for custom buttons -->

            <div v-show='Object.keys(filterSelectedValues).length'
                 class='mt-3 border p-2 bg-white'
                 style='flex: 1 1 0; overflow:auto; min-height:3rem'>
                <div v-for='filterName in Object.keys(filterSelectedValues)'
                     class="d-flex flex-column mt-2" style="flex: 1 1 auto">
                    <div class='d-flex flex-row'>
                        <span style="flex: 1 1 auto"><i class="fa fa-filter"></i> {{ filterName }}</span>
                        <button @click='clearFilters(filterName)' type='button'
                                :style="filtersCount(filterName) > 0 ? {} : {visibility: 'hidden'}"
                                style='padding-top:0.1rem; padding-bottom:0.1rem'
                                class='btn btn-outline-secondary btn-sm ml-2'>
                            <i class="fa fa-eraser"></i> Clear filter (show all)
                        </button>
                    </div>
                    <label v-for='value in filterValues[filterName]'
                           class='customcheckbox'
                           :class="{'checked': filterSelectedValues[filterName].includes(value)}">
                        <input type='checkbox' :value="value" v-model='filterSelectedValues[filterName]'> {{ value }}
                    </label>
                </div>
            </div>

            <div class='mt-3 border p-2 bg-white'>
                <action-select :actions="downloadActions" class="form-control"
                               data-balloon-pos='left' data-balloon-length='medium'
                               aria-label='Download the computed results in different formats'>
                    Download as:
                </action-select>
            </div>

            <div v-show="Object.keys(gsimsRecords).length" class='mt-3 border p-2 bg-white'
                 style='overflow:auto;  max-height:10rem'>
                <div><i class="fa fa-info-circle"></i> Database records used:</div>
                <table>
                <tr v-for="gsimname in Object.keys(gsimsRecords)"
                    v-if="!Object.keys(gsimsSkipped).includes(gsimname)">
                    <td class='text-right pr-2'>{{ gsimname }}:<td>
                    </td>{{ gsimsRecords[gsimname] }}</td>
                </tr>
                </table>
            </div>
            <div v-show="Object.keys(gsimsSkipped).length"
                 class='mt-3 border p-2 bg-white text-danger' style='overflow:auto;max-height:10rem'>
                <div><i class="fa fa-exclamation-triangle"></i> Gsim skipped:</div>
                <table>
                <tr v-for="gsimname in Object.keys(gsimsSkipped)">
                    <td class='text-right pr-2'>{{ gsimname }}:</td>
                    <td>{{ gsimsSkipped[gsimname] }}</td>
                </tr>
                </table>
            </div>
        </div>
    </div>`,
    filters: {
        numCell2Str: function (val, maxNumDigits, maxArraySize) {
            // provide a string representation of the value:
            var tostr = elm => maxNumDigits > 0 ? Number(elm).toFixed(maxNumDigits > 20 ? 20 : maxNumDigits) : '' + elm;
            if(typeof val == 'object' & val instanceof Array){
                if(val.length > maxArraySize){
                    var num = parseInt(maxArraySize/2);
                    strval = val.slice(0, num).map(elm => tostr(elm)).concat(['...'],
                        val.slice(val.length-num, val.length).map(elm => tostr(elm)));
                }else{
                    strval = val.map(elm => Number(elm).toFixed(maxD));
                }
                return `${strval.join(', ')} (${val.length} elements)`;
            }
            return tostr(val);
        }
    },
    methods: {
        filtersCount: function(filterName){
            // returns the number of elements currently selected for the filter identified by 'filterName'
            // if 'filterName' is undefined, returns all elements currently selected for all filters
            var sum = 0;
            for (var k of Object.keys(this.filterSelectedValues)){
                if (filterName === undefined || filterName === k){
                    sum += this.filterSelectedValues[k].length;
                }
            }
            return sum;
        },
        clearFilters: function(filterName){
            // clear the filter for the filter identified by 'filterName'
            // if 'filterName' is undefined, clears all filters (show all elements in table)
            for (var k of Object.keys(this.filterSelectedValues)){
                if (filterName === undefined || filterName === k){
                    this.filterSelectedValues[k] = [];
                }
            }
        },
        sortBy: function (key) {
            var columns = this.columns;
            if (!(key in columns)){return;}
            var ret = {}; // copy a new Object (see below)
            this.colnames.forEach(colname => {
                columns[colname].sortKey = key === colname;
                var newSortOrder = 0; //default sort order (all columns except the sorting column will be reset to this value)
                if (columns[colname].sortKey){
                    newSortOrder = columns[colname].sortOrder + 1;
                    if (newSortOrder > 1){
                        newSortOrder = -1;
                    }
                }
                columns[colname].sortOrder = newSortOrder;
                ret[colname] = columns[colname];
            });
            // by setting a new object we trigger the template refresh.
            // this might look overhead but it triggers vuejs refresh without the need of watchers and/or
            // deep flags
            this.columns = ret;
        },
        sortKeyAndOrder: function(){
            for (var colname of this.colnames){
                if (this.isSortKey(colname)){
                    return [colname, this.columns[colname].sortOrder];
                }
            }
            return ["", 0];
        },
        isSortKey: function(colname){
            return !!((this.columns[colname] || {}).sortKey);  //!! = coerce to boolean
        },
        init: function(data){
            // make an Array of Arrays (tabular-like) from the Object data
            // and store all possible Measures of Fit (mof), imt and gsims.
            // return the Array of data
            var MAXARRAYSIZE = 6;
            var colnames = this.colnames;
            var columns = this.columns;
            // reset values:
            colnames.forEach(colname => {
                if (!(colname in columns)){
                    columns[colname]={sortOrder: 0, sortKey: false};
                }
                columns[colname].values = [];
            });

            var mofs = columns[this.COL_MOF].values = Object.keys(data);
            var ret = [];
            for (var mof of mofs){
                var imts = data[mof];
                for(var imt of Object.keys(imts)){
                    if (!columns[this.COL_IMT].values.includes(imt)){
                        columns[this.COL_IMT].values.push(imt);
                    }
                    var gsims = imts[imt];
                    for (var gsim of Object.keys(gsims)){
                        if (!columns[this.COL_GSIM].values.includes(gsim)){
                            columns[this.COL_GSIM].values.push(gsim);
                        }
                        var val = gsims[gsim];
                        var row = {};
                        row[this.COL_MOF] = mof;
                        row[this.COL_IMT] = imt;
                        row[this.COL_GSIM] = gsim;
                        row[this.COL_VAL] = val;
                        ret.push(row);  // {val: val, sortval: sortval, strval: strval}]);
                    }
                }
            }
            this.createFilterValues(ret);
            return ret;
        },
        createFilterValues: function(tableData){
            [this.filterValues, this.filterSelectedValues] = [{}, {}];
            var filterNames = this.filterNames;
            for (var key of filterNames){
                // use sets to assure unique values:
                this.filterValues[key] = new Set();
            }
            for (var entry of tableData){
                for (var key of filterNames){
                    this.filterValues[key].add(entry[key]);
                }
            }
            // convert sets to array:
            for (var key of filterNames){
                if (this.filterValues[key].size <= 1){
                    continue;
                }
                this.filterValues[key] = Array.from(this.filterValues[key]);
                this.$set(this.filterSelectedValues, key, []);
            }
        },
        createDownloadActions(){
            return EGSIM.createDownloadActions(this.downloadUrl, this.data);
        }
    }
});