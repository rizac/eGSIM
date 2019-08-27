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
        response: {type: Object, default: () => {return {}}}
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
            Vue.post(this.url, form).then(response => {  // defined in `vueutil.js`
                if (response && response.data){
                    this.responseData = response.data;
                } 
            });
        }
    },
    template: `<div class='flexible d-flex flex-column'>
        <div class='mb-3'>
            <form novalidate @submit.prevent="request" class='d-flex flex-column'>
                <div class="d-flex flex-row flexible align-items-end">

					<!-- @helprequested below is actually redundant (not called) in all but one field -->
                    <forminput v-for="name in Object.keys(form)" :key="name" :form='form' :name='name'
                    	:showhelpbutton="name == 'selexpr'" @helprequested='$emit("movetoapidoc", "selexpr")'
                    	:class="{ 'flexible': name == 'selexpr' }" class='mr-3'>
                    </forminput>

                    <button type="submit" class="btn btn-primary mt-2">
                        Display magnitude-distance plot
                    </button>

                </div>
            </form>
        </div>
        <gmdbplotdiv :data="responseData" class='flexible' />
    </div>`
})