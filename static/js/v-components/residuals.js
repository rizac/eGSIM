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
    	// this.$set(this.form['plot_type'], 'size', 10);
        return {
            responseData: {},
            formHidden: false
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

			<div class="mt-4">
            	<field-input :field='form.plot_type' size="7"></field-input>
			</div>

		</template>
	</base-form>

    <residualsplotdiv :data="responseData"
    	              :downloadurls="urls.downloadResponse.concat(urls.downloadImage)"
                      class='position-absolute pos-0' style='z-index:1'>
        <slot>
            <button @click='formHidden=false' class='btn btn-sm btn-primary'><i class='fa fa-list-alt'></i> Configuration</button>
        </slot>
    </residualsplotdiv>
</div>`
})