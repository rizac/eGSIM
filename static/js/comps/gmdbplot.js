/**
 * Registers globally a Vue component. The name of the component
 * (first argument of 'Vue.component' below must be equal to this file's name 
 * (without extension)
 */
Vue.component('gmdbplot', {
  //https://vuejs.org/v2/guide/components-props.html#Prop-Types:
  props: {
      'name': {type: String, default: 'gsim'},
      'errormsg': {type: String, default: ''},
      'showfilter': Boolean,
      'selectedgsims': {type: Array, default:[]},
      'avalgsims': Map
  },
  data: function () {
      return {
          filterText: '',
          filterType: 'GSIM name',
          filterTypes: ['GSIM name', 'IMT', 'Tectonic Region Type'],
          filterFunc: elm => true,
          selection: Array.from(this.selectedgsims)
      }
  },
  template: `<div class='d-flex flex-column'>
    this is Gmdbplot
  </div>`
})