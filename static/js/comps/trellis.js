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
    <div class="flexible d-flex flex-row mb-4">
        <div class="flexible d-flex flex-column">
            
            <gsimselect :form="form" showfilter class="flexible mb-4"></gsimselect>
            <imtselect :form="form"></imtselect>
        
        </div>
        
        <div class="d-flex flex-column flexible ml-4">
            <h5>Scenario configuration</h5>
            <div class="flexible form-control mb-4" style="background-color:transparent">

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
            
            <template v-for="name in ['plot_type']">
                <div class="d-flex flex-column">
                    <div class='d-flex flex-row align-items-baseline'>
                        <h5>{{ name }}</h5>
                        <span class="text-danger small flexible ml-3 text-right">{{ self.form[name].err }}</span>
                    </div>
                    
                    <select v-model="self.form[name].val" v-bind="self.form[name].attrs" size="4"  class='form-control'>
                        <option v-for='opt in self.form[name].choices' :value="opt[0]">{{ opt[1] }}</option>
                    </select>
                </div>
            </template>
        </div>
    </div>

    <button type="submit" class="btn btn-outline-primary">
        Display plots
    </button>

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
          formModal: false,
          responseData: this.response,
          formHidden: false
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
  watch: {
      responseData: {
          immediate: true, // https://forum.vuejs.org/t/watchers-not-triggered-on-initialization/12475
          handler: function(newval, oldval){
              var empty = Vue.isEmpty(newval); // defined in vueutil.js
              this.formModal = !empty;
              this.formHidden = !empty;
          }
      }
  },
  template: `<div class='flexible d-flex flex-column'>
      <egsimform :form='form' v-on:submit="request"
              :modalwindow='formModal' :hidden.sync="formHidden"
              class='flexible align-self-center position-relative' style='z-index:10'>
          ${_TEMPLATE_TRELLIS}
      </egsimform>

      <trellisplotdiv :data="responseData" :filename="this.$options.name"
          class='position-absolute pos-0 m-0' style='z-index:1'>
          <slot>
              <button @click='formHidden=false' class='btn btn-sm btn-outline-primary mb-1'><i class='fa fa-wpforms'></i> params</button>
          </slot>
      </trellisplotdiv>
  </div>`
})