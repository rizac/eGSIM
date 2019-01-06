Vue.component('imtselect', {
  //https://vuejs.org/v2/guide/components-props.html#Prop-Types:
  props: {
      'name': {type: String, default: 'imt'},
      'gsimName': {type: String, default: 'gsim'},
      'saPeriodsName': {type: String, default: 'sa_periods'},
      'form': Object
  },
  data: function () {
      return {
          // no-op for the moment
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
            <option v-for='imt in form[name].choices' :key='imt'
                v-bind:style="!isImtSelectable(imt) ? {'text-decoration': 'line-through'} : ''"
                v-bind:class="!isImtSelectable(imt) ? ['disabled'] : ''">
                {{ imt }}
            </option>
        </select>
      </div>
      <div>  
          <input type='text' v-model="form[saPeriodsName].val" :name='saPeriodsName'
              v-bind:disabled="!isImtSelectable('SA') || !isSelected('SA')"
              v-bind:placeholder="'SA period(s)'"
              class="form-control" >
      </div>
  </div>`,
  methods: {
      isImtSelectable(imt) {
          var avalgsims = this.form[this.gsimName].GSIMS_MANAGER;
          var selectedgsims = this.form[this.gsimName].val;
          return !selectedgsims.some(gsim => !avalgsims.get(gsim)[0].has(imt));
      },
      isSelected(imt){
          return this.form[this.name].val.includes(imt);
      }
  },
  computed: {
      // no-op for the moment
      
  }
})