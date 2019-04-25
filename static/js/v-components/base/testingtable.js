// register the grid component
Vue.component('testingtable', {
    props: {
        data: {type: Object, default: () => { return{} }}
    },
    data: function () {
    	var columns = ['Measure of fit', 'IMT', 'GSIM', 'Value(s)'];
    	// define sortOrder here so that it will be reactive (nested):
    	var sortOrders = {};
    	for(var col of columns){
    		sortOrders[col] = -1;
    	}
        return {
            visible: false,
            tableData: {},
            maxNumDecimalDigits: 5,
            columns: columns,
            sortKey: columns[columns.length-1],
            sortOrders: sortOrders,
        }
    },
    watch: {
        data: {
            immediate: true,
            handler(newval, oldval){
                this.visible = !Vue.isEmpty(newval);
                try{
                    this.tableData = this.visible ? this.init.call(this, this.data) : [];
                }catch(error){
                    this.visible = false;
                }
            }
        },
    },
    computed: {    
        filteredSortedEntries: function () {  // (filtering actually not yet implemented)
            var sortKey = this.sortKey;
            var index = this.columns.indexOf(sortKey);
            var tData = this.tableData;
            var order = this.sortOrders[sortKey] || 1;
            if (order !== 0){
            	tData = tData.slice();  // .slice() makes a copy right ??
	            if (index === this.columns.length - 1){
	            	// if clicking on the values, then sort by GROUP (it does
	            	// not make sense to sort all values together)
	            	var [mofIdx, imtIdx, gsimIdx] = [{}, {}, {}];
	            	
	            	tData = tData.sort(function(elm1, elm2) {  // .slice() makes a copy right ??
	            		// sort up to index, preserving the group:
	            		for (var i=0; i<2 ; i++){
	            			if (elm1[i] > elm2[i]){
	            				return 1 * (index == i ? order : 1);
	            			}else if(elm2[i] > elm1[i]){
	            				return -1 * (index == i ? order : 1);
	            			}
	            		}
	            		
	            		var idx = index > 1 ? index : this.columns.length -1;
	            		// keys are the same up to index, sort by index:
	                    val1 = elm1[idx].sortval || elm1[idx];
	                    val2 = elm2[idx].sortval || elm2[idx];
	                    return (val1 >= val2 ? 1 : -1) * (index == idx ? order : 1);
	                })
	            }
	            if (index > -1) {
	                var order = this.sortOrders[sortKey] || 1;
	            	tData = tData.sort(function(elm1, elm2) {  // .slice() makes a copy right ??
	            		// sort up to index, preserving the group:
	            		for (var i=0; i<2 ; i++){
	            			if (elm1[i] > elm2[i]){
	            				return 1 * (index == i ? order : 1);
	            			}else if(elm2[i] > elm1[i]){
	            				return -1 * (index == i ? order : 1);
	            			}
	            		}
	            		
	            		var idx = index > 1 ? index : this.columns.length -1;
	            		// keys are the same up to index, sort by index:
	                    val1 = elm1[idx].sortval || elm1[idx];
	                    val2 = elm2[idx].sortval || elm2[idx];
	                    return (val1 >= val2 ? 1 : -1) * (index == idx ? order : 1);
	                })
	            }
            }
            return tData
        }
    },
    // for sort keys and other features, see: https://vuejs.org/v2/examples/grid-component.html
    template: `<div v-show="visible">
    <table class='testing-table'>
        <thead>
            <tr>
                <th v-for="key in columns"
                  @click="sortBy(key)"
                  :class="{ active: sortKey == key }"
                  class='btn-primary'>
                  {{ key }}
                  <span v-if='sortKey == key && sortOrders[key] > 0'> <!-- ascending -->
                  	[ASC]
                  </span>
                  <span v-else='sortKey == key && sortOrders[key] > 0'> <!-- descending -->
                  	[DESC]
                  </span>
                  <!-- <span class="arrow" :class="sortOrders[key] > 0 ? 'asc' : 'dsc'"> -->
                  </span>
                </th>
            </tr>
        </thead>
        <tbody>
            <tr v-for="entry in filteredSortedEntries">
                <template v-for="(element, index) in entry">
                    <td :class="{ 'text-right': index === entry.length-1 }">
                    {{ element.strval || element }}
                    </td>
                </template>
            </tr>
        </tbody>
    </table>
    </div>`,
    filters: {
//         toCellStr: function (value) {
//             
//         }
    },
    methods: {
        sortBy: function (key) {
            this.sortKey = key
            this.sortOrders[key] = (this.sortOrders[key] || -1) * -1;
        },
        init: function(data){
            var MAXARRAYSIZE = 6;
            var maxD = this.maxNumDecimalDigits;
            var ret = [];
            for (var mof of Object.keys(data)){
                var imts = data[mof];
                for(var imt of Object.keys(imts)){
                    var gsims = imts[imt];
                    var [strval, sortval] = ['', 0];
                    for (var gsim of Object.keys(gsims)){
                        var val = gsims[gsim];
                       	if(typeof val == 'object' & val instanceof Array){
                       		if(val.length > MAXARRAYSIZE){
                        		strval = val.slice(0, MAXARRAYSIZE/2).map(elm => Number(elm).toFixed(maxD)).concat(['...'],
                        			val.slice(val.length-MAXARRAYSIZE/2, val.length).map(elm => Number(elm).toFixed(maxD)));
                        	}else{
                        		strval = val.map(elm => Number(elm).toFixed(maxD));
                        	}
                        	strval = `${strval.join(', ')} (${val.length} elements)`;
                        	sortval = Number(val[0]);
                       	}else{
                        	strval = Number(val).toFixed(maxD);
                        	sortval = val;
                       	}
                        ret.push([mof, imt, gsim, {val: val, sortval: sortval, strval: strval}]);
                    }
                }
            }
            return ret;
        }
    }
});