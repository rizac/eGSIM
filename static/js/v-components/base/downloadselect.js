/**
 * Implements a component for downloading Object as JSON or text-formatted data
 */
Vue.component('downloadselect', {
    //https://vuejs.org/v2/guide/components-props.html#Prop-Types:
    props: {
    	// model can be:
    	// 1. Object: then its {label1: callback1, .. labelN: callbackN}
    	// 2. Map. Same as above (keys are labels, values are callbacks)
    	// 3. Array [[label1, callback1], ... , [labelN, callbackN]]
    	// 4. Array [label1, ... labelN]
    	// callback needs to be a function with no arguments.
    	// You can always listen for the selected event,
    	// e.g.:
    	// <downloadselect ... @selected='somecallback(labelSelected)' ...>
    	// (in case 4., it's probably mandatory unless you want a no-op component)
        model: {default: () => []}
    },
    data: function () {
    	// parse the given model, create an Array of labels and an Object of callbacks
    	var [labels, callbacks, model] = [[], {}, this.model];
    	if (model instanceof Map){
    		for (var [label, callback] of model) {
    			labels.push(label);
    			callbacks[label] = callback;
    		}
    	}else if(Array.isArray(model)){
    		for (var item of model){
    			if (Array.isArray(item)){
    				labels.push(item[0]);
    				callbacks[item[0]] = item[1];
    			}else{
    				labels.push(item);
    				callbacks[item] = () => {};  // no-op function
    			}
    		}
    	}else{
    		labels = Object.keys(model);
    		callbacks = model;
    	}
    	// create an empty value (associated with the first <select> item which
    	// is "disabled" and acts as a title for the component)
    	var emptyValue = '';
    	while(labels.includes(emptyValue)){
    		emptyValue += ' ';
    	}
    	return {
    	    emptyValue: emptyValue,
    		selKey: emptyValue,
    		labels: labels,
    		callbacks: callbacks
        }
    },
    created: function(){
    	// create an empty value and insert it at index 0:
    	
    },
    watch: {
    	'selKey': function (newVal, oldVal){
            // we do not attach onchange on the <select> tag because of this: https://github.com/vuejs/vue/issues/293
            var idx = this.labels.indexOf(newVal);
            if(idx > -1){
            	this.callbacks[newVal]();
            	this.$emit('selected', newVal);   
            }
            this.selKey = this.emptyValue;
        }
    },
    computed: {
    	// no-op
    },
    template: `<div v-if='labels.length' class='d-flex flex-row text-nowrap align-items-baseline'>
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
            	v-for='label in labels'
            	:value='label'
            >
            	{{ label }}
            </option>
        </select>
    </div>`,
    methods: {
    	// no-op
    	download: function(){
    		
    	}
    }
})