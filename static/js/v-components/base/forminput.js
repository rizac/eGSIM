/**
 * Implements a component representing a form element (<input>, <select>)
 */
Vue.component('forminput', {
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
        // if true, display header only (name and infos) and not input element
        headonly: {type: Boolean, default:false},
        // if true, help button shows up in the header  and this component
        // emits an 'helprequested' event with no arguments (for the moment):
        showhelpbutton: {type: Boolean, default:false}
    },
    data: function () {
    	// define the Object whose data is associated to this component:
    	var elm = this.form[this.name];
    	return {
        	elm: elm,
            // calculate (once) data for the template below:
            isRadio: elm.attrs.type == 'radio',
            isCheck: elm.attrs.type == 'checkbox',
            // The <select> type might be undefined, this makes us know is we are dealing with a <select>:
            isSelect: elm.attrs.type == 'select' || (!elm.attrs.type && elm.choices && elm.choices.length)
        }
    },
    computed: {
    	info: function(){
    		// returns the string to be displayed next to the element label which might be

    		var elm = this.form[this.name];
    		// if the element value has error, the info is the error, thus return it:
    		if (elm.err){
    			return elm.err;
    		}
    		// return the element html help
    		var info = elm.help || '';
    		if (this.isSelect && elm.attrs.multiple){
    			// if the element is a <select multiple...>, display also the selected
    			// elements. Note that being this a computed property, Vue will collect all
    			// variables referenced here (e.g., `elm.val`, `elm.choices`, see below):
    			// when any of them will change, Vue will re-render the HTML by calling this property
    			var selected = `(${elm.val.length || 0} of ${elm.choices.length} selected)`;
    			return info ? `${info} ${selected}` : selected;
    		}
    		return info;
    	}
    },
    template: `<div v-if="!elm.is_hidden">
        <div class="d-flex flex-row mb-0" :class="[showhelpbutton ? ['align-items-end'] : ['align-items-baseline']]">
            <label :for="elm.attrs.id" class='mb-0 text-nowrap' :disabled='elm.attrs.disabled'
            	:class="{'checked': elm.val, 'customcheckbox': isCheck, 'customradio': isRadio}"
            >
                <input v-if="!headonly && (isCheck || isRadio)" v-model="elm.val" v-bind="elm.attrs" class='mr-1'>
                <span v-html="elm.label"></span>
            </label>
            <span
            	v-html="info"
            	:class="[elm.err ? 'text-danger' : 'text-muted']"
            	class="small flexible ml-2"
            >
            </span>
            <span class='text-primary small ml-3 text-right'>{{ name }}</span>
            <button v-if="showhelpbutton" type="button" @click='$emit("helprequested")'
    		 		class='btn btn-outline-secondary btn-sm ml-1 mb-1 py-0'>
    			<i class="fa fa-question"></i>
    		</button>
        </div>
        <template v-if="!headonly">
	        <select
	        	v-if="isSelect"
	        	v-model="elm.val"
	        	v-bind="elm.attrs"
	        	class='form-control'
	        	:class="{'border-danger': !!elm.err}"
	        >
	        	<option
	        		v-for='opt in elm.choices'
	        		:value='opt[0]'
	        		v-html='getOptionLabel(opt)'>
	        	</option>
	    	</select>
	    	<input v-else-if="!isCheck && !isRadio" v-model="elm.val" v-bind="elm.attrs" class='form-control'
	    		:class="{'border-danger': !!elm.err}">
    	</template>
    </div>`,
    methods: {
    	getOptionLabel: function(opt){
    		return opt[1] + (opt[0] == opt[1] ? '' : '&nbsp;&nbsp;[' + opt[0] + '] ')
    	}
    }
})