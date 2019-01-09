/**
 * Registers globally a Vue component. The name of the component
 * (first argument of 'Vue.component' below must be equal to this file's name 
 * (without extension)
 */

// template for the trellis form
// Note the slot-scope 'self' which refers to the egsimform component
// (see related .js file for info)
// the main <div> is the body of the <form>
_TEMPLATE_TRELLIS = `
<div class="d-flex flex-column flexible" slot-scope="self">
    <div class="flexible d-flex flex-row">
        <div class="flexible d-flex flex-column">
            
            <gsimselect :form="form" showfilter class="flexible mb-4"></gsimselect>
            <imtselect :form="form"></imtselect>
        
        </div>
        
        <div class="d-flex flex-column flexible ml-4">
            <h5>Scenario configuration</h5>
            <div class="flexible form-control" style="background-color:transparent">

                <template v-for="(data, name) in self.form" v-if="!['gsim', 'imt', 'sa_periods', 'plot_type'].includes(name)">
                    <div class="d-flex flex-row mb-0 mt-2 pt-1 align-items-baseline">
                        <label :for="data.attrs.id" class='mb-0 text-nowrap'>
                            <input v-if="!data.choices.length && ['radio', 'checkbox'].includes(data.attrs.type)" v-model="data.val" v-bind="data.attrs" class='mr-1'>
                            {{ name }}
                        </label>
                        <div class="text-muted small flexible ml-3 text-right">
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

    <div class="d-flex flex-row mt-4">
        
        <template v-for="name in ['plot_type']">
            <div class="flexible d-flex flex-column">
                <div class='d-flex flex-row align-items-baseline'>
                    <h5>{{ name }}</h5>
                    <span class="text-danger small flexible ml-3 text-right">{{ self.form[name].err }}</span>
                </div>
                
                <div class="d-flex flex-row flexible form-control" style="background-color:transparent">
                    <label v-for='opt in self.form[name].choices' :for="'id_' + opt[0]" class='mr-3 text-nowrap'> 
                        <input type='radio' v-model="self.form[name].val" :value="opt[0]" :id="'id_' + opt[0]"> {{ opt[1] }}
                    </label> 
                </div>
            </div>
        </template>

        <button type="submit" class="btn btn-outline-primary ml-4">
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
      response: {type: Object, default: () => {return {}}},
      post: Function
  },
  data: function () {
      return {
          modal: !Vue.isEmpty(this.response), // defined in vueutil.js
          responseData: this.response,
          hidden: !Vue.isEmpty(this.response)
      }
  },
  methods: {
      request: function(form){
          this.post(this.url, form).then(response => {
              if (response && response.data){
                  this.responseData = response.data;
              } 
          });
      }
  },
  template: `<egsimform style='max-width:70vw' :form='form' :url='url'
              v-on:submit="request"
              :class="modal ? ['shadow', 'border'] : ''" :modal='modal' :hidden="hidden" class='align-self-center m-4'>
      ${_TEMPLATE_TRELLIS}
  </egsimform>`
})