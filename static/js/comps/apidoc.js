/**
 * Registers globally a Vue component. The name of the component
 * (first argument of 'Vue.component' below must be equal to this file's name 
 * (without extension)
 */
Vue.component('apidoc', {
  props: {src: String},
  template: `<iframe class='flexible' :src='src'>`
})