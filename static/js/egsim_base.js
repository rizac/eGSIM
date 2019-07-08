/** base skeleton implementation for the base Vue instance */
var EGSIM_BASE = {
    data: function(){ return {
        // NOTE: do not prefix data variable with underscore: https://vuejs.org/v2/api/#data
        // csrf token stored in an <input> in the base.html. Get it here and use it for each post request:
        csrftoken: Object.freeze(document.querySelector("[name=csrfmiddlewaretoken]").value),
        // form: {classes: {}, visible:true, modal:false}, //a vuejs dict of props to be set to the main form
        // selectedGsims: [],
        // selectedImts: [],
        loading: false,
        errormsg: '',
        selComponent: '',
        gsims: {}, // an Object of gsim names (string) mapped to [[... imts ...], trt, oq_gsim_warning] (all elements strings)
        componentProps: {} // an object of Objects keyed by each string denoting a component name (<=> menu tab)
        // In case we want to use an event bus:
        // https://laracasts.com/discuss/channels/vue/help-please-how-to-refresh-the-data-of-child-component-after-i-post-some-data-on-main-component/replies/288180
    }},
    created: function(){
        var gsims = this.gsims;
        var gsimNames = Object.keys(gsims).sort();
        var imtNames = new Set();
        gsimNames.forEach(gsimName => {
        	gsims[gsimName][0].forEach(imt => imtNames.add(imt));
        });
        imtNames = Array.from(imtNames);
        var gsimManager = {
        	imtsOf: function(gsim){ return gsims[gsim][0]; },
			trtOf: function(gsim){ return gsims[gsim][1]; },
			warningOf: function(gsim){ return gsims[gsim][2]; }	
        }
        // set processed data:
        for (var [name, form] of this.forms()){
        	if (form.gsim){
               	form.gsim.choices = gsimNames;
               	form.gsim.gsimManager = gsimManager;
           	}
           	if (form.imt){
            	form.imt.choices = imtNames;
            	form.gsim.gsimManager = gsimManager;
        	}
        	// set disabled element in attrs if not present:
        	// (use $set to make the property reactive)
        	// and the initial value
        	for (var key of Object.keys(form)){
        		if (form[key].attrs && !('disabled' in form[key].attrs)){
        			this.$set(form[key].attrs, 'disabled', false);
        		}
        		// set the initial value as the current value of the field.
        		// The 'initial' value is the Django initial value, but might be None
        		// (which means "initial value not set"). Here, we want to use the initial
        		// value when we want the form to be "restored to defaults", i.e.
        		// `form[key].val = form[key].initial`.
        		// To make the latter a valid operation, we must be sure that ` form[key].initial`
        		// is valid. As `form[key].val` IS valid and it's actually the default to be restored:
        		form[key].initial = form[key].val;
        	}
        }
    },
    computed: {
        selComponentProps(){  // https://stackoverflow.com/a/43658979
            return this.componentProps[this.selComponent];
        }
    },
    mounted: function() {
        // https://stackoverflow.com/questions/40714319/how-to-call-a-vue-js-function-on-page-load
        // no -op for the moment
    },
    methods: {
        setComponent(name){
            this.selComponent = name;
            this.setUrlInBrowser(name);
        },
        setUrlInBrowser(menu){
            var location = window.location;
            if (!location.pathname.startsWith(`/${menu}`)){
            	var newHref = `${location.origin}/${menu}`
            	// https://developer.mozilla.org/en-US/docs/Web/API/History_API
            	window.history.replaceState({}, document.title, newHref);
            }
            return false; // in case accessed from within anchors
        },
        moveToApidoc(fragmentName){
        	this.componentProps['apidoc'].fragment = fragmentName.startsWith('#') ? fragmentName : '#' + fragmentName;
        	this.setComponent('apidoc');
        },
        // this function returns a promise and is passed to each sub-component:
        post(url, data, config) { // https://stackoverflow.com/questions/40714319/how-to-call-a-vue-js-function-on-page-load
            /** 
             * Perform a POST request. Returns a promise which can be chained with .then(response) and .catch(response)
             * where response is the axios response object
             * 
             * @param url: string of the url
             * @param data: any data (usually Object) to be sent as POST body. This might include the "form" objects
             *      in the form {field1: {err: '', val: V1, ... }, ..., fieldn: {err: '', val: Vn, ... }}
             *      In this case, 1. the Object sent will be of the form {field1: V1, ... fieldn: Vn} and
             *                    2. the fields errors ('err') will be set in case of form validation errors returned from the server
             * @param config: any data (Object) for configuring the POST request
             */ 
            // assign the form element to this class:
            this.setError('');
            this.setLoading(true);
            var config = Object.assign(config || {}, {headers: {"X-CSRFToken": this.csrftoken}});
            var jsonData = data || {};
            var isFormObj = Vue.isFormObject(data);  // defined in vueutil.js
            if (isFormObj){ // data is a Form Object, convert jsonData  to dict of scalars:
                jsonData = {};
                for (var key of Object.keys(data)){
                	data[key].err = '';  // initialize error
    	            if (!data[key].is_hidden){
	                    jsonData[key] = data[key].val;  // assign value to object up to be sent
    	            }
                }
            }
            return axios.post(url, jsonData, config).then(response => {
                // allow chaining this promise from sub-components:
                return response;  // https://github.com/axios/axios/issues/1057#issuecomment-324433430
            }).catch(response => {
                var error = (((response.response || {}).data || {}).error || response.message) || 'Unknown error';
                // set the data field errors:
                if (isFormObj){
                    var errors = error.errors || [];
                    for (var err of errors){
                        if (err.domain && (err.domain in data)){
                            data[err.domain].err = err.message || 'invalid: unknown error';
                        }
                    }
                }
                // set the global error message:
                this.setError(error);
                // allow chaining this promise from sub-components:
                throw response;   // https://www.peterbe.com/plog/chainable-catches-in-a-promise
            }).finally(() => {
                this.setLoading(false);
            });
        },
        selectGsims(gsims){
        	for (var [name, form] of this.forms()){
        		if (form.gsim){
                	form.gsim.val = Array.from(gsims);
                }
        	}
        },
        clearErrors(){
        	this.setError('');
        	// clear all errors in forms:
        	// set processed data:
        	for (var [name, form] of this.forms()){
        		Object.keys(form).forEach(fieldname => {
        	        form[fieldname].err = '';
        	    });
        	}
        },
        forms(){
        	var ret = [];
        	Object.keys(this.componentProps).forEach(name => {
	           var compProps = this.componentProps[name];
	           if (typeof compProps === 'object'){
	               Object.keys(compProps).forEach(pname => {
	                   var element = compProps[pname];
	                   if (Vue.isFormObject(element)){  // defined in vueutil.js
	                       ret.push([name, element]);
	                   }
	               });
	           }
	        });
	        return ret;
        },
        setError(error){ // error must be a google-json dict-like {message: String, code: String, errors: Array}
            if (typeof error === 'string'){
                error = {message: error};
            }
            this.errormsg = error.message;
        },
        setLoading(value){
            this.loading = value;
        }
    }
};
