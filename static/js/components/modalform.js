// modalform is an egsimform which changes its modal appearence on form submission
var MODALFORM = Vue.component('modalform', {
  extends: EGSIMFORM,  //defined in egsimform.js
  methods: {
      created: function(){
          // Note1: this function is called from within created (https://vuejs.org/v2/api/#created)
          // it's purpose is to add custom stuff on creation without overriding the 'super' call
          // Note2: seems that adding events in mounted causes infinite loops
          // Given the above, add event listener for the form visibility:
          if (this.eventbus){
              this.eventbus.$on(this.url+':form:show', () => {
                  this.setVisible(true);
              });
              this.eventbus.$on(this.url+':form:hide', () => {
                  this.setVisible(false);
              });
          }
          // catch component specific events:
          this.$on('formsubmitted', (response, isError) => {  // called by super-class when form is submitted
              if (!isError){
                  this.setVisible(false);  //hide the form
                  this.setModal(true);  //show close button
                  this.$set(this, 'formclasses', ['shadow', 'bg-light', 'border']);
              }
          });
      }
  }
})
