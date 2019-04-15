/**
 * Registers globally a Vue component. The name of the component
 * (first argument of 'Vue.component' below must be equal to this file's name 
 * (without extension)
 */
Vue.component('gmdbplot', {
  //https://vuejs.org/v2/guide/components-props.html#Prop-Types:
    props: {
        form: Object,
        url: String,
        response: {type: Object, default: () => {return {}}},
        post: Function
    },
    data: function () {
        return {
            responseData: this.response,
        }
    },
    watch: {
//        no-op
    },
    methods: {
        request: function(){
            var form = this.form;
            this.post(this.url, form).then(response => {
                if (response && response.data){
                    this.responseData = response.data;
                } 
            });
        }
    },
    template: `<div class='flexible d-flex flex-column'>
        <div>
            <form novalidate v-on:submit.prevent="request" class='d-flex flex-column'>
                <div class="d-flex flex-column flexible">
                    <template v-for="(data, name) in form">
                        <div class="d-flex flex-row mb-0 mt-2 pt-1 align-items-baseline">
                            <label :for="data.attrs.id" class='mb-0 text-nowrap'>
                                <input v-if="!data.choices.length && ['radio', 'checkbox'].includes(data.attrs.type)" v-model="data.val" v-bind="data.attrs" class='mr-1'>
                                {{ name }}
                            </label>
                            <div class="text-muted small flexible ml-3 text-right">
                                <span v-if="data.err" class="text-danger">{{ data.err }}</span>
                                <span v-if="!data.err && data.label.toLowerCase() != name.toLowerCase() && data.help" v-html="data.label + ' (' + data.help + ')'"></span>
                                <span v-if="!data.err && data.label.toLowerCase() != name.toLowerCase() && !data.help" v-html="data.label"></span>
                                <span v-if="!data.err && data.label.toLowerCase() == name.toLowerCase() && data.help" v-html="data.help"></span>
                            </div>
                        </div>
                        <input v-if="!data.choices.length && !['radio', 'checkbox'].includes(data.attrs.type)" v-model="data.val" v-bind="data.attrs" class='form-control'>
                        <select v-if="data.choices.length" v-model="data.val" v-bind="data.attrs" class='form-control'>
                            <option v-for='opt in data.choices' :value='opt[0]'>{{ opt[1] }}</option>
                        </select>
                    </template>
                    <button type="submit" class="btn btn-outline-primary mt-2">
                        Display magnitude-distance plot
                    </button>
                </div>
            </form>
        </div>
        <gmdbplotdiv :data="responseData" :filename="this.$options.name" class='flexible'>
        </gmdbplotdiv>
    </div>`
})