/** base skeleton implementation for the base Vue instance */
var EGSIM_BASE = {
    data: function(){ return {
        // NOTE: do not prefix data variable with underscore: https://vuejs.org/v2/api/#data
        // csrf token stored in an <input> in the base.html. Get it here and use it for each post request:
        csrftoken: Object.freeze(document.querySelector("[name=csrfmiddlewaretoken]").value),
        // form: {classes: {}, visible:true, modal:false}, //a vuejs dict of props to be set to the main form
        // selectedGsims: [],
        // selectedImts: [],
        forms: {},  // a dict of urls mapped to an Object of field names -> {val: Object, err:''}
        loading: false,
        initdata: {},
        errormsg: '',
        selComponent: '',
        componentProps: {}
        // In case we want to use an event bus:
        // https://laracasts.com/discuss/channels/vue/help-please-how-to-refresh-the-data-of-child-component-after-i-post-some-data-on-main-component/replies/288180
    }},
    created: function(){
        // configure listeners:
        this.$on('error', error => {
            this.setError(error);
        });
        this.$on('postrequest', (url, data, config) => {
            this.post(url, data, config);
        });
        
        // process input data (injected in the template with the minimum
        // amount possible for performance reasons):
        var [avalGsims, avalImts] = this.getInitData(this.initdata.gsims);
        var gsims = Array.from(avalGsims.keys());
        var imts = Array.from(avalImts);
        
        // set processed data:
        this.$set(this, 'componentProps', this.initdata.component_props);
        var forms = {};
        Object.keys(this.componentProps).forEach(name => {
           var element = this.componentProps[name];
           if (element.form){
               if (element.url){
                   forms[element.url] = element.form;
               }
               if (element.form.gsim){
                   element.form.gsim.choices = gsims;
                   element.form.gsim.GSIMS_MANAGER = avalGsims;
                   if (!element.form.gsim.val){
                       element.form.gsim.val = [];
                   }else if (element.form.gsim.val === '__all__'){
                       element.form.gsim.val = gsims;  // need to copy?
                   }
               }
               if (element.form.imt){
                   element.form.imt.choices = imts;
                   element.form.gsim.GSIMS_MANAGER = avalGsims;
                   if (!element.form.imt.val){
                       element.form.imt.val = [];
                   }else if (element.form.gsim.val === '__all__'){
                       element.form.imt.val = imts;  // need to copy?
                   }
               }
           } 
        });
        this.$set(this, 'forms', forms);
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
        post(url, data, config) { // https://stackoverflow.com/questions/40714319/how-to-call-a-vue-js-function-on-page-load
            // assign the form element to this class:
            this.setError('');
            this.setLoading(true);
            var config = Object.assign(config || {}, {headers: {"X-CSRFToken": this.csrftoken}});
            // fetch gsim and imts data:
            return axios.post(url, data || {}, config).then(response => {
                this.$emit('postresponse', response, false);
            }).catch(response => {
                // set the data field errors:
                var url = response.config.url;
                if (url in this.forms){
                    var form = this.forms[url];
                    var errors = error.errors || [];
                    var fielderrors = {};
                    for (var err of errors){
                        if (err.domain){
                            form[err.domain].err = err.message || 'unknown error';
                        }
                    }
                }
                // set the global error message:
                var err = (((response.response || {}).data || {}).error || response.message) || 'Unknown error';
                this.setError(err);
            }).finally(() => {
                this.setLoading(false);
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
