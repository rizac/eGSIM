/**
 * Implements a simple form input (or radio, or checkbox) from a given Object holding
 * the component properties and a given name
 */
Vue.component('forminput', {
    //https://vuejs.org/v2/guide/components-props.html#Prop-Types:
    props: {
        'data': {type: Object},  // an object with properties 'err', 'val', 'choices' ...
        'name': {type: String},
        'headonly': {type: Boolean, default:false}
    },
    data: function () {
        return {
            // calculate (once) data for the template below:
            isCheckOrRadio: this.data.attrs.type == 'radio' || this.data.attrs.type == 'checkbox',
            // type might be undefined, thus we need to check the choices for <select>:
            isSelect: this.data.attrs.type == 'select' || (this.data.choices && this.data.choices.length),
            nameEqualsLabel: this.data.label.toLowerCase() == this.name.toLowerCase()
        }
    },
    template: `<div>
        <div class="d-flex flex-row mb-0 pt-1 align-items-baseline">
            <label :for="data.attrs.id" class='mb-0 text-nowrap' :class="[data.attrs.disabled ? ['text-muted'] : ['']]">
                <input v-if="!headonly && isCheckOrRadio" v-model="data.val" v-bind="data.attrs" class='mr-1'>
                {{ name }}
            </label>
            <div class="text-muted small flexible ml-3 text-right">
                <span v-if="data.err" class="text-danger">{{ data.err }}</span>
                <span v-else-if="nameEqualsLabel && data.help" v-html="data.help"></span>
                <span v-else-if="data.help" v-html="data.label + ' (' + data.help + ')'"></span>
                <span v-else-if="data.label" v-html="data.label"></span>
            </div>
        </div>
        <template v-if="!headonly">
	        <select v-if="isSelect" v-model="data.val" v-bind="data.attrs" class='form-control'>
	        	<option v-for='opt in data.choices' :value='opt[0]'>
	        		{{ (opt[0] == opt[1] ? '' : '[' + opt[0] + '] ') +  opt[1] }}
	        	</option>
	    	</select>
	    	<input v-else-if="!isCheckOrRadio" v-model="data.val" v-bind="data.attrs" class='form-control'>
    	</template>
    </div>`
})