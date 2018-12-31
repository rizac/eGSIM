/**
 * Registers globally a Vue component. The name of the component
 * (first argument of 'Vue.component' below must be equal to this file's name 
 * (without extension)
 */

// template for the trellis form
// Note the slot-scope 'self' which refers to the egsimform component
// (see related .js file for info)
_TEMPLATE_TRELLIS = `
<div class="flexible flex-direction-col" slot-scope="self">
    <div class="flexible flex-direction-row">
        <div class="flexible flex-direction-col">
            
            <!--<gsimselect class="flexible p-1 mb-4" name="gsim" showfilter="" v-bind:errormsg="formscope.fielderrors['gsim']" v-bind:avalgsims="avalGsims" v-bind:selectedgsims.sync="selectedGsims">
                Ground Shaking Intensity Model(s)
            </gsimselect>
            
            <imtselect class="p-1" name="imt" v-bind:errormsg="formscope.fielderrors['imt']" v-bind:avalgsims="avalGsims" v-bind:selectedgsims="selectedGsims" v-bind:avalimts="avalImts" v-bind:selectedimts.sync="selectedImts">
                Intensity Measure Type(s)
            </imtselect>-->
        
        </div>
        
        <div class="flex-direction-col flexible ml-4">
            <h5>Scenario configuration</h5>
            <div class="flexible form-control" style="overflow:auto; background-color:transparent">
                <div class="flexible p-1 grid-2-columns grid-col-gap-2 grid-row-gap-0">
                
                    <template v-for="(data, name) in self.form" v-if="!['gsim', 'imt', 'sa_periods', 'plot_type'].includes(name)">
                        <div>
                            <label for="data.attrs.id">{{ name }}</label>
                            <span class="text-danger small text-nowrap">{{ data.err }}</span>
                        </div>
                        <input v-if="!data.choices.length" v-model="data.val" v-bind="data.attrs">
                        <select v-if="data.choices.length" v-model="data.val" v-bind="data.attrs">
                            <option v-for='opt in data.choices' :value='opt[0]'>{{ opt[1] }}</option>
                        </select>
                        <div class="text-muted small text-nowrap mb-2 field-help grid-col-span">{{ data.label }} ({{ data.help }})</div>
                    </template>

                </div>
            </div>
        </div>
    </div>

    <div class="flex-direction-row mt-3">
        
        <template v-for="name in ['plot_type']">
            <label for="self.form[name].attrs.id">{{ name }}</label>
            <div class="flexible mr-3 ml-1">
                <select v-model="self.form[name].val" v-bind="self.form[name].attrs" class="form-control" size="4">
                    <!-- if size is not provided, add the following (see note here: https://vuejs.org/v2/guide/forms.html#Select)
                    <option disabled value="">{{ self.form[name].label }}</option>
                     -->
                    <option v-for='opt in self.form[name].choices' :value='opt[0]'>{{ opt[1] }}</option>
                </select>
                <span class="text-danger small text-nowrap">{{ self.form[name].err }}</span>
            </div>
            
        </template>

        <button type="submit" class="btn btn-outline-primary">
            Display plots
        </button>
    </div>

</div>
`

Vue.component('trellis', {
  //https://vuejs.org/v2/guide/components-props.html#Prop-Types:
  props: {
      form: Object,
      url: String
  },
  data: function () {
      return {
      }
  },
  template: `<egsimform class='flex-direction-col' :form='form' :url='url'>
      ${_TEMPLATE_TRELLIS}
  </egsimform>`
})