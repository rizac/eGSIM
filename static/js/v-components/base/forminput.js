/**
 * Implements a simple form input (or radio, or checkbox) from a given Object holding
 * the component properties and a given name
 */
Vue.component('forminput', {
    //https://vuejs.org/v2/guide/components-props.html#Prop-Types:
    props: {
    	// form is an object with names (string) mapped to elements (elm).
    	// Each elm represents the input or select type and it's in turn an object
    	// with properties 'err', 'val', 'choices' ...
        'form': {type: Object},  
        'name': {type: String},
        'headonly': {type: Boolean, default:false} // if true, display only header (name and infos)
    },
    data: function () {
    	var elm = this.form[this.name];
    	var isSelect = elm.attrs.type == 'select' || (elm.choices && elm.choices.length);
    	// build label text according to the label and help attribute:
    	var nameEqualsLabel = (elm.label || "").replace(/ /g, "_").toLowerCase() == this.name.replace(/ /g, "_").toLowerCase();
    	var labelText = nameEqualsLabel ? (elm.help || "") : (elm.help ? elm.label + ' (' + elm.help + ')' : (elm.label || ""));
        var isSelectMultiple = isSelect && elm.attrs.multiple;
        if (labelText && isSelectMultiple){
        	labelText += ": ";
        }
        return {
        	elm: elm,
            // calculate (once) data for the template below:
            isCheckOrRadio: elm.attrs.type == 'radio' || elm.attrs.type == 'checkbox',
            // type might be undefined, thus we need to check the choices for <select>:
            isSelect: isSelect,
            isSelectMultiple: isSelectMultiple,
            labelText: labelText
        }
    },
    template: `<div v-if="!elm.is_hidden">
        <div class="d-flex flex-row mb-0 pt-1 align-items-baseline">
            <label :for="elm.attrs.id" class='mb-0 text-nowrap' :class="[elm.attrs.disabled ? ['text-muted'] : ['']]">
                <input v-if="!headonly && isCheckOrRadio" v-model="elm.val" v-bind="elm.attrs" class='mr-1'>
                {{ name }}
            </label>
            <div class="text-muted small flexible ml-3 text-right">
                <span v-if="elm.err" class="text-danger">{{ elm.err }}</span>
                <template v-else-if="labelText || isSelectMultiple">
                	<span v-if="labelText" v-html="labelText"></span>
                	<span v-if="isSelectMultiple">{{ elm.val.length || 0 }} of {{ elm.choices.length }} selected</span>
                </template>
            </div>
        </div>
        <template v-if="!headonly">
	        <select v-if="isSelect" v-model="elm.val" v-bind="elm.attrs" class='form-control'>
	        	<option v-for='opt in elm.choices' :value='opt[0]'>
	        		{{ (opt[0] == opt[1] ? '' : '[' + opt[0] + '] ') +  opt[1] }}
	        	</option>
	    	</select>
	    	<input v-else-if="!isCheckOrRadio" v-model="elm.val" v-bind="elm.attrs" class='form-control'>
    	</template>
    </div>`
})