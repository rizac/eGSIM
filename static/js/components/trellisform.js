Vue.component('trellisform', {
  extends: EGSIMFORM,  //defined in egsimform.js
  props: {  // properties are merged with the parent:  https://medium.com/js-dojo/extending-vuejs-components-42fefefc688b
      'id': {type: String, default: 'trellis_form_id'},  // overwrite parent prop
      'name': {type: String, default: 'trellis_form'},  // same as above
      'submit_element_id': String
  },
  //https://vuejs.org/v2/guide/components-props.html#Prop-Types:
  mounted: function(){
      // configure trellis plot <select> and make it the submit element:
      var submitSelect = this.form().querySelector('#' + this.submit_element_id);
      // create a first option acting as "label", use the django label for that:
      var noValue = '';
      // set the selected index to the just added option:
      submitSelect.selectedIndex = -1;
      submitSelect.value = noValue;
      // add event listener:
      submitSelect.onchange = (event) => {
          var selectElement = event.target;
          if(selectElement.selectedIndex == -1){
              // no selection (which is programmatically set after a valid selection is done
              // via the kyvoard or mouse): no-op
              return;
          }
          // submit form to vuejs:
          this.submitForm();
          selectElement.selectedIndex = -1;
          submitSelect.value = noValue;
      }
  },
  methods: {
      created: function(){
          // Note1: this function is called from within created (https://vuejs.org/v2/api/#created)
          // it's purpose is to add custom stuff on creation without overriding the 'super' call
          // Note2: seems that adding events in mounted causes infinite loops
          // Given the above, add event listener for the form visibility:
          if (this.eventbus){
              this.eventbus.$on('toggletrellisformvisibility', () => {
                  this.setVisible(!this.visible);
              });
          }
          // catch component specific events:
          this.$on('formsubmitted', (response, isError) => {  // called by super-class when form is submitted
              if (!isError){
                  this.setVisible(false);  //hide the form
                  this.setModal(true);  //show close button
              }
          });
          this.$on('modal', value => {  // called by super-class when form is submitted
              this.formclasses = value ? ['shadow', 'bg-light', 'border'] : [];
          });
          this.$on('visible', value => {  // called by super-class when form is submitted
              this.$set(this, 'styleobject', {zIndex: value ? 100 : -100});
          });
          this.$emit('visible', true);  // force calling method above
      }
  }
})
