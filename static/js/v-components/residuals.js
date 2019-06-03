/**
 * Registers globally a Vue component. The name of the component
 * (first argument of 'Vue.component' below must be equal to this file's name 
 * (without extension)
 */
Vue.component('residuals', {
	extends: _BASE_FORM,  // defined in baseform.js
    data: function () {
    	// set the size of the plot_type <select>. Maybe this is not the right place
    	// (maybe the 'created' method would be better:
    	// https://vuejs.org/v2/api/#created) but it works:
    	this.$set(this.form['plot_type'].attrs, 'size', 10);
        return {
            responseData: {},
            formHidden: false
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
		</slot>
	</baseform>            

    <residualsplotdiv
    	:data="responseData"
    	:downloadurls="urls.downloadResponse"
    	:post="post"
        class='position-absolute pos-0 m-0' style='z-index:1'
    >
        <slot>
            <button @click='formHidden=false' class='btn btn-sm btn-primary'><i class='fa fa-wpforms'></i> params</button>
        </slot>
    </residualsplotdiv>
</div>`
})