Vue.component('imtselect', {
    //https://vuejs.org/v2/guide/components-props.html#Prop-Types:
    props: {
        'name': {type: String, default: 'imt'},
        'gsimName': {type: String, default: 'gsim'},
        'saPeriodsName': {type: String, default: 'sa_period'},
        'form': Object
    },
    data: function () {
        return {
            elm: this.form[this.name]
            // this is just to type 'this.elm' instead of 'this.form[this.name]' throughout this component
            // elm is an Object with properties. E.g., elm.attrs (Object to be bound to the html element attrs via v-bind),
            // elm.val (any js value to be bound to the Vue element model), and so on ...
        }
    },
    created: function(){
    	this.$set(this.form[this.saPeriodsName].attrs, 'placeholder', this.form[this.saPeriodsName].label);
    },
    watch: { // https://siongui.github.io/2017/02/03/vuejs-input-change-event/
    },
    computed: {
        // computed properties are cached, i.e. they are re-evaluated only each time
        // the watched variable used therein are changed.
        // https://vuejs.org/v2/guide/computed.html
        // https://forum.vuejs.org/t/how-do-computed-properties-know-how-to-change/24140/2
        // Here we use it instead because it's more readable than two watchers
        // Also, here we set the enabled / disabled state of the Sa periods
        selectableImts: function(){
        	var gsimManager = this.form[this.gsimName].gsimManager;  // Object defined in egsim_base.js ('created' function)
            var selectedgsims = this.form[this.gsimName].val || [];
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
            selectableImts = new Set(selectableImts);
            // set the disabled state. Note also that here we: access this.elm.val to make this computed prop reactive
            this.$set(this.form[this.saPeriodsName].attrs, 'disabled', !selectableImts.has('SA') || !this.elm.val.includes('SA'));
            // return object:
            return selectableImts;
        }
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
        <div>  
            <input type='text' v-model="form[saPeriodsName].val" :name='saPeriodsName' 
            	v-bind="form[saPeriodsName].attrs" class="form-control" >
        </div>
    </div>`,
    methods: {
        // no-op
    }
})