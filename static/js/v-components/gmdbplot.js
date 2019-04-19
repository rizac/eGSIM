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

                    <forminput v-for="name in Object.keys(form)" :key="name" :form='form' :name='name'>
                    </forminput>

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