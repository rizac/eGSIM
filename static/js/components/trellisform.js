Vue.component('trellisform', {
  extends: EGSIMFORM,  //defined in egsimform.js
  props: {
      'submit_element_id': String
  },
  //https://vuejs.org/v2/guide/components-props.html#Prop-Types:
  mounted: function(args){
      var submitSelect = this.form().querySelector('#' + this.submit_element_id);
      // create a first option acting as "label", use the django label for that:
      var no_value = '';
      // set the selected index to the just added option:
      submitSelect.value = no_value;
      // add event listener:
      submitSelect.onchange = (event) => {
          var selectElement = event.target;
          if(selectElement.value == no_value){
              // no selection (which is programmatically set after a valid selection is done
              // via the kyvoard or mouse): no-op
              return;
          }
          // create arguments for submitForm:
//           var onEnd = function(isError){
//              selectElement.value = no_value;
//              // set classes styling the egsim-input vue elements appearence:
//              // (`this` refers to the vue instance)
//              this.dom.visible = isError;  // this sets classes on the main div
//              if (!this.dom.modal && !isError){
//                  this.dom.modal = true; // show upper div with close button
//              }
//              this.dom.formclasses = isError ? [] : ['shadow', 'bg-light', 'border'];
//          };
          // submit form to vuejs:
          this.submitForm();
          selectElement.value == no_value;
      }
  }
})
