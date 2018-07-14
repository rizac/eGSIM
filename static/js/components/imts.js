Vue.component('imts', {
  //https://vuejs.org/v2/guide/components-props.html#Prop-Types:
  props: {
      'id': String,
      'name': String,
      'label': String,
      'errormsg': String,
      'selectedimts': Array,
      'avalimts': Set,
      'selectedgsims': Array,
      'avalgsims': Map
  },
  data: function () {
      return {
          saPeriods: ""
      }
  },
  template: `<div class='flex-direction-col'>
      <div>{{ label }}
          <span class='text-danger text-nowrap small' v-show="errormsg">
              {{ errormsg }}
          </span>
      </div>  
      <div class='text-muted small'>
          {{ selection.length }} of {{ imts.length }} imt(s) selected 
      </div>
      <div class='mb-1 flexible flex-direction-col'>
        <select v-model="selection" :name="name" :id="id" multiple class="form-control" required>
            <option v-for='imt in imts' :key='imt'
                v-bind:style="!isImtSelectable(imt) ? {'text-decoration': 'line-through'} : ''"
                v-bind:class="!isImtSelectable(imt) ? ['text-muted'] : ''">
                {{ imt }}
            </option>
        </select>
      </div>
      <div>  
          <input type='text' v-model="saPeriods" name='sa_periods'
              v-bind:disabled="!isImtSelectable('SA') || !isSelected('SA')"
              v-bind:placeholder="isImtSelectable('SA') ? 'SA period/s' : ''"
              class="form-control" >
      </div>
  </div>`,
  methods: {
      isImtSelectable(imt) {
          if (!this.selectedgsims.length){
              return false;
          }
          for (let gsim of this.selectedgsims){
              var selectableImts = this.avalgsims.get(gsim)[0];
              if (!selectableImts.has(imt)){
                  return false;
              }
          }
          return true;    
      },
      isSelected(imt){
          for(var imt of this.selection){
              if (imt == 'SA'){
                  return true;
              }
          }
          return false;
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
            return this.selectedimts && this.selectedimts.length ? this.selectedimts : [];
        },
        set: function (newValue) {
            this.$emit('update:selectedimts', newValue);
        }
    },
    // https://stackoverflow.com/a/47044150
    imts() {
        return Array.from(this.avalimts);
    }
}
})