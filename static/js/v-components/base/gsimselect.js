Vue.component('gsimselect', {
    //https://vuejs.org/v2/guide/components-props.html#Prop-Types:
    props: {
        name: {type: String, default: 'gsim'},
        showfilter: {type: Boolean, default: false},
        form: Object,
        selectbutton: {type: String, default: ''}
    },
    data: function () {
    	var elm = this.form[this.name]; //wlm is an Object with several component properties
        return {
        	elm: elm,
            filterText: '',
            filterType: 'GSIM name',
            filterTypes: ['GSIM name', 'IMT', 'Tectonic Region Type'],
            filterFunc: elm => true,
            gsimManager: elm.gsimManager,  // Object defined in egsim_base.js ('created' function),
            selectableGsims: new Set(),  // updated in wathcer below
            warnings: [] //list of strings of warnings (updated also in watchers below)
        }
    },
    watch: { // https://siongui.github.io/2017/02/03/vuejs-input-change-event/
        filterText: function(value, oldValue) {
            if (oldValue !== value){
                this.updateFilter();
            }
        },
        filterType: function(value, oldValue) {
            if (oldValue !== value){
                this.updateFilter();
            }
        },
        // listen for changes in the selected imts:
        'form.imt.val': {  // even if it should not happen: if we change the imt param name, change it also here ...
        	immediate: true,
        	handler: function(newVal, oldVal){
        		var selectableGsims = this.elm.choices;
	            var selectedimts = newVal;
	            if (selectedimts.length){
	                var gsimManager = this.gsimManager;  // Object defined in egsim_base.js ('created' function)
	            	selectableGsims = selectableGsims.filter(gsim => {
	                	return selectedimts.every(imt => gsimManager.imtsOf(gsim).includes(imt));
	                });
	            }
	            this.selectableGsims = new Set(selectableGsims);
        	}
        },
        // listen for changes in gsim selection
        'elm.val': {
        	immediate: true,
        	handler: function(newVal, oldVal){
	        	var gsimManager = this.gsimManager;  // Object defined in egsim_base.js ('created' function)
        		this.warnings = (newVal || []).filter(gsim => gsimManager.warningOf(gsim)).map(gsim => gsimManager.warningOf(gsim));
        		if (this.warnings.length && newVal && newVal.length && this.$refs.select){
        			// scroll last element into view because we might hide it (see template)
        			// (https://vuejs.org/v2/guide/components-edge-cases.html#Accessing-Child-Component-Instances-amp-Child-Elements)
        			var elm = Array.from(this.$refs.select.options).filter(opt => opt.value === newVal[newVal.length-1]);
        			if (elm && elm.length == 1){
        				this.$nextTick(() => {
        					var [r1, r2] = [elm[0].parentElement.getBoundingClientRect(),
				        					elm[0].getBoundingClientRect()];
				        	if (r2.y >= r1.height + r1.y){
			                	elm[0].scrollIntoView(false);
			                }
			            });
        			}
        		}
        	}
        }
    },
    computed: {
        // computed properties are cached, i.e. they are re-evaluated only each time
        // the watched variable used therein are changed.
        // https://vuejs.org/v2/guide/computed.html
        // https://forum.vuejs.org/t/how-do-computed-properties-know-how-to-change/24140/2
        // no-op for the moment
    },
    template: `<div class='d-flex flex-column'>
      <forminput :form="form" :name='name' headonly></forminput>
      <div class='flexible d-flex flex-column'>
          <select v-model="elm.val" v-bind="elm.attrs" ref="select"
          v-bind:class="{'rounded-bottom-0': warnings.length, 'border-danger': !!elm.err}"
          class="form-control flexible with-icons">
              <option v-for="gsim in elm.choices" :value="gsim" :key="gsim" v-show="isGsimVisible(gsim)"
               v-bind:style="!selectableGsims.has(gsim) ? {'text-decoration': 'line-through'} : ''"
               v-bind:class="{'disabled': !selectableGsims.has(gsim)}">
                  {{ gsim }} {{ gsimManager.warningOf(gsim) ? '&#xf071;' : '' }} 
              </option>
          </select>
          <div v-show='warnings.length' class='form-control position-relative border-top-0 rounded-top-0'
          		style='height:4rem;overflow:auto'>
          			
          	  <div class='small position-absolute pos-x-0 pos-y-0 p-1'>
          	  	  <div>{{ warnings.length }} warning(s):</div>
          	      <div v-for='warn in warnings'>
          		      <span class='text-warning'><i class="fa fa-exclamation-triangle"></i></span> {{ warn }}
          		  </div>
          	  </div>
          </div>
      </div>
    
      <!-- GSIM FILTER CONTROLS: -->
      <div class="d-flex flex-row mt-1" v-if='showfilter'>  
          <select v-model="filterType" class="form-control form-control-sm" style='border:0px; background-color:transparent'>
              <option v-for="item in filterTypes" :key="item" v-bind:value="item">
                      Filter by {{ item }}:
              </option>
          </select>
          <input v-model="filterText" type="text" class="form-control form-control-sm" style='width:initial'>
      </div>
      
      <div v-if='selectbutton' class='mt-2'>
          <button @click="$emit('selection-fired', elm.val)" v-html='selectbutton' 
           :disabled='!(elm.val || []).length' class='btn btn-outline-primary form-control'>
          </button>
      </div>
    </div>`,
    methods: {
        isGsimVisible(gsim){
            return this.filterFunc(gsim);
        },
        updateFilter(){
            this.adjustWidth();
            var regexp = this.filterText ? 
                new RegExp(this.filterText.replace(/([^\w\*\?])/g, '\\$1').replace(/\*/g, '.*').replace(/\?/g, '.'), 'i') : 
                    undefined;
            var filterFunc = elm => true;
            var gsimManager = this.gsimManager;  // Object defined in egsim_base.js ('created' function)
            if (this.filterType == this.filterTypes[0]){
                var filterFunc = gsimName => gsimName.search(regexp) > -1;
            }else if (this.filterType == this.filterTypes[1]){
                var filterFunc = gsimName => gsimManager.imtsOf(gsimName).some(imt => imt.search(regexp) > -1);
            }else if (this.filterType == this.filterTypes[2]){
            	var filterFunc = gsimName => gsimManager.trtOf(gsimName).search(regexp) > -1;
            }
            this.filterFunc = filterFunc;
        },
        adjustWidth(){
            // fixes or releases the <select> tag width before filtering
            // to avoid upleasant rapid width changes
            if (!this.showfilter){
                return;
            }
            var htmElm = document.querySelector('select#id_gsim');
            if (!htmElm){
                return;
            }
            htmElm.style.width = !this.filterText ? '' : htmElm.offsetWidth + 'px';
        }
    },
    mounted: function() { // https://stackoverflow.com/questions/40714319/how-to-call-a-vue-js-function-on-page-load
        // no -op
    },
    deactivated: function(){
        // no-op
    }
});