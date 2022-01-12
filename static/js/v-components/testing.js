/**
 * Registers globally a Vue component. The name of the component
 * (first argument of 'Vue.component' below must be equal to this file's name 
 * (without extension)
 */
Vue.component('testing', {
	extends: _BASE_FORM,  // defined in baseform.js
    data: function () {
        return {
        	responseData: {},
            formHidden: false
        }
    },
    watch: {
    },
    computed: {
        isEDRSelected(){
            var val = this.form.fit_measure.value;
            edr = val && val.length && val.some(v => v.toLowerCase() == 'edr');
            // if disabled, data is not sent to the server (for safety):
            this.form.edr_bandwidth.disabled = !edr;
            this.form.edr_multiplier.disabled = !edr;
            return edr;
        }
    },
    template: `
<div class='flexible d-flex flex-column position-relative'>
	<!-- $props passes all of the props on to the "parent" component -->
	<!-- https://stackoverflow.com/a/40485023 -->
	<base-form v-show="!formHidden" v-bind="$props"
		       @responsereceived="responseData = arguments[0]; formHidden = true"
		       @closebuttonclicked="formHidden = true">

		<template v-slot:left-column>
            <gsim-select :field="form.gsim" :imtField="form.imt" class="flexible" />
        </template>

        <template v-slot:right-column>
            <imt-select :field="form.imt" class='flexible' size="7"></imt-select>

            <div class="mt-4 form-control" style="background-color:transparent">
                <field-input :field='form.flatfile'></field-input>
            	<field-input :field='form.selexpr' class='mt-2'></field-input>
            	<!-- showhelpbutton	@helprequested='$emit("emit-event", "movetoapidoc", "selexpr")' -->
            </div>
            
            <div class="mt-4" style="background-color:transparent">
            	<field-input :field='form.fit_measure' size="5"></field-input>
            	<base-input v-show="isEDRSelected" class='mt-1'
            	            v-model="form.edr_bandwidth.value"
            	            :disabled="form.edr_bandwidth.disabled"
            	            :error="!!form.edr_bandwidth.error">
            	    {{ form.edr_bandwidth.name }}
            	</base-input>
            	<base-input v-show="isEDRSelected" class='mt-1'
            	            v-model="form.edr_multiplier.value"
            	            :disabled="form.edr_multiplier.disabled"
            	            :error="!!form.edr_multiplier.error">
            	    {{ form.edr_multiplier.name }}
            	</base-input>
			</div>
    	</template>
    </base-form>

    <testingtable :data="responseData" :downloadurls="urls.downloadResponse"
    	          class='position-absolute pos-0' style='z-index:1'>
    	<slot>
            <button @click='formHidden=false' class='btn btn-sm btn-primary'><i class='fa fa-list-alt'></i> Configuration</button>
        </slot>
    </testingtable>
</div>`
})