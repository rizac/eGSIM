/**
 * Implements a simple form input (or radio, or checkbox) from a given Object holding
 * the component properties and a given name
 */
Vue.component('forminput', {
    //https://vuejs.org/v2/guide/components-props.html#Prop-Types:
    props: {
        'data': {type: Object},  // an object with properties 'err', 'val', 'choices' ...
        'name': {type: String}
    },
    data: function () {
        return {
            // no-op for the moment
        }
    },
    template: `<div>
        <div class="d-flex flex-row mb-0 pt-1 align-items-baseline">
            <label :for="data.attrs.id" class='mb-0 text-nowrap'
            :class="[data.disabled ? ['text-muted'] : ['']]">
                <input v-if="!data.choices.length && ['radio', 'checkbox'].includes(data.attrs.type)"
                    v-model="data.val" v-bind="data.attrs" :disabled="data.disabled" class='mr-1'>
                {{ name }}
            </label>
            <div class="text-muted small flexible ml-3 text-right">
                <span v-if="data.err" class="text-danger">{{ data.err }}</span>
                <span v-if="!data.err && data.label.toLowerCase() != name.toLowerCase() && data.help"
                    v-html="data.label + ' (' + data.help + ')'"></span>
                <span v-if="!data.err && data.label.toLowerCase() != name.toLowerCase() && !data.help"
                    v-html="data.label"></span>
                <span v-if="!data.err && data.label.toLowerCase() == name.toLowerCase() && data.help"
                    v-html="data.help"></span>
            </div>
        </div>
        <input v-if="!data.choices.length && !['radio', 'checkbox'].includes(data.attrs.type)"
            v-model="data.val" v-bind="data.attrs" :disabled="data.disabled" class='form-control'>
        <select v-if="data.choices.length" v-model="data.val" v-bind="data.attrs" :disabled="data.disabled"
            class='form-control'>
            <option v-for='opt in data.choices' :value='opt[0]'>{{ opt[1] }}</option>
        </select>
    </div>`
})