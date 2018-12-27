/**
 * Registers globally a Vue component. The name of the component
 * (first argument of 'Vue.component' below must be equal to this file's name 
 * (without extension)
 */
Vue.component('egsim-iframe', {
  //https://vuejs.org/v2/guide/components-props.html#Prop-Types:
  props: {
      'src': {type: String},
  },
  data: function () {
      return {
      }
  },
  template: `<iframe class='flex-direction-col' :src=src>`
})