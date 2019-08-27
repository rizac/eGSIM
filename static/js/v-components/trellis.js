/**
 * Registers globally a Vue component. The name of the component
 * (first argument of 'Vue.component' below must be equal to this file's name 
 * (without extension)
 */
Vue.component('trellis', {
	extends: _BASE_FORM,  // defined in baseform.js
    data: function () {
    	// set the size of the plot_type <select>. Note that it turns out
    	// that 'created' is executed after the template is created, so we add
    	// reactive properties like 'size' here (or maybe 'beforeCreate' would be
    	// a better place? https://vuejs.org/v2/api/#beforeCreate)
    	this.$set(this.form['plot_type'].attrs, 'size', 3);
		// return data:
        return {
        	predefinedSA: false,  // whether we have selected spectra as plot type
        	responseData: {},
        	formHidden: false,
            scenarioKeys: Object.keys(this.form).filter(key => key!='gsim' && key!='imt' && key!='sa_period' && key!='plot_type' && key!='stdev')
        }
    },
    computed: {
    	scenarioHasErrors: function(){
    		var form = this.form;
    		return this.scenarioKeys.some(key => !!form[key].err);
    	}
    },
    watch: {
        // watch additionally for the property val of plot_type in form
        // and make imt enabled if we are not choosing spectra plots
        // this is a bit hacky in that it relies on the parameter names
        // plot_type and imt:
        'form.plot_type.val': {
        	immediate: true,
        	handler: function(newVal, oldVal){
        		var enabled = newVal !== 's' && newVal !== 'ss';
        		this.form.imt.attrs.disabled = !enabled;
        		this.predefinedSA = !enabled;
        	}
        }
    },
    template: `
<div class='flexible d-flex flex-column'>
	<!-- v-bind="$props" passes all of the props on to the "parent" component -->
	<!-- https://stackoverflow.com/a/40485023 -->
	<baseform
		v-show="!formHidden"
		v-bind="$props"
		:imtselectclasses="''"
		@responsereceived="responseData = arguments[0]; formHidden = true"
		@closebuttonclicked="formHidden = true"
    >
    	<slot>
    		<div v-show='predefinedSA'><i class='text-warning fa fa-info-circle'></i> Intensity Measure Type will default to 'SA' with a set of pre-defined periods</div>
        	<div class="flexible form-control mt-4"
            	style="flex-basis:0;background-color:transparent;overflow-y:auto"
            	:class="{'border-danger': scenarioHasErrors}"
            >
                <forminput
                	v-for="(name, index) in scenarioKeys"
                    :form='form' :name='name' :key="name"
                    :class="{ 'mt-2': index > 0 }">
                </forminput>
            </div>

            <div class="mt-4" style="background-color:transparent">
                <forminput :form='form' :name='"plot_type"'></forminput>
                <forminput :form='form' :name='"stdev"' class='mt-1'></forminput>
            </div>
        </slot>
    </baseform>

    <trellisplotdiv
    	:data="responseData"
    	:downloadurls="urls.downloadResponse.concat(urls.downloadImage)"
        class='position-absolute pos-0 mb-2 mx-2' style='z-index:1'
    >
        <slot>
            <button @click='formHidden=false' class='btn btn-sm btn-primary'><i class='fa fa-list-alt'></i> Configuration</button>
        </slot>
    </trellisplotdiv>
</div>`
})