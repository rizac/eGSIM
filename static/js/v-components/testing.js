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
    	// set `edr_bandwidth` and `edr_multiplier` inital value as undefined.
    	// This means that we will skip setting the value
   		// for those fields when clicking 'restore to defaults' (see baseform.js).
   		// Their value will be set according to 'plot_type' (see 'watch' below):
   		this.form.edr_bandwidth.initial = undefined;
   		this.form.edr_multiplier.initial = undefined;
   		// return data:
        return {
        	responseData: {},
            formHidden: false
        }
    },
    watch: {
        // see parent class for watchers on the form
        
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
	<!-- https://stackoverflow.com/a/40485023 -->
	<baseform
		v-show="!formHidden"
		v-bind="$props"
		@responsereceived="responseData = arguments[0]; formHidden = true"
		@closebuttonclicked="formHidden = true"
	>
        <slot>        
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
    	</slot>
    </baseform>

    <testingtable
    	:data="responseData"
    	:downloadurls="urls.downloadResponse"
    	:post="post"
    	class='position-absolute pos-0 m-0' style='z-index:1'
    >
    	<slot>
            <button @click='formHidden=false' class='btn btn-sm btn-primary'><i class='fa fa-list-alt'></i> Configuration</button>
        </slot>
    </testingtable>
</div>`
})