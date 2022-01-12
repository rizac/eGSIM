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
    	this.$set(this.form['plot_type'], 'size', 3);
		// return data:
        return {
        	predefinedSA: false,  // whether we have selected spectra as plot type
        	responseData: {},
        	formHidden: false,
            scenarioKeys: Object.keys(this.form).filter(key => key!='gsim' && key!='imt' && key!='plot_type' && key!='stdev')
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
        'form.plot_type.value': {
        	immediate: true,
        	handler: function(newVal, oldVal){
        		var enabled = newVal !== 's' && newVal !== 'ss';
        		this.form.imt.disabled = !enabled;
        		this.predefinedSA = !enabled;
        		if (!enabled){
        		    // Spectra plots ignore the passed IMT, but <gsim-select>s might need
        		    // to be updated. What to set as selected IMTs then? simply nothing:
        		    this.form.imt.value = [];
        		}
        	}
        }
    },
    template: `
<div class='flexible d-flex flex-column position-relative'>
	<!-- v-bind="$props" passes all of the props on to the "parent" component -->
	<!-- https://stackoverflow.com/a/40485023 -->
	<base-form v-show="!formHidden" v-bind="$props"
		      @responsereceived="responseData = arguments[0]; formHidden = true"
		      @closebuttonclicked="formHidden = true">

        <template v-slot:left-column>
            <gsim-select :field="form['gsim']" :imtField="form['imt']" class="flexible" />
        </template>

        <template v-slot:right-column>
    	    <imt-select v-show='!predefinedSA' :field="form['imt']"></imt-select>
    		<div v-show='predefinedSA'>
    		    <i class='text-warning fa fa-info-circle'></i>
    		    Intensity Measure will default to 'SA' with a set of pre-defined periods
    		</div>
        	<div class="flexible form-control mt-4"
        	     :class="{'border-danger': scenarioHasErrors}"
            	 style="flex-basis:0;background-color:transparent;overflow-y:auto">

                <field-input v-for="(name, index) in scenarioKeys" :key="name"
                             :field='form[name]' :class="{ 'mt-2': index > 0 }">
                </field-input>
            </div>

            <div class="mt-4" style="background-color:transparent">
                <field-input :field='form["plot_type"]'></field-input>
                <field-input :field='form["stdev"]' class='mt-1'></field-input>
            </div>
        </template>
    </base-form>

    <trellisplotdiv	:data="responseData"
    	            :downloadurls="urls.downloadResponse.concat(urls.downloadImage)"
                    class='position-absolute pos-0' style='z-index:1'>
        <slot>
            <button @click='formHidden=false' class='btn btn-sm btn-primary'>
                <i class='fa fa-list-alt'></i> Configuration
            </button>
        </slot>
    </trellisplotdiv>
</div>`
})