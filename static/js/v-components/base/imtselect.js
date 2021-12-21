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
            gsimField: this.form.gsim,
            // define the Set of the selectable IMTs (see watchers below):
            selectableImts: new Set(),
            // Vue.eGSIM is created in vueutil.js: it's an Object storing gsims, imts,
            // and their relations via custom methods (e.g., imtsOf(gsim), warningOf(gsim)...)
            // make it available here as `this.gsimManager`:
            gsimManager: Vue.eGSIM
        }
    },
    created: function(){
    	// no-op
    },
    watch: { // https://siongui.github.io/2017/02/03/vuejs-input-change-event/
    	'gsimField.val': function(newVal, oldVal){
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
        <div class='flexible d-flex flex-column'>
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
        <input type=text v-model=
        <forminputlite :form="form" :name='saPeriodName' class='mt-1'></forminputlite>
    </div>`,
    methods: {
        // no-op
        updateSaPeriodsEnabledState: function(){
        	var disabled = !!this.elm.attrs.disabled || !this.selectableImts.has('SA');
        	this.form[this.saPeriodName].attrs.disabled = disabled;
        	this.form[this.saPeriodName].is_hidden = !this.elm.val.includes('SA');
        },
        computeSelectableImts: function(){
        	var gsimManager = this.gsimManager;  
            var selectedgsims = this.gsimField.val || [];
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
            this.updateSaPeriodsEnabledState();
        }
    }
})