/**
 * vuejs component to be used for error message content. If no error text provided, the
 * span is hidden. The span is styled with bootstrap.css (required).
 * You can bind the text to a variable:
 * <errorspan v-bind:text="variable"></errorspan>
 * Or provide custom text:
 * <errorspan>my error text</errorspan>
 */
Vue.component('errorspan', {
  // https://vuejs.org/v2/guide/components-props.html#Prop-Types:
  props: {
      'text': {type: String, default: ''}
  },
  // https://vuejs.org/v2/guide/components-slots.html#Default-Slot-Content:
  template: `<span class='text-danger text-nowrap small' v-show="text"><slot>{{ text }}</slot></span>`
})