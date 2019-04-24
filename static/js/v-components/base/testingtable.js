// register the grid component
Vue.component('testingtable', {
    props: {
        data: {type: Object, default: () => { return{} }},
        filterKey: String
    },
    data: function () {
        return {
            sortKey: '',
            sortOrders: {},
            tableData: {},
            columns: []
        }
    },
    computed: {
        data: {
            immediate: true,
            handler(newval, oldval){
               this.visible = !Vue.isEmpty(this.data);
               if (this.visible){ // see prop below
                   this.init.call(this, this.data);
               }
            }
        },
        filteredHeroes: function () {
            var sortKey = this.sortKey
            var filterKey = this.filterKey && this.filterKey.toLowerCase()
            var order = this.sortOrders[sortKey] || 1
            var heroes = this.heroes
            if (filterKey) {
                heroes = heroes.filter(function (row) {
                    return Object.keys(row).some(function (key) {
                        return String(row[key]).toLowerCase().indexOf(filterKey) > -1
                    })
                })
            }
            if (sortKey) {
                heroes = heroes.slice().sort(function (a, b) {
                    a = a[sortKey]
                    b = b[sortKey]
                    return (a === b ? 0 : a > b ? 1 : -1) * order
                })
            }
            return heroes
        }
    },
    template: `<table>
        <thead>
            <tr>
                <th v-for="key in columns"
                  @click="sortBy(key)"
                  :class="{ active: sortKey == key }">
                  {{ key | capitalize }}
                  <span class="arrow" :class="sortOrders[key] > 0 ? 'asc' : 'dsc'">
                  </span>
                </th>
            </tr>
        </thead>
        <tbody>
            <tr v-for="entry in filteredHeroes">
                <td v-for="key in columns">
                {{entry[key]}}
                </td>
            </tr>
        </tbody>
    </table>`,
    filters: {
        capitalize: function (str) {
            return str.charAt(0).toUpperCase() + str.slice(1)
        }
    },
    methods: {
        sortBy: function (key) {
            this.sortKey = key
            this.sortOrders[key] = (this.sortOrders[key] || -1) * -1
        },
        init: function(data){
            columns = ["Measure of fit", "gsim", "imt"];
            keys = Object.keys(data)
            if (keys.some(elm => elm == 'Residuals' || elm == 'Likelihood')){
                columns.push('type');
            }
            if (keys.includes('Residuals')){
                columns.push('Mean', 'Std Dev');
            }
            if (keys.includes('EDR')){
                columns.push("MDE Norm", "sqrt Kappa", "EDR");
            }
            for (var key of Object.keys(data)){
                if (key.toLowerCase().startsWith('residuals')){
                    columns.push('type')
                }
            }
        }
    }
})

// bootstrap the demo
var demo = new Vue({
  el: '#demo',
  data: {
    searchQuery: '',
    gridColumns: ['name', 'power'],
    gridData: [
      { name: 'Chuck Norris', power: Infinity },
      { name: 'Bruce Lee', power: 9000 },
      { name: 'Jackie Chan', power: 7000 },
      { name: 'Jet Li', power: 8000 }
    ]
  }
})