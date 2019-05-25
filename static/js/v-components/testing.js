/**
 * Registers globally a Vue component. The name of the component
 * (first argument of 'Vue.component' below must be equal to this file's name 
 * (without extension)
 */
Vue.component('testing', {
	extends: _BASE_FORM,  // defined in baseform.js
    data: function () {
    	// set the size of the plot_type <select>. Maybe this is not the right place
    	// (maybe the 'created' method would be better:
    	// https://vuejs.org/v2/api/#created) but it works:
    	this.$set(this.form['fit_measure'].attrs, 'size', 5);
        return {
            /* 
            this object will be merged with the data Object returned by the parent
            which has the following properties:
            responseDataEmpty: true,
            responseData: this.response,
            formHidden: false
            */
        }
    },
    methods: {
        // see parent class
    },
    watch: {
        // see parent class
        
        // watch additionally for this field and set other fields visible/disabled accordingly:
        'form.fit_measure.val': {
        	// watch for changes in the fit_measure (<select> element):
        	immediate: true,
        	handler: function(newVal, oldVal){
        		var enabled = newVal && newVal.length && newVal.some(val => val.toLowerCase() == 'edr');
        		this.form.edr_bandwidth.is_hidden = !enabled;
        		this.form.edr_multiplier.is_hidden = !enabled;
        	}
        }
    },
    template: `
<div class='flexible d-flex flex-column'>

	<!-- $props passes all of the props on to the "parent" component -->
	<baseform v-bind="$props">
        <slot>        
            <div class="d-flex flex-column flexible ml-4">
            
            	<imtselect :form="form" class='flexible'></imtselect>

                <div class="mt-4 form-control" style="background-color:transparent">
                    <forminput :form='form' :name='"gmdb"'></forminput>
                	<forminput :form='form' :name='"selexpr"' showhelpbutton
            			@helprequested='$emit("movetoapidoc", "selexpr")' class='mt-2'>
            		</forminput>
                </div>
                
                <div class="mt-4" style="background-color:transparent">
                	<forminput :form='form' :name='"fit_measure"'></forminput>
                	<forminputlite :form='form' :name='"edr_bandwidth"' class='mt-1'></forminputlite>
                	<forminputlite :form='form' :name='"edr_multiplier"' class='mt-1'></forminputlite>
				</div>
            </div>
    	</slot>
    </baseform>

    <testingtable :data="responseData" :filename="this.$options.name" class='position-absolute pos-0 m-0' style='z-index:1'>
    	<slot>
            <button @click='formHidden=false' class='btn btn-sm btn-primary'><i class='fa fa-wpforms'></i> params</button>
        </slot>
    </testingtable>
</div>`
})