/** base skeleton implementation for the base Vue instance */
var EGSIM_BASE = {
    data: function(){ return {
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
        initdata: [],
        errormsg: '',
        //fielderrors: {},
        initURL: '/get_init_params', //url for requesting the initialization data. For info:
        // https://laracasts.com/discuss/channels/vue/help-please-how-to-refresh-the-data-of-child-component-after-i-post-some-data-on-main-component/replies/288180
        eventbus: new Vue({})  // This empty Vue model will serve as our event bus.
    }},
    created: function(){
        this.eventbus.$on('selectedimts', iterable => {  // currently not used
            this.$set(this, selectedImts, new Set(iterable));
        });
        this.eventbus.$on('selectedgsims', iterable => {  // currently not used
            this.$set(this, selectedGsims, new Set(iterable));
        });
        this.eventbus.$on('postresponse', (response, isError) => {
            if (isError){
                // handle the case when we have a form validation error (response.response.data.error is a dict with error.message as prop)
                // or a general error (e.g., template not found, in which case use response.message):
                var err = (((response.response || {}).data || {}).error || response.message) || 'Unknown error';
                this.eventbus.$emit('error', err);
            }else if (response.config.url == this.initURL){
                [avalGsims, avalImts] = this.getInitData(response);
                this.$set(this, 'avalGsims', avalGsims);
                this.$set(this, 'avalImts', avalImts);
            }
        });
        this.eventbus.$on('postrequest', (url, data, config) => {
            this.post(url, data, config);
        });
        this.eventbus.$on('error', error => {
            this.setError(error);
        });
    },
    mounted: function() { // https://stackoverflow.com/questions/40714319/how-to-call-a-vue-js-function-on-page-load
        if (!this.errormsg){
            [avalGsims, avalImts] = this.getInitData(this.initdata);
            this.$set(this, 'avalGsims', avalGsims);
            this.$set(this, 'avalImts', avalImts);
        }
    },
    methods: {
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
                this.eventbus.$emit('postresponse', response, false);
            }).catch(error => {
                this.eventbus.$emit('postresponse', error, true);
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
        // https://stackoverflow.com/a/47044150
        gsims() {
            return Array.from(this.avalGsims.keys());
        },
        imts(){
            return Array.from(this.avalImts);
        },
    }
};