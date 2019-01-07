// base "class" for EGSIM forms. The user has jyst to override the template
// with a slot for custom <input>s and <select> tags.
// Using the slot scope, e.g. <div slot-scope="self"> on the root template element,
// then 'self.form' can be used in the template to access all passed form fields and customize
// the inputs and select tags.
var EGSIMFORM = Vue.component('egsimform', {
  //https://vuejs.org/v2/guide/components-props.html#Prop-Types:
  props: {
      'form': Object,
      'url': String,
      'hidden': {type: Boolean, default: false},
      'modal': {type: Boolean, default: false},
  },
  data: function () {
      return {};
  },
  template: `<form novalidate v-on:submit.prevent='submitForm'
                v-show="!hidden" class='p-4'>

                <div v-show='modal' class='text-right'>
                    <button type="button" v-on:click='setVisible(false)' class="close" aria-label="Close">
                        <span aria-hidden="true">&times;</span>
                    </button>
                </div>
                <slot v-bind:form="form"></slot>
            </form>`,
  methods: {
      setModal: function(value){
          this.$set(this, 'modal', value);
      },
      setVisible: function(value){
          this.$set(this, 'hidden', !value);
      },
      submitForm(){
          if(!this.eventbus){
              return;
          }
          this.$set(this, 'fielderrors', {});  // clear field errors
          var url = this.url;
          // build form data inot a dict:
          var form = this.$el;
          var [data, error] = parseForm(form);
          if(error){
              this.eventbus.$emit('error', error);
          }else{
              this.eventbus.$emit('postrequest', url, data, {});
          }
      },
      //formSubmitted(response, isError){return;}, // no-op, can be overridden (see below)
      created(){return;} // no-op, can be overriden for custom code when this instance is created
  },
  created: function(){
      if (this.eventbus){
          this.eventbus.$on('postresponse', (response, isError) => {
              if (response.config.url == this.url){
                  this.$emit('formsubmitted', response, isError);
              }
          });
          this.eventbus.$on('error', error => {
              var errors = error.errors || [];
              var fielderrors = {};
              for (var err of errors){
                  if (err.domain){
                      fielderrors[err.domain] = err.message || 'unknown error';
                  }
              } 
              this.$set(this, 'fielderrors', fielderrors);
          });
      }
      this.created();
  }
});


function parseForm(form){
    /**
    * Parses a given form and returns an array of two objects: [data, error]
    * where `data` maps form element names to their *parsed* values, and `error` is a google
    * json error object (https://stackoverflow.com/a/23708903) which maps
    * invalid form element names to their error messages (string). If the form is valid, then
    * `error` is anot an object but falsy (false/undefined/null).
    * Form elements are those returned by the `form.elements` method:
    * <input> elements of type 'button', 'submit' and 'reset' will be ignored, as well as elements
    * without a valid (truthy) name, or elements with no value set and no required attribute.
    * "No value set" means generally empty string value, but it depends on the input type and tagName;
    * in fact, values are parsed for these elements:
    * <select multiple>  (returns an array of strings instead of a string. No value set: empty array)
    * <input type=checkbox> (returns a boolean instead of string. No value set: false)
    * <input type=number> (returns a float instead of string. No value set: empty string,
    *                      which should be checked by the browser validation beforehand)
    * For any other element, the element value attribute is returned (should be string in most, when
    * not all, cases). For info on input types, see:
    *   https://www.w3schools.com/Html/html_form_input_types.asp
    */
    var data = {};
    var error = false;
    var toNumber = parseFloat;
    var toInt = parseInt;
    var toDate = function(value){return new Date(value);}
    var SELECT_TAG = 'select';
    for (var elm of formElements(form)){
        var type = elm.tagName.toLowerCase() == SELECT_TAG ? SELECT_TAG : elm.type.toLowerCase();
        var name = elm.name;
        var value = elm.value;
        var required = elm.required;
        // run browser form field validation:
        if(!elm.checkValidity()){
            error = error || {code: 400, message: 'Validation error', errors: []};
            error.errors.push({domain: name, message: elm.validationMessage});
            continue;
        }
        // specific cases, parsing and ignoring (if no required):
        if (type == 'radio' && !elm.checked){
            // in case of radios, when no selection is made, value is the value of the first radio
            // item (at least in Chrome): first continue if element is not required:
            if(!required){
                continue;
            }
            // if required, set the value to the empty string for safety:
            value = '';
        }else if(type == 'select'){
            var selected = elm.querySelectorAll('option:checked');
            value = Array.from(selected).map((el) => el.value);
            if(!elm.multiple){
                value = value[0] || '';
                if(!value && !required){
                    continue;
                }
            }else{
                // "no value set" means empty array for <select multiple>s:
                if(!value.length && !required){
                    continue;
                }
            }
        }else if(type == 'checkbox'){
            value = elm.checked && true;
            if(!value && !required){
                continue;
            }
        }else if(type == 'number'){
            // do check prior to conversion, otherwise !0 = true and we might discard valid values: 
            if(!value && !required){
                continue;
            }
            value == toNumber(value);
        }else{
            if(!value && !required){
                continue;
            }
        }
        
        /* else if(type == 'date'){
            value == toDate(value);
        }else if(type == 'time'){
            value == toDate(value);
        }else if(type == 'datetime-local'){
            value == toDate(value);
        }else if(type == 'range'){
            value == toInt(value);
        } */
        data[name] = value;
    }
    return [data, error];
}

function* formElements(form) {
    // returns a generator over all elements of the given form.
    // Does not yield <input> elements of type ('submit', 'button', 'reset')
    // <button> elements
    // any element with falsy 'name' property (not set or empty)
    for (var elm of form.elements){
        var tagName = elm.tagName.toLowerCase();
        var typeName = elm.type.toLowerCase();
        var type = tagName == 'select' || tagName == 'button' ? tagName : typeName;
        var name = elm.name;
        // skip stuff we do not need to include:
        if(!name || type == 'submit' || type=='button' || type=='reset'){
            continue;
        }
        yield elm;
    }
}
