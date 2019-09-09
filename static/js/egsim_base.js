/** base skeleton implementation for the base Vue instance */
var EGSIM_BASE = {
    data: function(){ return {
        // NOTE: do not prefix data variable with underscore: https://vuejs.org/v2/api/#data
        loading: false,
        errormsg: '',
        selComponent: '',
        gsims: {}, // an Object of gsim names (string) mapped to [[... imts ...], trt, oq_gsim_warning] (all elements strings)
        componentProps: {}, // an object of Objects keyed by each string denoting a component name (<=> menu tab)
        postfuncDefaultConfig: {}  // default config used in Vue.post. See egsim.html and vueutils.js
        // In case we want to use an event bus:
        // https://laracasts.com/discuss/channels/vue/help-please-how-to-refresh-the-data-of-child-component-after-i-post-some-data-on-main-component/replies/288180
    }},
    created: function(){
        var gsimNames = Vue.eGSIM.gsims;  // defined in vueutil.js
        var imtNames = Vue.eGSIM.imts;  // defined in vueutil.js
        // set processed data:
        for (var [name, form] of this.forms()){
        	if (form.gsim){
               	form.gsim.choices = gsimNames;
           	}
           	if (form.imt){
            	form.imt.choices = imtNames;
        	}
        	// set disabled element in attrs if not present:
        	// (use $set to make the property reactive)
        	// and the initial value
        	for (var key of Object.keys(form)){
        		if (form[key].attrs && !('disabled' in form[key].attrs)){
        			this.$set(form[key].attrs, 'disabled', false);
        		}
        		// set the initial value as the current value of the field.
        		// The 'initial' value (`form[key].initial`) is the Django initial value, which
        		// might be None/null (which means "initial value not set"). As null might be invalid
        		// (e.g. <select multiple> need an empty Array instead) we write here the initial value
        		// as the value currently hold in the field:
        		form[key].initial = form[key].val;
        	}
        }
        // in `vueutils.js` we defined a POST function which emits the following events
        // on this instance. Create the POST function and event notifiers attached to this object
        Vue.createPostFunction(this, this.postfuncDefaultConfig);
        // and now listen for the just created event notifiers:
        this.$on('postRequestStarted', this.postRequestStarted);
        this.$on('postRequestCompleted', this.postRequestCompleted);
        this.$on('postRequestFailed', this.postRequestFailed);
        this.$on('postRequestEnded', this.postRequestEnded);
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
        /*
         * POST request listeners:
         */
        postRequestStarted(){
        	this.setError('');
            this.setLoading(true);
        },
        postRequestCompleted(url, data, config, response){ /* no-op*/ },
        postRequestFailed(url, data, config, response){
        	var errorMessage = response.message ||  'Unknown error';
        	var errData = (response.response || {}).data;
        	if (errData instanceof ArrayBuffer){
        		// sometimes we might want to download png and json, we then
        		// need to return an ArrayBuffer (see download.js).
        		// The ArrayBuffer might "hide" a JSON formatted string. Thus,
        		// try to convert to string and then json.parse:
        		try{
        			// copied from: https://developers.google.com/web/updates/2012/06/How-to-convert-ArrayBuffer-to-and-from-String
        			// Uint8 because we send data as UTF8
        			errData = JSON.parse(String.fromCharCode.apply(null, new Uint8Array(errData)));
        		}catch(exc){
        			errData = {};
        		}
        	}
        	var error = (errData || {}).error || {};
        	// set the data field errors:
            if (Vue.isFormObject(data)){  // defined in vueutils.js
                var errors = error.errors || [];
                for (var err of errors){
                    if (err.domain && (err.domain in data)){
                        data[err.domain].err = err.message || 'invalid: unknown error';
                    }
                }
            }
            // set the global error message:
            this.setError(error.message || errorMessage);
        },
        postRequestEnded(){
        	this.setLoading(false);
        },
        /*
         * Components event handlers:
         */
        handleEmittedEvent(eventName){
        	if (eventName == 'movetoapidoc'){
        		this.moveToApidoc(arguments[1] || '');
        	}else if (eventName == 'selectgsims'){
        		this.selectGsims(arguments[1] || []);
        	} 
        },
        moveToApidoc(fragmentName){
        	this.componentProps['apidoc'].fragment = fragmentName.startsWith('#') ? fragmentName : '#' + fragmentName;
        	this.setComponent('apidoc');
        },
        selectGsims(gsims){
        	for (var [name, form] of this.forms()){
        		if (form.gsim){
                	form.gsim.val = Array.from(gsims);
                }
        	}
        },
        /* other functions: */
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
        setError(error){
            this.errormsg = error;
        },
        setLoading(value){
            this.loading = value;
        }
    }
};
