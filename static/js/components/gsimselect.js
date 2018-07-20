Vue.component('gsimselect', {
  //https://vuejs.org/v2/guide/components-props.html#Prop-Types:
  props: {
      'name': {type: String, default: 'gsim'},
      'errormsg': {type: String, default: ''},
      'showfilter': Boolean,
      'selectedgsims': Array,
      'avalgsims': Map
  },
  data: function () {
      return {
          filterText: '',
          filterType: 'GSIM name',
          filterTypes: ['GSIM name', 'IMT', 'Tectonic Region Type'],
          filterFunc: elm => true
      }
  },
  template: `<div class='flex-direction-col'>
    <div><slot>{{ name }}</slot>
      <errorspan v-bind:text="errormsg"></errorspan>
    </div>  
    <div class='text-muted small'>
        {{ selection.length }} of {{ gsims.length }} gsim(s) selected 
    </div>
    <div class='mb-1 flexible flex-direction-col'>
        <select v-model="selection" multiple required class="form-control flexible"
            :name="name" :id="'id_' + name">
            <option v-for="gsim in gsims" :key="gsim" v-show="isGsimVisible(gsim)">
                {{ gsim }}
            </option>
        </select>
    </div>

    <!-- GSIM FILTER CONTROLS: -->
    <div class="input-group" v-show='showfilter'>  
        <select v-model="filterType" class="form-control">
            <option v-for="item in filterTypes" :key="item" v-bind:value="item">
                    Filter by {{ item }}:
            </option>
        </select>
        <input v-model="filterText" type="text" class="form-control">
    </div>
  </div>`,
  methods: {
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
                  var imts = this.avalgsims.get(gsimName)[0];
                  for (let imt of imts){
                      if (imt.search(regexp) > -1){
                          return true;
                      }
                  };
                  return false;
              }
          }else if (this.filterType == this.filterTypes[2]){
              var filterFunc = function(gsimName){f
                  var trt = this.avalgsims.get(gsimName)[1];
                  return trt.search(regexp) > -1;
              }
          }
          this.$set(this, 'filterFunc', filterFunc);
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
    selection:{
        // selection is the v-model of the <select multiple> used as html component for selecting the gsims
        // (see template above). We need a getter bound to this.selectedgsims (which is in turn a props
        // bound to the parent Vue instance's selectedGsims) and a setter that notifies the selection change
        // In the html, the <gsim> component bounds the changed property to the Vue instance's selectedGsims
        // to achieve a two way binding
        get: function () {
            return this.selectedgsims && this.selectedgsims.length ? this.selectedgsims : [];
        },
        set: function (newValue) {
            this.$emit('update:selectedgsims', newValue);
        }
    },
    // https://stackoverflow.com/a/47044150
    gsims() {
        return Array.from(this.avalgsims.keys());
    }
}
})