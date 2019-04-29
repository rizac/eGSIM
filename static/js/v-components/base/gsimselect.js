Vue.component('gsimselect', {
    //https://vuejs.org/v2/guide/components-props.html#Prop-Types:
    props: {
        name: {type: String, default: 'gsim'},
        imtName: {type: String, default: 'imt'},
        showfilter: {type: Boolean, default: false},
        form: Object,
        selectbutton: {type: String, default: ''}
    },
    data: function () {
        return {
            filterText: '',
            filterType: 'GSIM name',
            filterTypes: ['GSIM name', 'IMT', 'Tectonic Region Type'],
            filterFunc: elm => true,
            gsimManager: this.form[this.name].gsimManager  // Object defined in egsim_base.js ('created' function)
        }
    },
    watch: { // https://siongui.github.io/2017/02/03/vuejs-input-change-event/
        filterText: function(value, oldValue) {
            if (oldValue !== value){
                this.updateFilter();
            }
        },
        filterType: function(value, oldValue) {
            if (oldValue !== value){
                this.updateFilter();
            }
        }
    },
    computed: {
        // computed properties are cached, i.e. they are re-evaluated only each time
        // the watched variable used therein are changed.
        // https://vuejs.org/v2/guide/computed.html
        // https://forum.vuejs.org/t/how-do-computed-properties-know-how-to-change/24140/2
        selectableGsimsSet: function(){
            var selectedimts = this.form[this.imtName].val;
            var selectableGsims = this.form[this.name].choices;
            if (selectedimts.length){
                var gsimManager = this.gsimManager;  // Object defined in egsim_base.js ('created' function)
            	selectableGsims = selectableGsims.filter(gsim => {
                	return selectedimts.every(imt => gsimManager.imtsOf(gsim).includes(imt));
                });
            }
            return new Set(selectableGsims);
        }
    },
    template: `<div class='d-flex flex-column'>
      <forminput :form="form" :name='"gsim"' headonly></forminput>
      <div class='flexible d-flex flex-column'>
          <select v-model="form[name].val" v-bind="form[name].attrs" class="form-control flexible with-icons">
              <option v-for="gsim in form[name].choices" :value="gsim" :key="gsim" v-show="isGsimVisible(gsim)"
               v-bind:style="!isGsimSelectable(gsim) ? {'text-decoration': 'line-through'} : ''"
               v-bind:class="!isGsimSelectable(gsim) ? ['disabled'] : ''">
                  {{ gsim }} {{ gsimManager.warningOf(gsim) ? '&#xf071;' : '' }} 
              </option>
          </select>
      </div>
    
      <!-- GSIM FILTER CONTROLS: -->
      <div class="d-flex flex-row mt-1" v-if='showfilter'>  
          <select v-model="filterType" class="form-control form-control-sm" style='border:0px; background-color:transparent'>
              <option v-for="item in filterTypes" :key="item" v-bind:value="item">
                      Filter by {{ item }}:
              </option>
          </select>
          <input v-model="filterText" type="text" class="form-control form-control-sm" style='width:initial'>
      </div>
      
      <div v-if='selectbutton' class='mt-2'>
          <button @click="$emit('selection-fired', form[name].val)" v-html='selectbutton' 
           :disabled='!(form[name].val || []).length' class='btn btn-outline-primary form-control'>
          </button>
      </div>
    </div>`,
    methods: {
        isGsimVisible(gsim){
            return this.filterFunc(gsim);
        },
        isGsimSelectable(gsim){
            return this.selectableGsimsSet.has(gsim);
        },
        updateFilter(){
            this.adjustWidth();
            var regexp = this.filterText ? 
                new RegExp(this.filterText.replace(/([^\w\*\?])/g, '\\$1').replace(/\*/g, '.*').replace(/\?/g, '.'), 'i') : 
                    undefined;
            var filterFunc = elm => true;
            var gsimManager = this.gsimManager;  // Object defined in egsim_base.js ('created' function)
            if (this.filterType == this.filterTypes[0]){
                var filterFunc = gsimName => gsimName.search(regexp) > -1;
            }else if (this.filterType == this.filterTypes[1]){
                var filterFunc = gsimName => gsimManager.imtsOf(gsimName).some(imt => imt.search(regexp) > -1);
            }else if (this.filterType == this.filterTypes[2]){
            	var filterFunc = gsimName => gsimManager.trtOf(gsimName).search(regexp) > -1;
            }
            this.filterFunc = filterFunc;
        },
        adjustWidth(){
            // fixes or releases the <select> tag width before filtering
            // to avoid upleasant rapid width changes
            if (!this.showfilter){
                return;
            }
            var elm = document.querySelector('select#id_gsim');
            if (!elm){
                return;
            }
            elm.style.width = !this.filterText ? '' : elm.offsetWidth + 'px';
        }
    },
    mounted: function() { // https://stackoverflow.com/questions/40714319/how-to-call-a-vue-js-function-on-page-load
        // no -op
    },
    deactivated: function(){
        // no-op
    }
});