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
            filterFunc: elm => true
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
            var avalgsims = this.form[this.name].GSIMS_MANAGER;
            var selectedimts = new Set(this.form[this.imtName].val);
            var selectableGsims = Array.from(avalgsims.keys());
            if (selectedimts.size){
                selectableGsims = selectableGsims.filter(gsim => {
                    var gsimImts = avalgsims.get(gsim)[0]; // it's a Set
                    for (var imt of selectedimts){
                        if (!gsimImts.has(imt)){
                            return false;
                        }
                    }
                    return true;
                });
            }
            return new Set(selectableGsims);
        }
    },
    template: `<div class='d-flex flex-column'>
      <div class='d-flex flex-row align-items-baseline'>
          <h5>{{ name }}</h5>
          <div class='small flexible text-right ml-3'>
              <span class='text-danger'>{{ form[name].err }}</span>
              <span v-if='!form[name].err' class='text-muted'>
                  {{ form[name].label }}: {{ form[name].val.length }} of {{ form[name].choices.length }} selected
              </span>
          </div>
      </div>
      <div class='flexible d-flex flex-column'>
          <select v-model="form[name].val" v-bind="form[name].attrs" class="form-control flexible">
              <option v-for="gsim in form[name].choices" :value="gsim" :key="gsim" v-show="isGsimVisible(gsim)"
               v-bind:style="!isGsimSelectable(gsim) ? {'text-decoration': 'line-through'} : ''"
               v-bind:class="!isGsimSelectable(gsim) ? ['disabled'] : ''">
                  {{ gsim }}
              </option>
          </select>
      </div>
    
      <!-- GSIM FILTER CONTROLS: -->
      <div class="d-flex flex-row mt-1" v-if='showfilter'>  
          <select v-model="filterType" class="form-control" style='border:0px; background-color:transparent'>
              <option v-for="item in filterTypes" :key="item" v-bind:value="item">
                      Filter by {{ item }}:
              </option>
          </select>
          <input v-model="filterText" type="text" class="form-control" style='width:initial'>
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
            var regexp = this.filterText ? 
                new RegExp(this.filterText.replace(/([^\w\*\?])/g, '\\$1').replace(/\*/g, '.*').replace(/\?/g, '.'), 'i') : 
                    undefined;
            var filterFunc = elm => true;
            var avalGsims = this.form[this.name].GSIMS_MANAGER;
            if (this.filterType == this.filterTypes[0]){
                var filterFunc = function(gsimName){
                    return gsimName.search(regexp) > -1;
                }
            }else if (this.filterType == this.filterTypes[1]){
                var filterFunc = function(gsimName){
                    var imts = avalGsims.get(gsimName)[0];
                    for (let imt of imts){
                        if (imt.search(regexp) > -1){
                            return true;
                        }
                    };
                    return false;
                }
            }else if (this.filterType == this.filterTypes[2]){
                var filterFunc = function(gsimName){
                    var trt = avalGsims.get(gsimName)[1];
                    return trt.search(regexp) > -1;
                }
            }
            this.filterFunc = filterFunc;
        }
    }
});