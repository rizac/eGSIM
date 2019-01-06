Vue.component('gsimselect', {
  //https://vuejs.org/v2/guide/components-props.html#Prop-Types:
  props: {
      'name': {type: String, default: 'gsim'},
      'showfilter': Boolean,
      'form': Object
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
    <div>
      <h5>{{ name }}</h5>
      <span class='small text-danger'>{{ form[name].err }}</span>
    </div>  
    <div class='text-muted small'>
        {{ form[name].val.length }} of {{ form[name].choices.length }} selected 
    </div>
    <div class='mb-1 flexible flex-direction-col'>
        <select v-model="form[name].val" v-bind="form[name].attrs" multiple class="form-control flexible">
            <option v-for="gsim in form[name].choices" :value="gsim" :key="gsim" v-show="isGsimVisible(gsim)">
                {{ gsim }}
            </option>
        </select>
    </div>

    <!-- GSIM FILTER CONTROLS: -->
    <div class="input-group" v-if='showfilter'>  
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
      },
//      selection: function(value, oldValue){
//          // watch this.selection (which is initialized from the 'selectedgsims' prop).
//          // if 'selectedgsims' is synced with some other component's (or instance's) property,
//          // emit the event notifying the change
//          // (https://vuejs.org/v2/guide/components-custom-events.html#sync-Modifier):
//          this.$emit('update:selectedgsims', value);  // (value is an array)
//      }
  },
  computed: {
      // no-op for the moment
  }
})