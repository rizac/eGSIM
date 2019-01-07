/**
 * Registers globally a Vue component. The name of the component
 * (first argument of 'Vue.component' below must be equal to this file's name 
 * (without extension)
 */

// template for the trellis form
// Note the slot-scope 'self' which refers to the egsimform component
// (see related .js file for info)
_TEMPLATE_TRELLIS = `
<div class="d-flex flex-column flexible" slot-scope="self">
    <div class="flexible d-flex flex-row">
        <div class="flexible d-flex flex-column">
            
            <gsimselect :form="form" showfilter class="flexible mb-4"></gsimselect>
            <imtselect :form="form"></imtselect>
        
        </div>
        
        <div class="d-flex flex-column flexible ml-4">
            <h5>Scenario configuration</h5>
            <div class="flexible form-control" style="overflow:auto; background-color:transparent">
                <div class="flexible p-1">
                
                    <template v-for="(data, name) in self.form" v-if="!['gsim', 'imt', 'sa_periods', 'plot_type'].includes(name)">
                        <div class="d-flex flex-row mb-0 mt-2 pt-1 align-items-baseline">
                            <label :for="data.attrs.id" class='mb-0'>
                                <input v-if="!data.choices.length && ['radio', 'checkbox'].includes(data.attrs.type)" v-model="data.val" v-bind="data.attrs" class='mr-1'>
                                {{ name }}
                            </label>
                            <div class="text-muted small text-nowrap flexible ml-3 text-right">
                                <span v-if="data.err" class="text-danger">{{ data.err }}</span>
                                <span v-if="!data.err && data.label.toLowerCase() != name.toLowerCase() && data.help" v-html="data.label + ' (' + data.help + ')'"></span>
                                <span v-if="!data.err && data.label.toLowerCase() != name.toLowerCase() && !data.help" v-html="data.label"></span>
                                <span v-if="!data.err && data.label.toLowerCase() == name.toLowerCase() && data.help" v-html="data.help"></span>
                            </div>
                        </div>
                        <input v-if="!data.choices.length && !['radio', 'checkbox'].includes(data.attrs.type)" v-model="data.val" v-bind="data.attrs" class='form-control'>
                        <select v-if="data.choices.length" v-model="data.val" v-bind="data.attrs" class='form-control'>
                            <option v-for='opt in data.choices' :value='opt[0]'>{{ opt[1] }}</option>
                        </select>
                    </template>

                </div>
            </div>
        </div>
    </div>

    <div class="d-flex flex-row mt-3">
        
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
      url: String,
      response: {type:Object, default: () => { return {} } }
  },
  data: function () {
      return {
      }
  },
  template: `<egsimform class='align-self-center m-4' :form='form' :url='url'
              :class="!!response ? ['shadow', 'border'] : ''" :modal='!!response' >
      ${_TEMPLATE_TRELLIS}
  </egsimform>`
})