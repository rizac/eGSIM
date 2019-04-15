// base "class" for EGSIM forms. The user has jyst to override the template
// with a slot for custom fields, e.g. via <input>s and <select> (and a <submit>) tags.
// Using the slot scope, e.g. <div slot-scope="self"> on the root template element,
// then 'self.form' can be used in the template to access all passed form fields and customize
// the inputs and select tags.
var EGSIMFORM = Vue.component('egsimform', {
    //https://vuejs.org/v2/guide/components-props.html#Prop-Types:
    props: {
        'form': Object,
        'hidden': {type: Boolean, default: false},  // wheather the form is visible
        'modalwindow': {type: Boolean, default: false},  // wheather the form is a modal window (e.g., close button is shown)
    },
    computed: {
        visible: {  // https://vuejs.org/v2/guide/computed.html#Computed-Setter
          // getter
          get: function () {
              return !this.hidden;
          },
          // setter
          set: function (newValue) {
              this.$emit('update:hidden', !newValue);
          }
        }
    },
    template: `<form novalidate v-on:submit.prevent='submitForm'
                    class='d-flex flex-column px-4 pb-4'
                    v-show="visible"
                    :class="[modalwindow ? ['shadow', 'border', 'bg-light', 'pt-2', 'mb-3'] : 'pt-4']">
        <div v-show='modalwindow' class='text-right'>
            <button type="button" v-on:click='visible=false' class="close" aria-label="Close">
                <span aria-hidden="true">&times;</span>
            </button>
        </div>
        <slot v-bind:form="form"></slot>
    </form>`,
    methods: {
        setVisible: function(value){
            this.visible = value;
        },
        submitForm(){
            this.$emit('submit', this.form);
        }
    },
    created: function(){
        // no-op
    }
});
