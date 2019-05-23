/**
 * Implements a component for visualizing text-formatted data (e.g., json, yaml)
 */
Vue.component('visualizerdiv', {
    //https://vuejs.org/v2/guide/components-props.html#Prop-Types:
    props: {
    	// the data to be visualized (string)
        data: {default: () => ""},
        // the format argument. Supported is "JSON"
        filename: {type: String, default: ""}
    },
    data: function () {
    	return {
        }
    },
    computed: {
    	textData: function(){
    		var obj = this.data;
    		if (Vue.isFormObject(obj)){  // defined in vueutil.js
    			var obj2 = {};
    			for(var key of Object.keys(obj)){
    				obj2[key] = obj[key].val;
    			}
    			obj = obj2;
    		}
    		if (typeof obj === 'object'){
    			return JSON.stringify(obj, null, 4);
    		}
    		return obj.toString().trim();
    	}
    },
    template: `<div class='d-flex flex-column'>
	    <pre class='flexible'><code class="language-python" v-html="textData"></code></pre>
	    <div class='text-center'>
	    	<button v-show='filename' type='button' @click='download()'>
	    		<i class="fa fa-download"></i> {{ filename }}
	    	</button>
	    </div>
	</div>`,
    methods: {
    	// no-op
    	download: function(){
    		Vue.download(this.textData, this.filename);  // defined in vueutil.js
    	}
    }
})