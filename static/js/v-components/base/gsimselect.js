/**
 * Implements a component representing the form element of GSIMs
 */
Vue.component('gsimselect', {
    //https://vuejs.org/v2/guide/components-props.html#Prop-Types:
    props: {
    	// form is an object where a name (string) is mapped to an Object representing HTML input elements (elm).
    	// Each elm is in turn an object with properties 'err' (string), 'val' (any),
    	// 'attrs' (Object of strings mapped to any value representing attributes dynamically bound to
    	// the HTML element via Vuejs), is_hidden (boolean), 'choices' (list of two element lists, for <select>s),
    	// label and help (both strings). Only 'err' and 'val' are mandatory. If you want to attach a new attribute
    	// to be bound to the element (e.g. `elm.attrs.disabled`) remember to use Vuejs $set to make the prop reactive
    	// before passing the form to this component (https://vuejs.org/v2/guide/reactivity.html#Change-Detection-Caveats)
        form: {type: Object},
    	// (optional) name of the input component. form[name] must be the Object 'elm' described above:
        name: {type: String, default: 'gsim'},
        // whether to show the "show filter" component on the bottom of the <select> main component
        showfilter: {type: Boolean, default: false},
        // if true, a button shows up and this when clicked it
        // emits a 'selection-fired' event with the list of selected GSIMs as argument:
        selectbutton: {type: String, default: ''}
    },
    data: function () {
    	var elm = this.form[this.name]; //wlm is an Object with several component properties
        return {
        	elm: elm,
            filterValue: '',
            filterType: 'GSIM name',
            filterTypes: ['GSIM name', 'IMT', 'Tectonic Region Type'],
            filterFunc: elm => true,
            // Vue.eGSIM is created in vueutil.js: it's an Object storing gsims, imts, trts,
            // and their relations via custom methods (e.g., imtsOf(gsim), trtOf(gsim), warningOf(gsim)...)
            // make it available here as `this.gsimManager`:
            gsimManager: Vue.eGSIM,
            selectableGsims: new Set(),  // updated in wathcer below
            warnings: [] //list of strings of warnings (updated also in watchers below)
        }
    },
    watch: { // https://siongui.github.io/2017/02/03/vuejs-input-change-event/
        filterValue: function(value, oldValue) {
            if (oldValue !== value){
                this.updateFilter();
            }
        },
        filterType: function(value, oldValue) {
            if (oldValue !== value){
            	var valIsStr = typeof this.filterValue === 'string';
            	if (value === this.filterTypes[0] && !valIsStr){
            		this.filterValue = '';  // calls updateFilter (see above)
            		return;
            	}else if(valIsStr){
            		this.filterValue = [];  // calls updateFilter (see above)
            		return;
            	}
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
	                var gsimManager = this.gsimManager;
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
	        	var gsimManager = this.gsimManager;
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
          <input v-if="filterType === filterTypes[0]" v-model="filterValue" type="text" class="form-control form-control-sm" style='width:initial'>
          <select v-else-if="filterType === filterTypes[1]" v-model="filterValue" multiple size='3' class="form-control form-control-sm" style='width:initial'>
          	  <option v-for='imt in gsimManager.imts' :value="imt">{{ imt }}</option>
          </select>
          <select v-else-if="filterType === filterTypes[2]" v-model="filterValue" multiple size='3' class="form-control form-control-sm" style='width:initial'>
          	  <option v-for='trt in gsimManager.trts' :value="trt">{{ trt }}</option>
          </select>
      </div>
      
      <div v-if='selectbutton' class='mt-2'>
          <button @click="$emit('selection-fired', elm.val)" v-html='selectbutton' 
           :disabled='!(elm.val || []).length' class='btn btn-primary form-control'>
          </button>
      </div>
    </div>`,
    methods: {
        isGsimVisible(gsim){
            return this.filterFunc(gsim);
        },
        updateFilter(){
            this.adjustWidth();
            var filterValue = this.filterValue;
            var filterFunc = elm => true;
            var gsimManager = this.gsimManager;
            if (this.filterType == this.filterTypes[0] && filterValue){
            	var regexp = filterValue ? 
                	new RegExp(filterValue.replace(/([^\w\*\?])/g, '\\$1').replace(/\*/g, '.*').replace(/\?/g, '.'), 'i') : 
                    	undefined;
                var filterFunc = gsimName => gsimName.search(regexp) > -1;
            }else if (this.filterType == this.filterTypes[1] && filterValue.length){
            	filterValue = new Set(filterValue);
                var filterFunc = gsimName => gsimManager.imtsOf(gsimName).some(imt => filterValue.has(imt));
            }else if (this.filterType == this.filterTypes[2] && filterValue.length){
            	filterValue = new Set(filterValue);
            	var filterFunc = gsimName => filterValue.has(gsimManager.trtOf(gsimName));
            }
            this.filterFunc = filterFunc;
        },
        adjustWidth(){
            // fixes or releases the <select> tag width before filtering,
            // as changes in the <option>s visibility cause
            // unpleasant rapid width changes, which we want to avoid
            if (!this.showfilter){
                return;
            }
            var htmElm = document.querySelector('select#id_gsim');
            if (!htmElm){
                return;
            }
            htmElm.style.width = !this.filterValue || !this.filterValue.length ? '' : htmElm.offsetWidth + 'px';
        }
    },
    mounted: function() { // https://stackoverflow.com/questions/40714319/how-to-call-a-vue-js-function-on-page-load
        // no -op
    },
    deactivated: function(){
        // no-op
    }
});