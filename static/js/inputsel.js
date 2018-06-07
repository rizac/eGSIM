new Vue({
    el: '#inputsel',
    data: {
        // NOTE: do not prefix data variable with underscore: https://vuejs.org/v2/api/#data
        avalGsims: new Map(),  // map of available gsims name -> array of gsim attributes
        avalImts: new Set(),  // set of available imts names
        selectedGsims: [],
        selectedImts: [],
        saPeriods: '',
        typeDropdownVisible: false,
        gsimsDropdownVisible: false,
        filterText: '',
        filterType: 'GSIM name',
        filterTypes: ['GSIM name', 'IMT', 'Tectonic Region Type'],
        filterFunc: elm => true
    },
    methods: {
        showTypeDropdown: function (event) {
            this.typeDropdownVisible = true;
            this.gsimsDropdownVisible = false;
        },
        showGsimsDropdown: function (event) {
            this.typeDropdownVisible = false;
            this.gsimsDropdownVisible = true;
        },
        setFilterType: function(type){
            this.filterType = type;
            this.typeDropdownVisible = false;
            this.gsimsDropdownVisible = true;
        },
        isImtSelectable(imt) {
            if (!this.selectedGsims.length){
                return false;
            }
            for (let gsim of this.selectedGsims){
                var selectableImts = this.avalGsims.get(gsim)[0];
                if (!selectableImts.has(imt)){
                    return false;
                }
            }
            return true;    
        },
        isGsimVisible(gsim){
            return this.filterFunc(gsim);
        },
        updateFilter(){
            var regexp = this.filterText ? new RegExp(this.filterText.replace(/\*/g, '.*').replace(/\?/g, '.'), 'i') : undefined;
            var filterFunc = elm => true;
            if (this.filterType == this.filterTypes[0]){
                var filterFunc = function(gsimName){
                    return gsimName.search(regexp) > -1;
                }
            }else if (this.filterType == this.filterTypes[1]){
                var filterFunc = function(gsimName){
                    if (gsimName.startsWith('AlNomanC')){
                        var fg = 9;
                    }
                    var imts = this.avalGsims.get(gsimName)[0];
                    for (let imt of imts){
                        if (imt.search(regexp) > -1){
                            return true;
                        }
                    };
                    return false;
                }
            }else if (this.filterType == this.filterTypes[2]){
                var filterFunc = function(gsimName){
                    var trt = this.avalGsims.get(gsimName)[1];
                    return trt.search(regexp) > -1;
                }
            }
            this.$set(this, 'filterFunc', filterFunc);
        }
    },
    mounted: function() { // https://stackoverflow.com/questions/40714319/how-to-call-a-vue-js-function-on-page-load
        this.$http.post('/get_init_params', {}).then((response) => {
            //success
            [avalGsims, avalImts] = getInitData(response.body.init_data);
            this.$set(this, 'avalGsims', avalGsims);
            this.$set(this, 'avalImts', avalImts);
        }, (response) => {
            //error
        })
    },
    watch: { // https://siongui.github.io/2017/02/03/vuejs-input-change-event/
        filterText: function(value, oldValue) {
            if (oldValue !== value){
                this.gsimsDropdownVisible = true;
                this.typeDropdownVisible = false;
                this.updateFilter();
            }
        },
        filterType: function(value, oldValue) {
            if (oldValue !== value){
                this.gsimsDropdownVisible = true;
                this.typeDropdownVisible = false;
                this.updateFilter();
            }
        }
    },
    computed: {
        // https://stackoverflow.com/a/47044150
        gsims() {
            return Array.from(this.avalGsims.keys());
        },
        imts(){
            return Array.from(this.avalImts);
        }
    }
})


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