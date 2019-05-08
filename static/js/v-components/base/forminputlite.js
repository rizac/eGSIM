/**
 * Implements a component representing a form element (<input>, <select>).
 * Similar to <forminput>, but it is smaller and packed with less details
 */
Vue.component('forminputlite', {
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
        // the name of the input component. form[name] must be the Object 'elm' described above
        name: {type: String},
    },
    data: function () {
    	// define the Object whose data is associated to this component:
    	var elm = this.form[this.name];
    	var isSelect = elm.attrs.type == 'select' || (elm.choices && elm.choices.length);
        return {
        	elm: elm,
            // calculate (once) data for the template below:
            isCheckOrRadio: elm.attrs.type == 'radio' || elm.attrs.type == 'checkbox',
            // type might be undefined, thus we need to check the choices for <select>:
            isSelect: isSelect,
            isSelectMultiple: isSelect && elm.attrs.multiple
        }
    },
    template: `<div v-if="!elm.is_hidden"
		class="d-flex flex-row mb-0"
		:class="[isSelectMultiple ? ['align-items-start'] : ['align-items-baseline']]"
		>
            <label
            	:for="elm.attrs.id"
            	class='mb-0 text-nowrap small'
            	:class="[elm.attrs.disabled ? ['text-muted'] : ['font-weight-bold']]"
            >
                <input v-if="isCheckOrRadio" v-model="elm.val" v-bind="elm.attrs" class='mr-1'>
                <span v-html="elm.label"></span>
            </label>
	        <select
	        	v-if="isSelect"
	        	v-model="elm.val"
	        	v-bind="elm.attrs"
	        	class='form-control form-control-sm ml-1'
	        	:class="{'border-danger': !!elm.err}"
	        >
	        	<option
	        		v-for='opt in elm.choices'
	        		:value='opt[0]'
	        		v-html='getOptionLabel(opt)'>
	        	</option>
	    	</select>
	    	<input
	    		v-else-if="!isCheckOrRadio"
	    		v-model="elm.val"
	    		v-bind="elm.attrs"
	    		class='form-control form-control-sm ml-1'
	    		:class="{'border-danger': !!elm.err}">
	    </div>`,
    methods: {
    	getOptionLabel: function(opt){
    		return opt[1] + (opt[0] == opt[1] ? '' : '&nbsp;&nbsp;[' + opt[0] + '] ')
    	}
    }
})