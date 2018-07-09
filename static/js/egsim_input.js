var EGSIM_INPUT = new Vue({
    el: '#egsim-input',
    data: {
        // NOTE: do not prefix data variable with underscore: https://vuejs.org/v2/api/#data
        // csrf token stored in an <input> in the base.html. Get it here and use it for each post request:
        csrftoken: Object.freeze(document.querySelector("[name=csrfmiddlewaretoken]").value),
        dom: {formclasses: {}, visible:true, modal:false}, //a vuejs dict of classes to be set to the main form
        avalGsims: new Map(),  // map of available gsims name -> array of gsim attributes
        avalImts: new Set(),  // set of available imts names
        selectedGsims: [],
        selectedImtsChanged: false, //for computed property (see below)
        selectedImtsSet: new Set(),
        saPeriods: '',
        filterText: '',
        filterType: 'GSIM name',
        filterTypes: ['GSIM name', 'IMT', 'Tectonic Region Type'],
        filterFunc: elm => true,
        loading: false,
        errormsg: '',
        fielderrors: {},
        form: undefined //will be set in mounted()
    },
    methods: {
        isImtSelectable(imt) {
            if (!this.selectedGsims.length){
                return false;
            }
            for (let gsim of this.selectedGsims){
                var selectableImts = this.avalGsims.get(gsim)[0];
                if (!selectableImts.has(imt)){
                    return false;
                }
            }
            return true;    
        },
        toggleImtSelection(imt){
            if(this.avalImts.has(imt)){
                this.$set(this, 'selectedImtsChanged', !this.selectedImtsChanged);
                if(this.selectedImtsSet.has(imt)){
                    this.selectedImtsSet.delete(imt);
                }else{
                    this.selectedImtsSet.add(imt);
                }
            }
        },
        isGsimVisible(gsim){
            return this.filterFunc(gsim);
        },
        updateFilter(){
            var regexp = this.filterText ? new RegExp(this.filterText.replace(/\*/g, '.*').replace(/\?/g, '.'), 'i') : undefined;
            var filterFunc = elm => true;
            if (this.filterType == this.filterTypes[0]){
                var filterFunc = function(gsimName){
                    return gsimName.search(regexp) > -1;
                }
            }else if (this.filterType == this.filterTypes[1]){
                var filterFunc = function(gsimName){
                    if (gsimName.startsWith('AlNomanC')){
                        var fg = 9;
                    }
                    var imts = this.avalGsims.get(gsimName)[0];
                    for (let imt of imts){
                        if (imt.search(regexp) > -1){
                            return true;
                        }
                    };
                    return false;
                }
            }else if (this.filterType == this.filterTypes[2]){
                var filterFunc = function(gsimName){f
                    var trt = this.avalGsims.get(gsimName)[1];
                    return trt.search(regexp) > -1;
                }
            }
            this.$set(this, 'filterFunc', filterFunc);
        },
        setError(error){ // error must be a google-json dict-like {message: '', code: '', errors: []}
            this.$set(this, 'loading', false);
            this.$set(this, 'errormsg', error.message || 'Unknown error');
            var errors = error.errors || [];
            var fielderrors = {};
            for (var err of errors){
                if (err.domain){
                    fielderrors[err.domain] = err.message || 'invalid value';
                }
            }
            this.$set(this, 'fielderrors', fielderrors);
        },
        formIsValid(){
            return isValid(this.form);
        },
        submitForm(url, onSuccess, onEnd=undefined){
            //submits a form to the given url, calling `onSuccess(jsonResponseData)` on success
            // (jsonResponseData is the dict of the response data). If onEnd is provided,
            // calls onEnd(isError) at the end of the call, where isError is a boolean denoting
            // if an error (url error, code error, validation error) occurred. This callback is
            // usually used to make some cleanup in the DOM
            if (!onEnd){
                onEnd = arg => {};
            }
            // build form data inot a dict:
            var [data, error] = parseForm(this.form);
            if(error){
                this.setError(error);
                onEnd.call(this, true);
            }else{
                this.$set(this, 'loading', true);
                this.$set(this, 'errormsg', '');
                this.$set(this, 'fielderrors', {});
                axios.post(url, data, {headers: {"X-CSRFToken": this.csrftoken}}).
                    then(response => {
                     // Note: arrow function don't have a proper this, so this refers to this vue instance:
                        var jsondata = response.data.data;
                        // execute the function when the the Vue instance has finished rendering the DOM:
                        this.$nextTick(this.getFormSubmittedCallback(onSuccess, jsondata));
                        onEnd.call(this, false);
                    }).catch(error => {
                        var jsondata = error.response.data.error;
                        this.$set(this, 'loading', false);
                        this.setError(jsondata);
                        onEnd.call(this, true);
                    });
            }
        },
        getFormSubmittedCallback(callback, response){
            return () => {
                this.$set(this, 'loading', false);
                if (typeof callback === 'function'){
                    try{
                        callback(response);
                    }catch(err){
                        this.setError({message: err.message, code:500});
                    }
                }
            }
        },
        toggleFormVisibility(){
            this.$set(this, 'formvisible', !this.formvisible);
        }
    },
    mounted: function() { // https://stackoverflow.com/questions/40714319/how-to-call-a-vue-js-function-on-page-load
        // assign the form element to this class:
        this.$set(this,'form', document.forms["egsim-form"]);
        // fetch gsim and imts data:
        axios.post('/get_init_params', {}, {headers: {"X-CSRFToken": this.csrftoken}}).then(response => {
            //success: if using this.$http (vue ruouting):
            // [avalGsims, avalImts] = getInitData(response.body.init_data);
            // if using axios:
            [avalGsims, avalImts] = getInitData(response.data.initData);
            this.$set(this, 'avalGsims', avalGsims);
            this.$set(this, 'avalImts', avalImts);
        }).catch((error) => {
            var jsondata = error.response.data.error;
            this.setError(jsondata);
        })
    },
    watch: { // https://siongui.github.io/2017/02/03/vuejs-input-change-event/
        filterText: function(value, oldValue) {
            if (oldValue !== value){
                this.updateFilter();
            }
        },
        filterType: function(value, oldValue) {
            if (oldValue !== value){
                this.updateFilter();
            }
        }
    },
    computed: {
//        hasError(){
//            for(var err in this.errors){
//                // no need of hasOwnProperty anymore: https://stackoverflow.com/a/45014721
//                return true;
//            }
//            return false;
//        },
        // https://stackoverflow.com/a/47044150
        gsims() {
            return Array.from(this.avalGsims.keys());
        },
        imts(){
            return Array.from(this.avalImts);
        },
        selectedImts(){
            // use this.selectedImtsChanged to notify vuejs that we need to recompute this property then
            // its value changes:
            this.selectedImtsChanged; // http://optimizely.github.io/vuejs.org/guide/computed.html#Dependency_Collection_Gotcha
            // compute the array:
            return Array.from(this.selectedImtsSet);
        }
    }
})


function getInitData(data) {
    gsims = new Map();
    imts = new Set();
    
    /**
     * Initializes a new InputSelection
     * 
     * :param avalGsims: an iterable (Array, Set,...) of objects. Each object is na Array
     *  is an Array of the form:
     * [
     *  gsimName (string),
     *  intensity measure types defined for the gsim (Array of String),
     *  tectonic region type defined for the gsim (String)
     *  ruptureParams (array of strings? FIXME: check)
     * ]
     */
    for (let gsim of data) {
        var gsimName = gsim[0];
        var gImts = new Set(gsim[1]);
        for (let gImt of gImts){
            imts.add(gImt);
        }
        var trt = gsim[2];
        var ruptureParams = gsim[3];
        gsims.set(gsimName, [gImts, trt, ruptureParams]);
    }
    return [gsims, imts];
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


function isValid(form){
    for (var elm of formElements(form)){
        // run browser form field validation:
        if(!elm.checkValidity()){
            return false;
        }
    }
    return true;
}


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