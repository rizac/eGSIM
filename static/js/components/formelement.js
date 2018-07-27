/**
 * 
 */
Vue.component('formelement', {
  // https://vuejs.org/v2/guide/components-props.html#Prop-Types:
  props: {
      'boolean': {type: Boolean, default:false},
      'name': String,
      'help': {type:String, default:''},
      'label': {type: String, default: ''},
      'fielderrors': {type:Object, default:''}
  },
//  data: function(){
//      return {id: 'id_' + this.name};
//  },
  template: `<div><label :for="'id_' + name">{{ name }}</label>
                 <span class='text-danger text-nowrap small ml-1' v-show="fielderrors[name]">{{ fielderrors[name] }}</span>
             <span class="text-muted small text-nowrap ml-1" v-show="helptext">{{ helptext }}</span>
             </div>
             <slot></slot>`,
  computed: {
      // https://stackoverflow.com/a/47044150
      helptext() {
          var str = this.label.toLowerCase() != this.name.toLowerCase() ? this.label : '';
          if (this.help and str){
              str += ' ';
          }
          str += this.help;
          return str;
      }
  }    
})