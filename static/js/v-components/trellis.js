/**
 * Registers globally a Vue component. The name of the component
 * (first argument of 'Vue.component' below must be equal to this file's name 
 * (without extension)
 */
Vue.component('trellis', {
    //https://vuejs.org/v2/guide/components-props.html#Prop-Types:
    props: {
        form: Object,
        url: String,
        response: {type: Object, default: () => {return {}}},
        post: Function
    },
    data: function () {
    	// set the size of the plot_type <select>. Maybe this is not the right place
    	// (maybe the 'created' method would be better:
    	// https://vuejs.org/v2/api/#created) but it works:
    	this.$set(this.form['plot_type'].attrs, 'size', 3);
        return {
            formModal: false,
            responseData: this.response,
            formHidden: false,
            scenarioKeys: Object.keys(this.form).filter(key => key!='gsim' && key!='imt' & key!='sa_periods' & key!='plot_type')
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

                    <div class="flexible form-control mb-4" style="background-color:transparent">
                        <forminput v-for="(name, index) in scenarioKeys"
                            :form='form' :name='name' :key="name"
                            :class="{ 'mt-2': index > 0 }">
                        </forminput>
                    </div>

                    <div class="form-control" style="background-color:transparent">
                        <forminput :form='form' :name='"plot_type"'></forminput>
                    </div>

                </div>
            </div>
        
            <button type="submit" class="btn btn-outline-primary">
                Display plots
            </button>
        
        </div>
        
    </form>

    <trellisplotdiv :data="responseData" :filename="this.$options.name"
        class='position-absolute pos-0 m-0' style='z-index:1'>
        <slot>
            <button @click='formHidden=false' class='btn btn-sm btn-outline-primary mb-1'><i class='fa fa-wpforms'></i> params</button>
        </slot>
    </trellisplotdiv>
</div>`
})