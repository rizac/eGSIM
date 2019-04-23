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
    computed: {
        // computed properties are cached, i.e. they are re-evaluated only each time
        // the watched variable used therein are changed.
        // https://vuejs.org/v2/guide/computed.html
        // https://forum.vuejs.org/t/how-do-computed-properties-know-how-to-change/24140/2
        selectableImtsSet: function(){
            var avalgsims = this.form[this.gsimName].GSIMS_MANAGER;
            var selectedgsims = this.form[this.gsimName].val;
            var selectableimts = new Set(this.form[this.name].choices);
            for (var gsim of selectedgsims){
                var gsimImts = avalgsims.get(gsim)[0]; // it's a Set
                var intersection = new Set();
                for (var imt of selectableimts){
                    if (gsimImts.has(imt)){
                        intersection.add(imt);
                    }
                }
                selectableimts = intersection;
                if (!selectableimts.size){
                    break;
                }
            }
            return selectableimts;
        },
        selectedImtSet : function(){
            return new Set(this.form[this.name].val);
        }
    },
    // note on imts <option>s in template below: do not disable unselectable imts, as the user might not
    // be able to deselect them if gsims are changed. Just style them gray and use strike-through
    template: `<div class='d-flex flex-column'>
        <forminput :form="form" :name='"imt"' headonly></forminput>
        <div class='mb-1 flexible d-flex flex-column'>
          <select v-model="form[name].val" v-bind="form[name].attrs" class="form-control flexible">
              <option v-for='imt in form[name].choices' :key='imt'
                  v-bind:style="!isImtSelectable(imt) ? {'text-decoration': 'line-through'} : ''"
                  v-bind:class="!isImtSelectable(imt) ? ['disabled'] : ''">
                  {{ imt }}
              </option>
          </select>
        </div>
        <div>  
            <input type='text' v-model="form[saPeriodsName].val" :name='saPeriodsName'
                :disabled="!isImtSelectable('SA') || !isSelected('SA')"
                :placeholder="'SA period(s)'"
                class="form-control" >
        </div>
    </div>`,
    methods: {
        isImtSelectable(imt) {
            return this.selectableImtsSet.has(imt); // delegate computed property below (cached)
        },
        isSelected(imt){
            return this.selectedImtSet.has(imt);  // delegate computed property below (cached)
        }
    }
})