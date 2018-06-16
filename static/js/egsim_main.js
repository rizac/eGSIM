var EGSIM = new Vue({
    el: '#egsim-input',
    data: {
        // NOTE: do not prefix data variable with underscore: https://vuejs.org/v2/api/#data
        avalGsims: new Map(),  // map of available gsims name -> array of gsim attributes
        avalImts: new Set(),  // set of available imts names
        selectedGsims: [],
        selectedImtsChanged: false, //for computed property (see below)
        selectedImtsSet: new Set(),
        saPeriods: '',
        typeDropdownVisible: false,
        gsimsDropdownVisible: false,
        filterText: '',
        filterType: 'GSIM name',
        filterTypes: ['GSIM name', 'IMT', 'Tectonic Region Type'],
        filterFunc: elm => true,
        loading: false,
        errors: {},  // dict of keys (fields) mapped to their message
        form: undefined //will be set in mounted()
    },
    methods: {
        showTypeDropdown: function (event) {
            this.typeDropdownVisible = true;
            this.gsimsDropdownVisible = false;
        },
        showGsimsDropdown: function (event) {
            this.typeDropdownVisible = false;
            this.gsimsDropdownVisible = true;
        },
        setFilterType: function(type){
            this.filterType = type;
            this.typeDropdownVisible = false;
            this.gsimsDropdownVisible = true;
        },
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
                var filterFunc = function(gsimName){
                    var trt = this.avalGsims.get(gsimName)[1];
                    return trt.search(regexp) > -1;
                }
            }
            this.$set(this, 'filterFunc', filterFunc);
        },
        setError(errors){
            this.$set(this, 'loading', false);
            this.$set(this, 'errors', errors);
        },
        formIsValid(){
            return isValid(this.form);
        },
        submitForm(url, onSuccess, onError=undefined){
            if (!onError){
                onError = function(arg){};
            }
            // build form data inot a dict:
            var [data, errors] = parseForm(this.form);
            if(errors){
                this.setError(errors);
                onError(errors);
            }else{
                this.$set(this, 'loading', true);
                this.$set(this, 'errors', {});
                var me = this;
                axios.post(url, data).
                    then(function (response) {
                        me.$set(me, 'loading', false);
                        if (onSuccess){
                            try{
                                onSuccess(response);
                            }catch(err){
                                console.log(`DEV. ERROR in "onSuccess" function: ${err.message}`);
                            }
                        }
                    }).catch(function (error) {
                        me.$set(me, 'loading', false);
                        me.setError.apply(me, [error]);
                        onError(errors);
                    });
            }
        }
    },
    mounted: function() { // https://stackoverflow.com/questions/40714319/how-to-call-a-vue-js-function-on-page-load
        // assign the form element to this class:
        this.$set(this,'form', document.forms["egsim-form"]);
        // fetch gsim and imts data:
        axios.post('/get_init_params', {}).then((response) => {
            //success: if using this.$http (vue ruouting):
            // [avalGsims, avalImts] = getInitData(response.body.init_data);
            // if using axios:
            [avalGsims, avalImts] = getInitData(response.data.initData);
            this.$set(this, 'avalGsims', avalGsims);
            this.$set(this, 'avalImts', avalImts);
        }).catch((error) => {
            this.errors = error
            //error
        })
    },
    watch: { // https://siongui.github.io/2017/02/03/vuejs-input-change-event/
        filterText: function(value, oldValue) {
            if (oldValue !== value){
                this.gsimsDropdownVisible = true;
                this.typeDropdownVisible = false;
                this.updateFilter();
            }
        },
        filterType: function(value, oldValue) {
            if (oldValue !== value){
                this.gsimsDropdownVisible = true;
                this.typeDropdownVisible = false;
                this.updateFilter();
            }
        }
    },
    computed: {
        hasError(){
            for(var err in this.errors){
                // no need of hasOwnProperty anymore: https://stackoverflow.com/a/45014721
                return true;
            }
            return false;
        },
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
    * Parses a given form and returns an array of two objects: [data, errors]
    * where `data` maps form element names to their *parsed* values, and `errors` maps
    * invalid form element names to their error messages (string). If the form is valid, then
    * `errors` is not an object but falsy (false/undefined/null).
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
    var errors = false;
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
            errors = errors || {};
            errors[name] = elm.validationMessage;
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
    return [data, errors];
}