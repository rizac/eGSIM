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
        // Use regular expression to convert Gsim names to readable names by
        // splitting into space-separated tokens (in the following order of importance):
        // [A-Z]+[a-z]+ e.g. "Akkar" "BNCLower"
        // (?<!_)[0-9]+(?!_)  e.g. "2006" but not "2006_"
        // [A-Z_]+ or [a-z_]+ e.g. "ABC" "abc"
        // .* anything else returned as single token, e.g., "b2006_g"
        var reg = /[A-Z]+[a-z]+|(?<!_)[0-9]+(?!_)|[A-Z_]+|[a-z_]+|.+/g;
        // converts the gsims received from server from an Array of Arrays to an
        // Array of Objects:
        var imts = [];
        var gsimObjects = this.gsims.map(elm => {
            var [gsimName, imts_, warning] = elm;
            // add imt:
            imts_.map(imt => {
                if (!imts.includes(imt)){
                    imts.push(imt);
                }
            });
            return {
                value: gsimName,
                disabled: false,
                // innerHTML (the display name) is gsimName with spaces: split
                // according to Camel Case words, or numbers, the rest (.*)
                // keep it together:
                innerHTML: gsimName.match(reg).join(" "),
                imts: imts_,
                warning: warning || ""
            }
        });
        // set processed data:
        for (var [name, form] of this.forms()){
        	if (form.gsim){
        	    // set form.gsim.choices as a deep copy of gsimObjects:
               	form.gsim.choices = gsimObjects.map(elm => Object.assign({}, elm));
           	}
           	if (form.imt){
           	    // set form.imt as a deep copy of imts:
            	form.imt.choices = Array.from(imts);
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
