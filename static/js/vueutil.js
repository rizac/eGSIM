/** 
 * Add global property / method / directives to Vue (https://vuejs.org/v2/guide/plugins.html) 
*/
Vue.use({
    install : function (Vue, options) {
    	// defines ColorMap class extensing Map and retrievable via Vue.colorMap() (see below):
        class ColorMap extends Map {
            constructor() {
                super();
                this._defaults = {
                        index: 0,
                        colors: [
                        	'#1f77b4',  // muted blue
                            '#ff7f0e',  // safety orange
                            '#2ca02c',  // cooked asparagus green
                            '#d62728',  // brick red
                            '#9467bd',  // muted purple
                            '#8c564b',  // chestnut brown
                            '#e377c2',  // raspberry yogurt pink
                            '#7f7f7f',  // middle gray
                            '#bcbd22',  // curry yellow-green
                            '#17becf'   // blue-teal
                        ]
                }
            }
            get(key){
            	// sets a color mapping `key` if `key` is not in this Map
            	// (the color will be set incrementally based on `this._defauls.colors`).
            	// Eventually, it returns the color (hex string) mapped to `key`, as the superclass does
                var color = super.get(key);
                if (color === undefined){
                    var colors = this._defaults.colors;
                    color = colors[(this._defaults.index++) % colors.length];
                    this.set(key, color);
                }
                return color;
            }
            transparentize(hexcolor, alpha) {
                // Returns the corresponding 'rgba' string of `hexcolor` with the given alpha channel ( in [0, 1], 1:opaque)
                // If `hexcolor` is an integer, it indicates the index of the default color to be converted
                if (typeof hexcolor == 'number'){
                    hexcolor = this._defaults.colors[parseInt(hexcolor) % this._defaults.colors.length];
                }
                if (hexcolor.length == 4){
                    var [r, g, b] = [hexcolor.substring(1, 2), hexcolor.substring(2, 3), hexcolor.substring(3, 4)];
                    var [r, g, b] = [r+r, g+g, b+b];
                }else if(hexcolor.length == 7){
                    var [r, g, b] = [hexcolor.substring(1, 3), hexcolor.substring(3, 5), hexcolor.substring(5, 7)];
                }else{
                    return hexcolor;
                }
                var [r, g, b] = [parseInt(r, 16), parseInt(g, 16), parseInt(b, 16)];
                return `rgba(${r}, ${g}, ${b}, ${alpha})`;
            }
        };
        Vue.colorMap = function () {
            return new ColorMap();
        };
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
                return (typeof elm === 'object') && ('val' in elm) && ('err' in elm);
            });
        };
        Vue.init = function(data){
        	// Creates the globally available
        	// Vue.eGSIM Object via the data passed from the server via Django (see egsim.html)
	        var gsims = data;
	        // data is an Array of Arrays: each Array element represents a GSIM:
	        // [gsimName, [imtName1, ... imtNameN], gsimOpenQuakeWarning]
	        var gsimNames = Object.keys(gsims).sort();
	        var imtNames = new Set();
	        gsimNames.forEach(gsimName => {
	        	gsims[gsimName][0].forEach(imt => imtNames.add(imt));
	        });
	        // create the globally available Vue.eGSIM variable:
	        Vue.eGSIM = {
	        	gsims: gsimNames,
	            imts: Array.from(imtNames),
	        	imtsOf: function(gsim){ return gsims[gsim][0]; },
				warningOf: function(gsim){ return gsims[gsim][2]; }
	        }
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
	            if (isFormObj){ // data is a Form Object, convert jsonData  to dict of scalars:
	                jsonData = {};
	                for (var key of Object.keys(data)){
	                	data[key].err = '';  // initialize error
	    	            if (!data[key].is_hidden){
    	    	            jsonData[data[key].attrs.name] = data[key].val;  // assign value to object up to be sent
//		                    jsonData[key] = data[key].val;  // assign value to object up to be sent
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
