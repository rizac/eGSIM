Vue.component('errorspan', {
  //https://vuejs.org/v2/guide/components-props.html#Prop-Types:
  props: {
      'errormsg': {type: String, default: ''}
  },
  template: `<span class='text-danger text-nowrap small' v-show="errormsg">{{ errormsg }} </span>`
})