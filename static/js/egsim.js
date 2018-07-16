var EGSIM = new Vue({
    el: '#egsim-vue',
    data: {
        // NOTE: do not prefix data variable with underscore: https://vuejs.org/v2/api/#data
        // csrf token stored in an <input> in the base.html. Get it here and use it for each post request:
        csrftoken: Object.freeze(document.querySelector("[name=csrfmiddlewaretoken]").value),
        // form: {classes: {}, visible:true, modal:false}, //a vuejs dict of props to be set to the main form
        avalGsims: new Map(),  // map of available gsims name -> array of gsim attributes
        avalImts: new Set(),  // set of available imts names
        selectedGsims: [],
        selectedImts: [],
        data: {},
        loading: false,
        errormsg: '',
        fielderrors: {},
        initURL: '/get_init_params', //url for requesting the initialization data. For info:
        // 
        // https://laracasts.com/discuss/channels/vue/help-please-how-to-refresh-the-data-of-child-component-after-i-post-some-data-on-main-component/replies/288180
        eventbus: new Vue({})  // This empty Vue model will serve as our event bus.
    },
    created: function(){
        this.eventbus.$on('selectedimts', iterable => {  // currently not used
            this.$set(this, selectedImts, new Set(iterable));
        });
        this.eventbus.$on('selectedgsims', iterable => {  // currently not used
            this.$set(this, selectedGsims, new Set(iterable));
        });
        this.eventbus.$on('postresponse', (response, isError) => {
            if (isError){
                this.eventbus.$emit('error', response.response.data.error);
            }else if (response.config.url == this.initURL){
                [avalGsims, avalImts] = getInitData(response.data.initData);
                this.$set(this, 'avalGsims', avalGsims);
                this.$set(this, 'avalImts', avalImts);
            }
        });
        this.eventbus.$on('postrequest', (url, data, config) => {
            this.post(url, data, config);
        });
        this.eventbus.$on('error', (error) => {
            this.setError(error);
        });
    },
    mounted: function() { // https://stackoverflow.com/questions/40714319/how-to-call-a-vue-js-function-on-page-load
        this.post(this.initURL, {}, {});
    },
    methods: {
        post(url, data, config) { // https://stackoverflow.com/questions/40714319/how-to-call-a-vue-js-function-on-page-load
            // assign the form element to this class:
            this.setError('');
            this.setLoading(true);
            var config = Object.assign(config || {}, {headers: {"X-CSRFToken": this.csrftoken}});
            // fetch gsim and imts data:
            return axios.post(url, data || {}, config).then(response => {
                this.eventbus.$emit('postresponse', response, false);
            }).catch((error) => {
                this.eventbus.$emit('postresponse', response, true);
            }).finally(()=>{
                this.setLoading(false);
            });
        },
        setError(error){ // error must be a google-json dict-like {message: String, code: String, errors: Array}
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
        }
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
});


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
