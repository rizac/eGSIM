/** 
 * Add global property / method / directives to Vue (https://vuejs.org/v2/guide/plugins.html) 
*/
Vue.use({
    install : function (Vue, options) {
        Vue.isEmpty = function(obj){
        	// global function returning true if `obj` is null, undefined or an empty Object
        	return (obj === null) || (obj === undefined) || ((typeof obj === 'object') && Object.keys(obj).length === 0);
        };
        Vue.isFormObject = function(obj){
        	// global function returning true if `obj` is a form Object, i.e. an Object where each of its
        	// properties is a form field name (string) mapped to the form field (Object)
            if (typeof obj !== 'object'){
                return false;
            }
            // check if all form fields have two mandatory properties of the Object: val and err (there are more,
            // but the two above are essential)
            return Object.keys(obj).every(key => {
                var elm = obj[key];
                return (typeof elm === 'object') && ('value' in elm) && ('error' in elm);
            });
        };
	    Vue.createPostFunction = function(root, defaultAxiosConfig){
	    	// creates a globally available POST function using axios, and notifying the
	    	// root instance. This function is called from egsim.html after creation of the main Vue instance
	    	Vue.post = (url, data, config) => {
		    	/**
	             * Perform a POST request. `Vue.post` can be called from any component and
	             * returns a promise which can be chained with .then(response) and .catch(response)
	             * where response is the axios response object. The function emits events on the root
	             * instance passed above, to control visual stuff (e.g., progress bar while fetching,
	             * display of errors)
	             * 
	             * @param url: string of the url
	             * @param data: any data (usually Object) to be sent as POST body. This might include the "form" objects
	             *     in the form {field1: {err: '', val: V1, ... }, ..., fieldn: {err: '', val: Vn, ... }}
	             *     In this case, 1. the Object sent will be of the form {field1: V1, ... fieldn: Vn} and
	             *                   2. the fields errors ('err') will be set in case of form validation errors returned from the server
	             * @param config: any data (Object) for configuring the POST request
	             */
	            // emit the starting of a POST:
	            root.$emit('postRequestStarted');
	            var config = Object.assign(config || {}, defaultAxiosConfig);  // Object.assign(target, source)
	            // guess if we passed a form data object, and in case convert it to a JSONizable Object:
	            var jsonData = data || {};
	            var isFormObj = Vue.isFormObject(data);  // see above
	            if (isFormObj){  // data is a Form Object, convert jsonData  to dict of scalars:
	                jsonData = {};
	                for (var key of Object.keys(data)){
	                	data[key].error = '';  // initialize error
	    	            if (!data[key].disabled){
    	    	            jsonData[data[key].name] = data[key].value;  // assign value to object up to be sent
	    	            }
	                }
	            }
	            return axios.post(url, jsonData, config).then(response => {
	            	root.$emit('postRequestCompleted', url, data, config, response);
	                // allow chaining this promise from sub-components:
	                return response;  // https://github.com/axios/axios/issues/1057#issuecomment-324433430
	            }).catch(response => {
	            	root.$emit('postRequestFailed', url, data, config, response);
	                // allow chaining this promise from sub-components:
	                throw response;   // https://www.peterbe.com/plog/chainable-catches-in-a-promise
	            }).finally(() => {
		            root.$emit('postRequestEnded');
	            });
	    	}
	    }
    }
});
