// register the grid component
Vue.component('testingtable', {
    props: {
        data: {type: Object, default: () => { return{} }},
        filename: {type: String},
        // these two properties are passed to the downloadselect for downloading the response:
        downloadurls: {type: Array, default: () => []},
        post: {type: Function}
    },
    data: function () {
	    var colnames = ['Measure of fit', 'IMT', 'GSIM', 'Value'];
	    return {
            visible: false,
            tableData: [],
            gsimsRecords: [], // array of [gsim, records] elements (string, int)
            gsimsSkipped: {}, //Object of gsims (strings) mapped to its error (e.g., 0 records found)
            rowInfo: [], // Array of Objects storign row info for styling/rendereing (popolated in filteredSortedEntries)
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
    watch: {
        data: {
            immediate: true,
            handler(newval, oldval){
                this.visible = !Vue.isEmpty(newval);
                if (this.visible){
                    this.gsimsRecords = newval['Db records'];
                    this.gsimsSkipped = newval['Gsim skipped'];
                	this.tableData = this.init.call(this, newval['Measure of fit']);
                }else{
                	this.gsimsRecords = [];
                	this.gsimsSkipped = [];
                	this.tableData = [];
                }
            }
        },
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
	        // the sort groups are defined by [COL_MOF, COL_IMT] unless
	        // sortCol == COL_GSIM or sortCol == COL_IMT
	        var oddeven = 1;
	        this.rowInfo = tData.map((item, idx, items) => {
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
	        	/* note: isHidden below should hold a set of keys (columns) mapped to boolean values
	        	telling if for that row the cell should be displayed (ret[index].isHidden(colname)).
	        	It's not used and defaults to the empty dict. If
	        	you want to remove the property, look at the template and remove it from there
	        	as well */
	        	var ret = {isHidden: {}, group: oddeven};
	        	/*ret.isHidden[COL_MOF] = !groupChanged && !mofDiffers;
	        	ret.isHidden[COL_IMT] = !groupChanged && !imtDiffers;
	        	ret.isHidden[COL_GSIM] = !groupChanged && !gsimDiffers;*/
	        	return ret;
	        });
            return tData;
        }
    },
    // for sort keys and other features, see: https://vuejs.org/v2/examples/grid-component.html
    template: `<div v-show="visible" class="d-flex flex-row">
	    <div class='testing-table flexible btn-primary'>
		    <table class='table testing-table'>
		        <thead>
		            <tr>
		            	<th v-for="colname in colnames" @click="sortBy(colname)"
		                  class='btn-primary align-text-top'
		                  :class="{'text-right': colname === COL_VAL}"
		                  >
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
			            <tr :style="rowInfo[index].group ? 'background-color: rgba(0,0,0,.05)':  ''">
			            	<template v-for="colname in colnames">
			            		<td v-if="colname === COL_VAL" class='align-top text-right'>
			            			{{ entry[colname] | numCell2Str(MAX_NUM_DIGITS, MAX_ARRAY_SIZE) }}
			            		</td>
			            		<td v-else class='align-top'>
			            			{{ rowInfo[index].isHidden[colname] ? "" : entry[colname] }}
			            		</td>
			            	</template>
			            </tr>
		            </template>
		        </tbody>
		    </table>
	    </div>
	   
	    <div class='d-flex flex-column mr-2 pl-2 border-left'>

            <slot></slot> <!-- slot for custom buttons -->
            
            <downloadselect
				:urls="downloadurls"
				:post="post"
				:data="data"
				class='mt-3 border p-2 bg-white'
			/>
	           
            <div v-show="Object.keys(gsimsRecords).length" class='mt-3 border p-2 bg-white' style='overflow:auto'>
                <div><i class="fa fa-info-circle"></i> Database records used:</div>
                <table>
                <tr
                    v-for="gsimname in Object.keys(gsimsRecords)"
                >
                    <td class='text-right pr-2'>{{ gsimname }}:<td></td>{{ gsimsRecords[gsimname] }}</td>
                </tr>
                </table>
            </div>
            <div v-show="Object.keys(gsimsSkipped).length" class='mt-3 border p-2 bg-white text-danger' style='overflow:auto'>
                <div><i class="fa fa-exclamation-triangle"></i> Gsim skipped:</div>
                <table>
                <tr
                    v-for="gsimname in Object.keys(gsimsSkipped)"
                    
                >
                    <td class='text-right pr-2'>{{ gsimname }}:</td><td>{{ gsimsSkipped[gsimname] }}</td>
                </tr>
                </table>
            </div>
            <div class='position-relative flexible mt-3'>
                <span class='position-absolute pos-b-0 small text-muted'>
                    <i class="fa fa-info-circle"></i>
                    Click on the table headers to sort. Note that "{{ COL_VAL }}" will not sort
                    rows globally but within each group of equal ({{ COL_MOF }}, {{ COL_IMT }}).
                </span>
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
        	// this might look overhead but it triggers vuwjs refresh without the need of watchers and/or
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
            return ret;
        },
        download: function(format, formatIndex, formats){
        	var filename = this.filename + '.request';
        	if (format === 'json'){
        		Vue.download(this.data, filename + '.json'); // defined in vueutil.js
        	}
        }
    }
});