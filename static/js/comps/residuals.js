/**
 * Registers globally a Vue component. The name of the component
 * (first argument of 'Vue.component' below must be equal to this file's name 
 * (without extension)
 */
Vue.component('residuals', {
    //https://vuejs.org/v2/guide/components-props.html#Prop-Types:
    props: {
        form: Object,
        url: String,
        response: {type: Object, default: () => {return {}}},
        post: Function
    },
    data: function () {
        return {
            formModal: false,
            responseData: this.response,
            formHidden: false
        }
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
    watch: {
        responseData: {
            immediate: true, // https://forum.vuejs.org/t/watchers-not-triggered-on-initialization/12475
            handler: function(newval, oldval){
                var empty = Vue.isEmpty(newval); // defined in vueutil.js
                this.formModal = !empty;
                this.formHidden = !empty;
            }
        }
    },
    template: `
<div class='flexible d-flex flex-column'>

    <form novalidate v-on:submit.prevent="request" v-show="!formHidden"
        :class="[formModal ? ['shadow', 'border', 'bg-light', 'pt-2', 'mb-3'] : 'pt-4']"
        class='d-flex flex-column px-4 pb-4 flexible align-self-center position-relative' style='z-index:10'>

        <div v-show='formModal' class='text-right'>
            <button type="button" v-on:click='formHidden=true' class="close" aria-label="Close">
                <span aria-hidden="true">&times;</span>
            </button>
        </div>
        
        <div class="d-flex flex-column flexible">
            <div class="d-flex flexible flex-row mb-4">

                <div class="d-flex flexible flex-column">
                    <gsimselect :form="form" showfilter class="flexible mb-4"></gsimselect>
                    <imtselect :form="form"></imtselect>
                </div>
                
                <div class="d-flex flex-column flexible ml-4">
                    <h5>Database</h5>
                    <div class="flexible form-control mb-4" style="background-color:transparent">
        
                        <forminput v-for="(data, name) in form"
                            :data='data' :name='name' :key="name"
                            v-if="!['gsim', 'imt', 'sa_periods', 'plot_type'].includes(name)"
                            class='mt-2'>
                        </forminput>

                    </div>

                    <template v-for="name in ['plot_type']">
                        <div class="d-flex flex-column">
                            <div class='d-flex flex-row align-items-baseline'>
                                <h5>{{ name }}</h5>
                                <span class="text-danger small flexible ml-3 text-right">{{ form[name].err }}</span>
                            </div>

                            <select v-model="form[name].val" v-bind="form[name].attrs" size="6"
                             class='form-control'>
                                <option v-for='opt in form[name].choices' :value="opt[0]">
                                    {{ '[' + opt[0] + '] ' + opt[1] }}
                                </option>
                            </select>
                        </div>
                    </template>
                </div>
            </div>

            <button type="submit" class="btn btn-outline-primary">
                Display plots
            </button>

        </div>

    </form>

    <residualsplotdiv :data="responseData" :filename="this.$options.name"
        class='position-absolute pos-0 m-0' style='z-index:1'>
        <slot>
            <button @click='formHidden=false' class='btn btn-sm btn-outline-primary mb-1'><i class='fa fa-wpforms'></i> params</button>
        </slot>
    </residualsplotdiv>
</div>`
})