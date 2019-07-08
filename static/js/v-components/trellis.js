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
   		// set `imt` and `sa_period` inital value as undefined.
   		// This means that we will skip setting the value
   		// for those fields when clicking 'restore to defaults' (see baseform.js).
   		// Their value will be set according to 'plot_type' (see 'watch' below):
   		this.form.imt.initial = undefined;
   		this.form.sa_period.initial = undefined;
		// return data:
        return {
        	responseData: {},
        	formHidden: false,
            scenarioKeys: Object.keys(this.form).filter(key => key!='gsim' && key!='imt' & key!='sa_period' & key!='plot_type')
        }
    },
    watch: {
        // see parent class for watchers on the form

        // watch additionally for the property val of plot_type in form
        // and make imt enabled if we are not choosing spectra plots
        // this is a bit hacky in that it relies on the parameter names
        // plot_type and imt:
        'form.plot_type.val': {
        	immediate: true,
        	handler: function(newVal, oldVal){
        		var enabled = newVal !== 's' && newVal !== 'ss';
        		this.form.imt.attrs.disabled = !enabled;
        		if (!enabled){
        			this.form.imt.valTmp = this.form.imt.val;
        			this.form.sa_period.valTmp = this.form.sa_period.val;
        			this.form.imt.val = ['SA'];
        			this.form.sa_period.val = '(set of pre-defined periods)';
        		}else if('valTmp' in this.form.imt){
        			this.form.imt.val = this.form.imt.valTmp;
        			this.form.sa_period.val = this.form.sa_period.valTmp;
        			delete this.form.imt.valTmp;
        			delete this.form.sa_period.valTmp;
        		}
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
		@responsereceived="responseData = arguments[0]; formHidden = true"
		@closebuttonclicked="formHidden = true"
    >
    	<slot>
            <div class="d-flex flex-column flexible ml-4">

				<imtselect :form="form"></imtselect>

                <div class="flexible form-control mt-4"
                	style="flex-basis:0;background-color:transparent;overflow-y:auto">
                    <forminput
                    	v-for="(name, index) in scenarioKeys"
                        :form='form' :name='name' :key="name"
                        :class="{ 'mt-2': index > 0 }">
                    </forminput>
                </div>

                <div class="mt-4" style="background-color:transparent">
                    <forminput :form='form' :name='"plot_type"'></forminput>
                </div>

            </div>
        </slot>
    </baseform>

    <trellisplotdiv
    	:data="responseData"
    	:downloadurls="urls.downloadResponse"
    	:post="post"
        class='position-absolute pos-0 m-0' style='z-index:1'
    >
        <slot>
            <button @click='formHidden=false' class='btn btn-sm btn-primary'><i class='fa fa-wpforms'></i> Configuration</button>
        </slot>
    </trellisplotdiv>
</div>`
})