/* Testing (model ranking) components (model-to-data testing) */


EGSIM.component('testing', {
	props :{
		form: Object,
		url: String,
		urls: Object, // object with to props: downloadRequest, downloadResponse (both string)
	},
	data() {
		return {
			formVisible: true,
			formAsDialogBox: false,
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
				:show="formVisible" :dialogbox="formAsDialogBox"
				@submitted="(response) => {formVisible=false;formAsDialogBox=true;responseData=response.data;}">

		<template v-slot:left-column>
			<gsim-select :field="form.gsim" :imtField="form.imt" style="flex:1 1 auto"/>
		</template>

		<template v-slot:right-column>
			<imt-select :field="form.imt" style="flex: 1 1 auto" />

			<div class="mt-4 form-control pb-3 pt-2" style="background-color:transparent">
				<flatfile-select :field="form.flatfile"/>
				<flatfile-selexpr-input :field="form.selexpr" class='mt-3'/>
			</div>
			
			<div class="mt-4" style="background-color:transparent">
				<field-label :field='form.fit_measure'/>
				<field-input :field='form.fit_measure' size="5"/>

				<div class='invisible small' :style="{visibility: isEDRSelected ? 'visible !important': 'hidden'}">
					<field-label :field="form.edr_bandwidth" class='mt-2' />
					<field-input class='small' :field="form.edr_bandwidth" />
					<field-label :field="form.edr_multiplier" class='mt-2' />
					<field-input class='small' :field="form.edr_multiplier" />
				</div>
			</div>
		</template>
	</egsim-form>

	<testing-table :data="responseData" :download-url="urls.downloadResponse"
					class='invisible position-absolute start-0 top-0 end-0 bottom-0'
					:style="{visibility: Object.keys(responseData).length ? 'visible !important' : '', 'z-index':1}">
		<slot>
			<button @click='formVisible=!formVisible' class='btn btn-sm btn-primary'>
				<i class='fa fa-list-alt'></i> Configuration
			</button>
		</slot>
	</testing-table>
</div>`
});


// register the grid component
EGSIM.component('testing-table', {
	mixins: [DataDownloader],
	props: {
		data: {type: Object, default: () => { return{} }},
		filename: {type: String},
		downloadUrl: String  // base url for download actions
	},
	data() {
		var colnames = ['Measure of fit', 'IMT', 'GSIM', 'Value'];
		return {
			visible: false,
			filterNames: colnames.slice(0, colnames.length-1),
			filterValues: {},  // Object of filterNames -> list of possible values for the filter name
			filterSelectedValues: {}, // Object of filterNames -> list of chosen values for the filter name
			tableData: [],
			gsimsRecords: {}, // Object of gsim (string): records (int)
			gsimsSkipped: {}, //Object of gsims (strings): error (string)
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
	created(){
		this.tableParentStyle = { 'border-width': '2px', 'border-style': 'solid', 'border-radius': '4px',
			 padding: '3px', color: 'initial !important', 'background-color': 'initial !important',
			 flex: '1 1 auto', 'overflow-y': 'auto'};
		this.tableTHStyle = { border: 'none !important', padding:'.5rem', 'line-height': '1rem', cursor: 'pointer' };
		// attrs above should be non reactive (==immutable) and consume less memory
		this.createFilterValues([]);
	},
	watch: {
		data: {
			immediate: true,
			handler(newval, oldval){
				this.visible = (typeof newval === 'object') && !!(Object.keys(newval).length);
				if (this.visible){
					this.gsimsRecords = newval['Db records'];
					this.gsimsSkipped = newval['Models skipped'];
					this.tableData = this.init.call(this, newval['Measure of fit']);
				}else{
					this.gsimsRecords = {};
					this.gsimsSkipped = {};
					this.tableData = [];
				}
			}
		}
	},
	computed: {
		filteredSortedEntries() {  // (filtering actually not yet implemented)
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
			<div class='border-primary' :style='tableParentStyle'>
				<table class='table' style="flex: 1 1 auto">
					<thead>
						<tr>
							<th v-for="colname in colnames" @click="sortBy(colname)"
								class='bg-primary text-white align-text-top'
								:class="{'text-end': colname === COL_VAL}"
								:style='tableTHStyle'
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
							<tr :style="entry._group ? 'background-color: rgba(0,0,0,.05)':  ''">
								<template v-for="colname in colnames">
									<td v-if="colname === COL_VAL" class='align-top text-end'>
										{{ entry[colname].toFixed(5) }}
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

		<div class='d-flex flex-column ps-4'>

			<slot></slot> <!-- slot for custom buttons -->

			<div v-show='Object.keys(filterSelectedValues).length'
				 class='mt-3 border p-2 bg-white'
				 style='flex: 1 1 0; overflow:auto; min-height:3rem'>
				<div v-for='filterName in Object.keys(filterSelectedValues)'
					 class="d-flex flex-column mt-2" style="flex: 1 1 auto">
					<div class='d-flex flex-row'>
						<span class="text-nowrap" style="flex: 1 1 auto">
							<i class="fa fa-filter"></i> {{ filterName }}
						</span>
						<button @click='clearFilters(filterName)' type='button'
								:style="filtersCount(filterName) > 0 ? {} : {visibility: 'hidden'}"
								style='padding-top:0.1rem; padding-bottom:0.1rem'
								class='btn btn-outline-secondary btn-sm ms-2'>
							<i class="fa fa-eraser"></i> Clear filter (show all)
						</button>
					</div>
					<label v-for='value in filterValues[filterName]' class="mt-1"
						   :class="{'checked': filterSelectedValues[filterName].includes(value)}">
						<input type='checkbox' :value="value" v-model='filterSelectedValues[filterName]'> {{ value }}
					</label>
				</div>
			</div>

			<div class='mt-3 border p-2 bg-white'>
				<select @change="downloadTriggered" class="form-control"
						aria-label='Download the computed results in different formats'>
					<option value="">Download as:</option>
					<option value="json">json</option>
					<option value="csv">text/csv</option>
					<option value="csv_eu">tex/csv (decimal comma)</option>
				</select>
			</div>

			<div v-show="Object.keys(gsimsRecords).length" class='mt-3 border p-2 bg-white'
				 style='overflow:auto;  max-height:10rem'>
				<div><i class="fa fa-info-circle"></i> Database records used:</div>
				<table>
				<tr v-for="gsimname in Object.keys(gsimsRecords)">
					<template v-if="!Object.keys(gsimsSkipped).includes(gsimname)">
						<td class='text-end pe-2'>{{ gsimname }}:</td>
						<td>{{ gsimsRecords[gsimname] }}</td>
					</template>
				</tr>
				</table>
			</div>
			<div v-show="Object.keys(gsimsSkipped).length"
				 class='mt-3 border p-2 bg-white text-danger' style='overflow:auto;max-height:10rem'>
				<div><i class="fa fa-exclamation-triangle"></i> Gsim skipped:</div>
				<table>
				<tr v-for="gsimname in Object.keys(gsimsSkipped)">
					<td class='text-end pe-2'>{{ gsimname }}:</td>
					<td>{{ gsimsSkipped[gsimname] }}</td>
				</tr>
				</table>
			</div>
		</div>
	</div>`,
	methods: {
		filtersCount(filterName){
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
		clearFilters(filterName){
			// clear the filter for the filter identified by 'filterName'
			// if 'filterName' is undefined, clears all filters (show all elements in table)
			for (var k of Object.keys(this.filterSelectedValues)){
				if (filterName === undefined || filterName === k){
					this.filterSelectedValues[k] = [];
				}
			}
		},
		sortBy(key) {
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
			// by setting a new object we trigger the template refresh => vuejs refresh
			this.columns = ret;
		},
		sortKeyAndOrder(){
			for (var colname of this.colnames){
				if (this.isSortKey(colname)){
					return [colname, this.columns[colname].sortOrder];
				}
			}
			return ["", 0];
		},
		isSortKey(colname){
			return !!((this.columns[colname] || {}).sortKey);  //!! = coerce to boolean
		},
		init(data){
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
		createFilterValues(tableData){
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
				this.filterSelectedValues[key] = [];
			}
		},
		downloadTriggered(event){
			var selectElement = event.target;
			if (selectElement.selectedIndex == 0){
				return;
			}
			var format = selectElement.value;
			var url = this.downloadUrl + '.' + format;
			var data = this.data;
			if (format == 'json'){
				var filename =  url.split('/').pop();
				this.saveAsJSON(data, filename);
			} else if (format.startsWith('csv')){
				this.download(url, data);
			}
			selectElement.selectedIndex = 0;
		}
	}
});