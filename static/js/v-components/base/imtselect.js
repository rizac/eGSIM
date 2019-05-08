/**
 * Implements a component representing the form element of IMTs and SA periods
 */
Vue.component('imtselect', {
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
        name: {type: String, default: 'imt'},
        // (optional) name of the SA periods input component. form[saPeriodName] must be an Object
        // of the same type of 'elm' described above:
        saPeriodName: {type: String, default: 'sa_period'},
        
    },
    data: function () {
    	return {
        	// define the Object whose data is associated to this component:
            elm: this.form[this.name],
            // define the Object whose data is associated to the selected gsims:
            gsimData: this.form.gsim,
            // define the Set of the selectable IMTs (see watchers below):
            selectableImts: new Set()
        }
    },
    created: function(){
    	// no-op
    },
    watch: { // https://siongui.github.io/2017/02/03/vuejs-input-change-event/
    	// watch for properties that should update this.selectableImts:
    	'gsimData.gsimManager': function(newVal, oldVal){
    		// watch for changes in gsimManager, which is an Object defined in egsim_base.js
    		// ('created' function) holding information of each gsim's imt and trt.
    		// In principle, it's static, but watch for changes of it
    		this.computeSelectableImts();
    	},
    	'gsimData.val': function(newVal, oldVal){
    		// watch for changes in selected gsims
    		this.computeSelectableImts();
    	},
    	'elm.attrs.disabled': function(newVal, oldVal){
    		// watch for changes in disabled state of the imt
    		this.updateSaPeriodsEnabledState();
    	},
    	'elm.val': {
    		// watch for changes in selected imts. Immediate=true: call handler immediately
    		immediate: true,
    		handler: function(newVal, oldVal){
    			this.computeSelectableImts();
    			this.updateSaPeriodsEnabledState();
    		}
    	}
    },
    computed: {
        // no-op 
    },
    // note on imts <option>s in template below: do not disable unselectable imts, as the user might not
    // be able to deselect them if gsims are changed. Just style them gray and use strike-through
    template: `<div class='d-flex flex-column'>
        <forminput :form="form" :name='name' headonly></forminput>
        <div class='mb-1 flexible d-flex flex-column'>
          <select
          		v-model="elm.val"
          		v-bind="elm.attrs"
          		:class="{'border-danger': !!elm.err}"
          		class="form-control flexible"
          >
              <option
              		v-for='imt in elm.choices'
              		:key='imt'
              		:style="!selectableImts.has(imt) ? {'text-decoration': 'line-through'} : ''"
                  	:class="{'disabled': !selectableImts.has(imt)}"
              >
                  {{ imt }}
              </option>
          </select>
        </div>
        <!-- Instead of this: <forminput :form="form" :name='saPeriodName'></forminput> 
        we render for the sa periods a little bit differently: -->
        <div class='d-flex flex-row align-items-baseline'>
        	<label
        		:disabled="!selectableImts.has('SA') || form[saPeriodName].attrs.disabled"
        		:for='form[saPeriodName].attrs.id'
        		class='mr-1 text-nowrap small'
        	>
        		{{ form[saPeriodName].label }}
        	</label>
            <input
            	:name='saPeriodName' 
            	type='text'
            	v-model="form[saPeriodName].val"
            	v-bind="form[saPeriodName].attrs" 
            	:class = "{'disabled': !selectableImts.has('SA')}"
            	class="form-control form-control-sm"
            >
        </div>
    </div>`,
    methods: {
        // no-op
        updateSaPeriodsEnabledState: function(){
        	// The sa_period <input> will be set disabled in case the imt <input> has been explicitly
        	// set disabled, or SA is not selected. Note that a disabled input does not send its
        	// value to the server (see egsim-base.js). Previously, we disabled the sa_period <input>
        	// also when the SA was not in the selectable imts (i.e., not all selected gsim are defined for SA),
        	// but this would lead to a misleading 'SA must be specified with periods' error message,
        	// even when SA is selected and sa_periods is provided, if sa_period <input> was disabled.
        	// Thus we just add the class 'disabled' (see template above) if SA is not in the selectable
        	// imts, obtaining the same visual effect (see css) but avoiding misleading errors
        	var disabled = !!this.elm.attrs.disabled || !this.elm.val.includes('SA');
        	this.form[this.saPeriodName].attrs.disabled = disabled;
        },
        computeSelectableImts: function(){
        	var gsimManager = this.gsimData.gsimManager;  
            var selectedgsims = this.gsimData.val || [];
            var selectableImts = [];
            for (var gsim of selectedgsims){
            	if (!selectableImts.length){ // first gsim element
            		selectableImts = Array.from(gsimManager.imtsOf(gsim));  // make a copy
            	}else{
            		for (var i=selectableImts.length-1; i>=0; i--){
            			if (!gsimManager.imtsOf(gsim).includes(selectableImts[i])){
            				selectableImts.splice(i, 1);
            			}
            		}
            	}
            	if (!selectableImts.length){
            		break;
            	}
            }
            this.selectableImts = new Set(selectableImts);
            // we do not need to call this method anymore, as the disabled state of sa_periods
            // does not depend on the selectableImts (we provide the class 'disabled', see template)
            // this.updateSaPeriodsEnabledState();
        }
    }
})