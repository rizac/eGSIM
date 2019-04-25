// register the grid component
Vue.component('testingtable', {
    props: {
        data: {type: Object, default: () => { return{} }}
    },
    data: function () {
	    var colnames = ['Measure of fit', 'IMT', 'GSIM', 'Value(s)'];
	    return {
            visible: false,
            tableData: [],
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
                try{
                    this.tableData = this.visible ? this.init.call(this, newval) : [];
                }catch(error){
                    this.visible = false;
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
        	var isSorting = sortCol && sortOrder!=0;
        	if (!isSorting){
        		return tData;
        	}
        	// we need to sort:
        	var isSortingValues =  isSorting && (sortCol === this.COL_VAL);
        	var [COL_MOF, COL_IMT] = [this.COL_MOF, this.COL_IMT]; //this is not passed in the func below
        	return tData.slice().sort(function(elm1, elm2) {  // .slice() makes a copy right ??
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
    },
    // for sort keys and other features, see: https://vuejs.org/v2/examples/grid-component.html
    template: `<div v-show="visible">
    <table class='testing-table'>
        <thead>
            <tr>
                <th v-for="key in colnames"
                  @click="sortBy(key)"
                  :class="{ active: isSortKey(key) }"
                  class='btn-primary align-items-baseline' style='cursor:pointer'>
                  {{ key }}
                  <span v-if='isSortKey(key) && columns[key].sortOrder > 0'> <!-- ascending -->
                  	<i class="fa fa-sort-desc"></i>  <!-- ascending means we grow as we go down, so desc icon (V) makes more sense --> 
                  </span>
                  <span v-else-if='isSortKey(key) && columns[key].sortOrder < 0'> <!-- descending -->
                  	<i class="fa fa-sort-asc"></i>  <!-- descending means we grow as we go up, so asc icon (^) makes more sense --> 
                  </span>
                </th>
            </tr>
        </thead>
        <tbody>
            <tr v-for="entry in filteredSortedEntries">
            	<template v-for="colname in colnames">
            		<td v-if="colname === COL_VAL" class='text-right'>
            			{{ entry[colname] | numCell2Str(MAX_NUM_DIGITS, MAX_ARRAY_SIZE) }}
            		</td>
            		<td v-else>
            			{{ entry[colname] }}
            		</td>
            	</template>
            </tr>
        </tbody>
    </table>
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
        		if (columns[colname].sortKey){
        			newSortOrder = columns[colname].sortOrder + 1;
        			if (newSortOrder > 1){
        				newSortOrder = -1;
        			}
        			columns[colname].sortOrder = newSortOrder;
        		}
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
        }
    }
});