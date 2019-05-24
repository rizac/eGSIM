/**
 * Implements a component for visualizing text-formatted data (e.g., json, yaml)
 */
Vue.component('downloadselect', {
    //https://vuejs.org/v2/guide/components-props.html#Prop-Types:
    props: {
        keys: {default: () => []}
    },
    data: function () {
    	var emptyValue = '';
    	while(this.keys.includes(emptyValue)){
    		emptyValue += ' ';
    	}
    	return {
    	    emptyValue: emptyValue,
    		selKey: emptyValue
        }
    },
    created: function(){
    	// create an empty value and insert it at index 0:
    	
    },
    watch: {
    	'selKey': function (newVal, oldVal){
            // we do not attach onchange on the <select> tag because of this: https://github.com/vuejs/vue/issues/293
            var idx = this.keys.indexOf(newVal);
            if(idx > -1){
            	this.$emit('selected', newVal, idx, this.keys.slice());   
            }
            this.selKey = this.emptyValue;
        }
    },
    computed: {
    	// no-op
    },
    template: `<div class='d-flex flex-row text-nowrap align-items-baseline'>
		<i class="fa fa-download"></i>
		<select
			v-model='selKey'
			class='form-control ml-2'
		>	
		    <option
                :value='emptyValue'
                :disabled="true"
            >
                <slot></slot>
            </option>
            <option
            	v-for='(key, index) in keys'
            	:value='key'
            >
            	{{ key }}
            </option>
        </select>
    </div>`,
    methods: {
    	// no-op
    	download: function(){
    		
    	}
    }
})