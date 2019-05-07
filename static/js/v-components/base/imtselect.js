Vue.component('imtselect', {
    //https://vuejs.org/v2/guide/components-props.html#Prop-Types:
    props: {
        'name': {type: String, default: 'imt'},
        'saPeriodName': {type: String, default: 'sa_period'},
        'form': Object
    },
    data: function () {
    	// initialize here some properties. Note that it seems this is called before the template
    	// rendering which is called before created, which is called before mounting:
    	this.$set(this.form[this.saPeriodName].attrs, 'disabled', false);
    	// HACK! FIXME: this should be modified server side:
    	this.form[this.saPeriodName].help = '';
        return {
            elm: this.form[this.name], // elm just to type 'this.elm' instead of 'this.form[this.name]'
            // throughout this component:
            // elm is an Object with properties. E.g., elm.attrs (Object to be bound to the html element attrs via v-bind),
            // elm.val (any js value to be bound to the Vue element model), and so on ...
            gsimData: this.form.gsim,  // an Object with the related gsim data (gsimData.val = list of selected gsims, etcetera)
            selectableImts: new Set() // will be updated in watchers, see below
        }
    },
    created: function(){
    	if ('disabled' in this.elm.attrs){
    		// add a further watcher for this.elm.attrs.disabled (refresh saPeriods enabled state):
    		this.$watch('elm.attrs.disabled', function(newVal, oldVal){
    			this.updateSaPeriodsEnabledState();
    		}, {immediate: true});
    	}
    },
    watch: { // https://siongui.github.io/2017/02/03/vuejs-input-change-event/
    	'gsimData.gsimManager': function(newVal, oldVal){
    		// gsimForm.gsimManager is an Object defined in egsim_base.js ('created' function)
    		// in principle, it's static, but watch for changes of it
    		this.computeSelectableImts();
    	},
    	'gsimData.val': function(newVal, oldVal){
    		// watch for changes in selected gsims
    		this.computeSelectableImts();
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
        <div class='mb-1 flexible d-flex flex-column'>
          <select v-model="elm.val" v-bind="elm.attrs" class="form-control flexible" :class="{'border-danger': !!elm.err}">
              <option v-for='imt in elm.choices' :key='imt'
                  v-bind:style="!selectableImts.has(imt) ? {'text-decoration': 'line-through'} : ''"
                  v-bind:class="!selectableImts.has(imt) ? ['disabled'] : ''">
                  {{ imt }}
              </option>
          </select>
        </div>
        <forminput :form="form" :name='saPeriodName'></forminput> 
        <!-- <div>  
            <input type='text' v-model="form[saPeriodName].val" :name='saPeriodName' 
            	v-bind="form[saPeriodName].attrs" class="form-control" >
        </div>-->
    </div>`,
    methods: {
        // no-op
        updateSaPeriodsEnabledState: function(){
        	var selectableImts = this.selectableImts;
        	var disabled = !!this.elm.attrs.disabled || !selectableImts.has('SA') || !this.elm.val.includes('SA');
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
            this.updateSaPeriodsEnabledState();
        }
    }
})