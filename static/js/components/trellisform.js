Vue.component('trellisform', {
  extends: EGSIMFORM,  //defined in egsimform.js
  props: {
      'submit_element_id': String
  },
  //https://vuejs.org/v2/guide/components-props.html#Prop-Types:
  mounted: function(args){
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
      formSubmitted(response, isError){  // called by super-class when form is submitted
          if (!isError){
              this.$set(this, 'visible', false);  //hide the form
              this.$set(this, 'modal', true);  //show close button
          }
      }
  }
})
