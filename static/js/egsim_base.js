/** base skeleton implementation for the base Vue instance. Also implements
 Vue.post global function (see page bottom)
 */
var EGSIM_BASE = {
    data: function(){ return {
        // NOTE: do not prefix data variable with underscore: https://vuejs.org/v2/api/#data
        loading: false,
        errormsg: '',
        selComponent: '',
        // FIXME: IMPLEMENT PROPS FOR DEFAULT VARIABLES?
        // gsims: {}, // an Object of gsim names (string) mapped to [[... imts ...], trt, oq_gsim_warning] (all elements strings)
        componentProps: {}, // an object of Objects keyed by each string denoting a component name (<=> menu tab)
        postfuncDefaultConfig: {}  // default config used in Vue.post. FIXME: better doc
        // In case we want to use an event bus:
        // https://laracasts.com/discuss/channels/vue/help-please-how-to-refresh-the-data-of-child-component-after-i-post-some-data-on-main-component/replies/288180
    }},
    created: function(){
        // Use regular expression to convert Gsim names to readable names:
        // (Note: Safari does not support lookbehind/ ahead, keep it simple!):
        var reg = /[A-Z]+[^A-Z0-9]+|[0-9]+|.+/g;
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
                warning: warning || "",
            }
        });
        var regionalization = this.regionalization;
        // set processed data:
        for (var [name, form] of this.forms()){
            if (form.gsim){
                // set form.gsim.choices as a deep copy of gsimObjects:
                form.gsim.choices = gsimObjects.map(elm => Object.assign({}, elm));
                form.gsim.regionalization = {
                    url: regionalization.url,
                    choices: regionalization.names.map(elm => [elm, elm]),
                    value: Array.from(regionalization.names)
                }
            }
            if (form.imt){
                // set form.imt as a deep copy of imts:
                form.imt.choices = Array.from(imts);
            }
        }
        // Create a global function `Vue.post(url, data, config)`:
        Vue.createPostFunction(this, this.postfuncDefaultConfig);
        // `this` is now a listener for `Vue.post`, attach relative events callbacks:
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
         * POST request listeners (see Vue.post below for details):
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
            if (this.isFormObject(data)){
                var errors = error.errors || [];
                for (var err of errors){
                    var paramName = err.location;
                    if (paramName && (paramName in data)){
                        data[paramName].error = err.message || 'invalid: unknown error';
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
                       if (this.isFormObject(element)){
                           ret.push([name, element]);
                       }
                   });
               }
            });
            return ret;
        },
        isFormObject(obj){
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
        },
        setError(error){
            this.errormsg = error;
        },
        setLoading(value){
            this.loading = value;
        }
    }
};


/**
 * Add global property / method / directives to Vue (https://vuejs.org/v2/guide/plugins.html)
*/
Vue.use({
    install : function (Vue, options) {
        Vue.isEmpty = function(obj){
            // global function returning true if `obj` is null, undefined or an empty Object
            return (obj === null) || (obj === undefined) || ((typeof obj === 'object') && Object.keys(obj).length === 0);
        };
        Vue.createPostFunction = function(root, defaultAxiosConfig){
            /* creates a globally available `Vue.post` function using axios

            Parameters:
            defaultAxiosConfig: an Object with default config for axios
            root: The root Vue instance or component that will listen for the POST
                events (before request, request ended, request failed) in order to e.g.,
                control progress bars display request errors.
            */
            Vue.post = (url, data, config) => {
                /*
                 Global function that can be called from any Vue instance or component
                 performing a request and returning a `Promise` which can be chained with
                 `.then(response)` and `.catch(response)` (`response` is the axios
                 response object).
                 See `axios.post(url, data, config)` for details

                 Parameters:
                 url: string of the url
                 data: the request POST data (e.g. JSON serialzable Object)
                 config: any data (Object) for configuring the POST request. Defaults
                    to the default config passed (see `createPostFunction` above)
                 */
                // emit the starting of a POST:
                root.$emit('postRequestStarted');
                // merge passed config with default config in a new config Object:
                var config = Object.assign(config || {}, defaultAxiosConfig);
                var jsonData = data || {};
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
        },
        Vue.download = function(url, postData){
            /**
             Send a `Vue.post` request and download the response data on the client OS.

             The responses attributes 'content-disposition' ('attachment; filename=...')
             and 'content-type' must be specified.

             Those two attributes are enough ONLY for GET requests opened in a new tab or
             window, but with AJAX POST requests (as in our case) the response is received
             but no "save as" dialog pops up. Hence, the workaround implemented here.
             */

            // the post function needs to have the 'responseType' set in order
            // to work with `window.URL.createObjectURL` (info extracted from the "messy":

            Vue.post(url, postData, {responseType: 'arraybuffer'}).then(response => {
                // ref on `responseType` above (long thread with several outdated hints):
                // https://stackoverflow.com/questions/8022425/getting-blob-data-from-xhr-request
                if (response && response.data){
                    var filename = (response.headers || {})['content-disposition'];
                    if (!filename){ return; }
                    var iof = filename.indexOf('filename=');
                    if (iof < 0){ return; }
                    filename = filename.substring(iof + 'filename='.length);
                    if (!filename){ return; }
                    var ctype = (response.headers || {})['content-type'];
                    Vue.save(response.data, filename, ctype);
                }
            });
        },
        Vue.saveAsJSON = function(data, filename){
            /**
             Save the given JavaScript Object `data` on the client OS as JSON
             formatted string

             Parameters:
             data: the JavaScript Object or Array to be saved as JSON
             */
            var sData = JSON.stringify(data, null, 2);  // 2 -> num indentation chars
            Vue.download(sData, filename, "application/json");
        },
        Vue.save = function(data, filename, mimeType){
            /**
             Saves data with the given filename and mimeType on the client OS

             Parameters:
                data: a Byte-String (e.g. JSOn.stringify) or an ArrayBuffer
                    (https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/ArrayBuffer)
                filename: the string that is used as default name in the save as dialog
                mimeType: s atring denoting the MIME type
                     (https://developer.mozilla.org/en-US/docs/Web/HTTP/Basics_of_HTTP/MIME_types/Complete_list_of_MIME_types)
             */
            var blob = new Blob([data], {type: mimeType});
            var downloadUrl = window.URL.createObjectURL(blob);
            var downloadAnchorNode = document.createElement('a');
            downloadAnchorNode.setAttribute("href", downloadUrl);
            downloadAnchorNode.setAttribute("download", filename);
            document.body.appendChild(downloadAnchorNode); // required for firefox
            downloadAnchorNode.click();
            downloadAnchorNode.remove();
            // as we removed the node, we should have freed up memopry,
            // but let's be safe:
            URL.revokeObjectURL( downloadUrl );
        },
        Vue.createDownloadActions = function(downloadUrl, data){
            /* Return an Array of for downloading on the client OS) the given data.
            The returned Array has elements of the form `[format, download_callback]`,
            where format is 'json' 'csv', 'csv (comma separated)'. See <plot-div> and
            <testing-table> components for details

             Parameters:
              downloadUrl: a string identifying a download url, usually sent from the server
              data: the data returned from a response (e.g., trellis residuals or
                testing data) that needs to be downloaded
            */
            // Populate with the data to be downloaded as non-image formats:
            var downloadActions = [];
            // Download as JSON does not need to query the server, the data is here:
            downloadActions.push(["json", () => {
                var filename =  downloadUrl.split('/').pop() + '.json';
                Vue.saveAsJSON(data, filename);
            }]);
            // CSV download actions send data to the server and expects back converted:
            downloadActions.push(["text/csv", () => {
                var url =  downloadUrl + '.csv';
                Vue.download(url, data);
            }]);
            downloadActions.push(["text/csv, decimal comma", () => {
                var url =  downloadUrl + '.csv_eu';
                Vue.download(url, data);
            }]);
            return downloadActions;
        }
    }
});
