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
        initdata: {},
        errormsg: '',
        selComponent: '',
        componentProps: {}
        // In case we want to use an event bus:
        // https://laracasts.com/discuss/channels/vue/help-please-how-to-refresh-the-data-of-child-component-after-i-post-some-data-on-main-component/replies/288180
    }},
    created: function(){
        // process input data (injected in the template with the minimum
        // amount possible for performance reasons):
        var [avalGsims, avalImts] = this.getInitData(this.initdata.gsims);
        var gsims = Array.from(avalGsims.keys());
        var imts = Array.from(avalImts);
        
        // set processed data:
        this.$set(this, 'componentProps', this.initdata.component_props);
        Object.keys(this.componentProps).forEach(name => {
           var compProps = this.componentProps[name];
           if (typeof compProps === 'object'){
               Object.keys(compProps).forEach(pname => {
                   var element = compProps[pname];
                   if (this.isFormObject(element)){
                       if (element.gsim){
                           element.gsim.choices = gsims;
                           element.gsim.GSIMS_MANAGER = avalGsims;
                           if (!element.gsim.val){
                               // convert null to empty list in case:
                               element.gsim.val = [];
                           }
                       }
                       if (element.imt){
                           element.imt.choices = imts;
                           element.gsim.GSIMS_MANAGER = avalGsims;
                           if (!element.imt.val){
                               // convert null to empty list in case:
                               element.imt.val = [];
                           }
                       }
                   }
               });
           }
        });
    },
    mounted: function() {
        // https://stackoverflow.com/questions/40714319/how-to-call-a-vue-js-function-on-page-load
        // no -op for the moment
    },
    methods: {
        setComponent(name){
            this.$set(this, 'selComponent', name);
            this.setUrlInBrowser(name);
        },
        setUrlInBrowser(menu){
            var location = window.location;
            var newHref = location.href.replace(/\/\w+\/*$/, "/" + menu);
            window.history.replaceState({}, document.title, newHref);
            return false; // in case accessed from within anchors
        },
        getInitData(data) {
            // initializes the base Vue instance returning the array [gsims, imts] where:
            // gsims is a Map of gsim name -> [imts (Set), trt (string), ruptureParams (Array? - not used)]
            // imts is a set of all available imts
            var gsims = new Map();
            var imts = new Set();
            for (let gsim of data) {
                var gsimName = gsim[0];
                var gImts = new Set(gsim[1]);
                for (let gImt of gImts){
                    imts.add(gImt);
                }
                var trt = gsim[2];
                gsims.set(gsimName, [gImts, trt]);
            }
            return [gsims, imts];
        },
        // this function returns a promise and is passed to each sub-component:
        post(url, data, config) { // https://stackoverflow.com/questions/40714319/how-to-call-a-vue-js-function-on-page-load
            // assign the form element to this class:
            this.setError('');
            this.setLoading(true);
            var config = Object.assign(config || {}, {headers: {"X-CSRFToken": this.csrftoken}});
            var data_ = data || {}
            var isFormObj = this.isFormObject(data);
            if (isFormObj){ // convert data_  to dict of scalars:
                data_ = {};
                for (var key of Object.keys(data)){
                    data_[key] = data[key].val;
                }
            }
            return axios.post(url, data_, config).then(response => {
                if (isFormObj){
                    for (var name of Object.keys(data)){
                        data[name].err = '';
                    }
                }
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
                return response;   // https://github.com/axios/axios/issues/1057#issuecomment-324433430
            }).finally(() => {
                this.setLoading(false);
            });
        },
        isFormObject(obj){
            if (typeof obj !== 'object'){
                return false;
            }
            return Object.keys(obj).every(key => {
                var elm = obj[key];
                return (typeof elm === 'object') && ('val' in elm) && ('err' in elm);
            });
        },
        setError(error){ // error must be a google-json dict-like {message: String, code: String, errors: Array}
            if (typeof error === 'string'){
                error = {message: error};
            }
            this.$set(this, 'errormsg', error.message);
        },
        setLoading(value){
            this.$set(this, 'loading', value);
        }
    },
    computed: {
        selComponentProps(){  // https://stackoverflow.com/a/43658979
            return this.componentProps[this.selComponent];
        }
    }
};
