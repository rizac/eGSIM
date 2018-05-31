new Vue({
    el: '#inputsel',
    data: {
        // NOTE: do not prefix data variable with underscore: https://vuejs.org/v2/api/#data
        avalGsims: new Map(),  // map of available gsims name -> array of gsim attributes
        avalImts: new Set(),  // set of available imts names
        temporarySelectedGsims: [],
        selGsims: new Set(),
        selImts: new Set(),
        typeDropdownVisible: false,
        gsimsDropdownVisible: true,
        filterText: '',
        filterTypes: ['GSIM name', 'IMT', 'Tectonic Region Type'],
        filterType: 'GSIM name'
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
            if (!this.selGsims.size){
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
        unselectGsim(gsim){
            // this.selGsims must be a new Set at the end of this method.
            // This way the property will be updated in the view
            var _tmpSel = new Set();    
            for (let gsim_ of this.selGsims){
                if (gsim_ != gsim){
                    _tmpSel.add(gsim_);
                }
            }
            this._setGsimSelection(_tmpSel);
        },
        selectGsims(clearSelectionFirst){
            // this.selGsims must be a new Set at the end of this method.
            // This way the property will be updated in the view
            var _tmpSel = new Set(this.temporarySelectedGsims);
            if (!clearSelectionFirst){
                for (let gsim of this.selGsims){
                    _tmpSel.add(gsim);
                }
            }
            this._setGsimSelection(_tmpSel);
            this.$set(this, 'temporarySelectedGsims', []);
            this.gsimsDropdownVisible = false;
        },
        unselectAllGsims(){
            // this.selGsims must be a new Set at the end of this method.
            // This way the property will be updated in the view
            this._setGsimSelection(new Set());
        },
        _setGsimSelection(gsimsSet){
            this.$set(this, 'selGsims', gsimsSet);
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
            }
        },
        filterType: function(value, oldValue) {
            if (oldValue !== value){
                this.gsimsDropdownVisible = true;
                this.typeDropdownVisible = false;
            }
        }
    },
    computed: {
        // https://stackoverflow.com/a/47044150
        gsims() {
            
            var filterReg = this.filterText ? new RegExp(this.filterText.replace(/\*/g, '.*').replace(/\?/g, '.'), 'i') : undefined;
            var filterFunc = undefined;
            if (this.filterType == this.filterTypes[0]){
                var filterFunc = function(gsimName, regexp){
                    return gsimName.search(regexp) > -1;
                }
            }else if (this.filterType == this.filterTypes[1]){
                var filterFunc = function(gsimName, regexp){
                    var imts = this.avalGsims.get(gsimName)[0];
                    for (let imt of imts){
                        if (imt.search(regexp) > -1){
                            return true;
                        }
                    };
                    return false;
                }
            }else if (this.filterType == this.filterTypes[2]){
                var filterFunc = function(gsimName, regexp){
                    var trt = this.avalGsims.get(gsimName)[1];
                    return trt.search(regexp) > -1;
                }
            }
            
            var gsimNames = Array.from(this.avalGsims.keys());
            if (filterFunc && filterReg){
                return gsimNames.filter(el => filterFunc(el, filterReg))
            }
            return gsimNames;
        },
        imts(){
            return Array.from(this.avalImts);
        },
        selectedImts(){
            return Array.from(this.selImts);
        },
        selectedGsims(){
            return Array.from(this.selGsims);
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