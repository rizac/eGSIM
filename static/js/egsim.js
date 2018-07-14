var EGSIM = new Vue({
    el: '#egsim-vue',
    data: {
        // NOTE: do not prefix data variable with underscore: https://vuejs.org/v2/api/#data
        // csrf token stored in an <input> in the base.html. Get it here and use it for each post request:
        csrftoken: Object.freeze(document.querySelector("[name=csrfmiddlewaretoken]").value),
        form: {classes: {}, visible:true, modal:false}, //a vuejs dict of props to be set to the main form
        avalGsims: new Map(),  // map of available gsims name -> array of gsim attributes
        avalImts: new Set(),  // set of available imts names
        selectedGsims: [],
        selectedImts: [],
        data: {},
        loading: false,
        errormsg: '',
        fielderrors: {},
//        form: undefined //will be set in mounted()
    },
//    created: function(){
//        this.$on('loading', value => {
//            this.$set(this, 'loading', value);
//        });
//        this.$on('error', error => {
//            this.setError(error);
//        });
//    },
    methods: {
        setError(error){ // error must be a google-json dict-like {message: '', code: '', errors: []}
            if (typeof error === 'string'){
                error = {message: error};
            }
            this.$set(this, 'errormsg', error.message);
            var errors = error.errors || [];
            var fielderrors = {};
            for (var err of errors){
                if (err.domain){
                    fielderrors[err.domain] = err.message || 'unknown error';
                }
            } 
            this.$set(this, 'fielderrors', fielderrors);
        },
        setLoading(value){
            this.$set(this, 'loading', value);
        },
        post(url, data, config, callback) { // https://stackoverflow.com/questions/40714319/how-to-call-a-vue-js-function-on-page-load
            // assign the form element to this class:
            this.setError('');
            this.setLoading(true);
            if (!callback){
                callback = (responseData) => {};
            }
            var config = Object.assign(config || {}, {headers: {"X-CSRFToken": this.csrftoken}});
            // fetch gsim and imts data:
            return axios.post(url, data || {}, config).then(response => {
                this.setLoading(false);
                callback(response);
            }).catch((error) => {
                this.setError(error.response.data.error);
                this.setLoading(false);
            });
        }
    },
    mounted: function() { // https://stackoverflow.com/questions/40714319/how-to-call-a-vue-js-function-on-page-load
        /*// assign the form element to this class:
        this.setError('');
        this.setLoading(true);
        // fetch gsim and imts data:
        axios.post('/get_init_params', {}, {headers: {"X-CSRFToken": this.csrftoken}}).then(response => {
            //success: if using this.$http (vue ruouting):
            // [avalGsims, avalImts] = getInitData(response.body.init_data);
            // if using axios:
            [avalGsims, avalImts] = getInitData(response.data.initData);
            this.$set(this, 'avalGsims', avalGsims);
            this.$set(this, 'avalImts', avalImts);
            this.setLoading(false);
        }).catch((error) => {
            this.setError(error.response.data.error);
            this.setLoading(false);
        })*/
        var callback = (response) => {
            [avalGsims, avalImts] = getInitData(response.data.initData);
            this.$set(this, 'avalGsims', avalGsims);
            this.$set(this, 'avalImts', avalImts);
        };
        this.post('/get_init_params', {}, {}, callback);
    },
    computed: {
        // https://stackoverflow.com/a/47044150
        gsims() {
            return Array.from(this.avalGsims.keys());
        },
        imts(){
            return Array.from(this.avalImts);
        },
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


//function* formElements(form) {
//    // returns a generator over all elements of the given form.
//    // Does not yield <input> elements of type ('submit', 'button', 'reset')
//    // <button> elements
//    // any element with falsy 'name' property (not set or empty)
//    for (var elm of form.elements){
//        var tagName = elm.tagName.toLowerCase();
//        var typeName = elm.type.toLowerCase();
//        var type = tagName == 'select' || tagName == 'button' ? tagName : typeName;
//        var name = elm.name;
//        // skip stuff we do not need to include:
//        if(!name || type == 'submit' || type=='button' || type=='reset'){
//            continue;
//        }
//        yield elm;
//    }
//}
//
//
//function isValid(form){
//    for (var elm of formElements(form)){
//        // run browser form field validation:
//        if(!elm.checkValidity()){
//            return false;
//        }
//    }
//    return true;
//}
//
//
//function parseForm(form){
//    /**
//    * Parses a given form and returns an array of two objects: [data, error]
//    * where `data` maps form element names to their *parsed* values, and `error` is a google
//    * json error object (https://stackoverflow.com/a/23708903) which maps
//    * invalid form element names to their error messages (string). If the form is valid, then
//    * `error` is anot an object but falsy (false/undefined/null).
//    * Form elements are those returned by the `form.elements` method:
//    * <input> elements of type 'button', 'submit' and 'reset' will be ignored, as well as elements
//    * without a valid (truthy) name, or elements with no value set and no required attribute.
//    * "No value set" means generally empty string value, but it depends on the input type and tagName;
//    * in fact, values are parsed for these elements:
//    * <select multiple>  (returns an array of strings instead of a string. No value set: empty array)
//    * <input type=checkbox> (returns a boolean instead of string. No value set: false)
//    * <input type=number> (returns a float instead of string. No value set: empty string,
//    *                      which should be checked by the browser validation beforehand)
//    * For any other element, the element value attribute is returned (should be string in most, when
//    * not all, cases). For info on input types, see:
//    *   https://www.w3schools.com/Html/html_form_input_types.asp
//    */
//    var data = {};
//    var error = false;
//    var toNumber = parseFloat;
//    var toInt = parseInt;
//    var toDate = function(value){return new Date(value);}
//    var SELECT_TAG = 'select';
//    for (var elm of formElements(form)){
//        var type = elm.tagName.toLowerCase() == SELECT_TAG ? SELECT_TAG : elm.type.toLowerCase();
//        var name = elm.name;
//        var value = elm.value;
//        var required = elm.required;
//        // run browser form field validation:
//        if(!elm.checkValidity()){
//            error = error || {code: 400, message: 'Validation error', errors: []};
//            error.errors.push({domain: name, message: elm.validationMessage});
//            continue;
//        }
//        // specific cases, parsing and ignoring (if no required):
//        if (type == 'radio' && !elm.checked){
//            // in case of radios, when no selection is made, value is the value of the first radio
//            // item (at least in Chrome): first continue if element is not required:
//            if(!required){
//                continue;
//            }
//            // if required, set the value to the empty string for safety:
//            value = '';
//        }else if(type == 'select'){
//            var selected = elm.querySelectorAll('option:checked');
//            value = Array.from(selected).map((el) => el.value);
//            if(!elm.multiple){
//                value = value[0] || '';
//                if(!value && !required){
//                    continue;
//                }
//            }else{
//                // "no value set" means empty array for <select multiple>s:
//                if(!value.length && !required){
//                    continue;
//                }
//            }
//        }else if(type == 'checkbox'){
//            value = elm.checked && true;
//            if(!value && !required){
//                continue;
//            }
//        }else if(type == 'number'){
//            // do check prior to conversion, otherwise !0 = true and we might discard valid values: 
//            if(!value && !required){
//                continue;
//            }
//            value == toNumber(value);
//        }else{
//            if(!value && !required){
//                continue;
//            }
//        }
//        
//        /* else if(type == 'date'){
//            value == toDate(value);
//        }else if(type == 'time'){
//            value == toDate(value);
//        }else if(type == 'datetime-local'){
//            value == toDate(value);
//        }else if(type == 'range'){
//            value == toInt(value);
//        } */
//        data[name] = value;
//    }
//    return [data, error];
//}