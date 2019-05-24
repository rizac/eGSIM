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
    	// set the size of the plot_type <select>. Maybe this is not the right place
    	// (maybe the 'created' method would be better:
    	// https://vuejs.org/v2/api/#created) but it works:
    	this.$set(this.form['plot_type'].attrs, 'size', 10);
        return {
            responseDataEmpty: true,
            formHidden: false,
            responseData: this.response,
            yamlData: ''
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
        },
        download: function(filename, index, filenames){
        	var form = this.form;
        	var ext = filename.substring(filename.lastIndexOf('.')+1, filename.length);
            this.post("data/" + this.url + "/downloadrequest/" + filename, form).then(response => {
                if (response && response.data){
                    Vue.download(response.data, filename);
                } 
            });
        },
    },
    watch: {
        responseData: {
            immediate: true, // https://forum.vuejs.org/t/watchers-not-triggered-on-initialization/12475
            handler: function(newval, oldval){
                this.responseDataEmpty = Vue.isEmpty(newval); // defined in vueutil.js
                this.formHidden = !this.responseDataEmpty;
            }
        }
    },
    template: `
<div class='flexible d-flex flex-column'>

	<transition name="egsimform">
    <form novalidate v-on:submit.prevent="request" v-show="!formHidden"
        :class="[responseDataEmpty ? '' : ['shadow', 'border', 'bg-light']]"
        class='d-flex flex-column flexible align-self-center position-relative mb-3' style='z-index:10'>

        <div v-show='!responseDataEmpty' class='text-right m-2'>
            <button type="button" v-on:click='formHidden=true' class="close" aria-label="Close">
                <i class="fa fa-times-circle"></i>
            </button>
        </div>

        <div class="d-flex flex-column flexible" :class="[responseDataEmpty ? '' : ['mx-4', 'mb-4', 'mt-0']]">
            <div class="d-flex flexible flex-row mb-3">

                <div class="d-flex flexible flex-column">
                    <gsimselect :form="form" showfilter class="flexible"></gsimselect>
                </div>
                
                <div class="d-flex flex-column flexible ml-4">
                    
                   <imtselect :form="form" class="flexible"></imtselect>
                
                    <div class="mt-4 form-control" style="background-color:transparent">
        
        				<forminput :form='form' :name='"gmdb"'></forminput>	
                		<forminput :form='form' :name='"selexpr"' showhelpbutton
                			@helprequested='$emit("movetoapidoc", "selexpr")' class='mt-2' >
                		</forminput>
						
                    </div>

					<div class="mt-4" style="background-color:transparent">
                    	<forminput :form='form' :name='"plot_type"'></forminput>
					</div>

                </div>
            </div>
			
			<div class='d-flex flex-row justify-content-center border-top pt-2'>
				<downloadselect
					:keys="[this.$options.name + '.request.json', this.$options.name + '.request.yaml']"
					@selected="download"
					class='mr-2'
				>
					Download request as:
				</downloadselect>
	            <button type="submit" class="btn btn-outline-primary">
	                Display plots
	            </button>
            </div>

        </div>

    </form>
    </transition>
    
    <!--<visualizerdiv :data="yamlData" :filename="this.$options.name + '.yaml'" style='width:10em;height:10em'></visualizerdiv>
    <visualizerdiv :data="form" :filename="this.$options.name + '.json'" style='width:10em;height:10em'></visualizerdiv>-->
    

    <residualsplotdiv :data="responseData" :filename="this.$options.name"
        class='position-absolute pos-0 m-0' style='z-index:1'>
        <slot>
            <button @click='formHidden=false' class='btn btn-sm btn-outline-primary'><i class='fa fa-wpforms'></i> params</button>
        </slot>
    </residualsplotdiv>
</div>`
})