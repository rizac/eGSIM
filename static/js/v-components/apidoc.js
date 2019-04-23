/**
 * Registers globally a Vue component. The name of the component
 * (first argument of 'Vue.component' below must be equal to this file's name 
 * (without extension)
 */
Vue.component('apidoc', {
    props: {
    	src: String,
    	id: {String, default: '__apidoc__iframe__'},
    	fragment: {String, default: ''}
    },
    template: `<iframe :id='id' class='flexible' :src='src + fragment'></iframe>`,
    /*methods: {
    	getSrc(){
    		// return this.src unless fragments are given in the url
    		// in case, pass the fragment to the iframe:
            var pathname = window.location.href.split('#');
            if (pathname.length > 1){
		    	var fragment = pathname.pop();
		    	if (!fragment.includes('/')){  // brutal check for safety ...
		    		return `${this.src}#${fragment}`
		    	}
            }
			return this.src;
        }
    },
    mounted: function(){
    	// listen for changes of fragment from within the iframe:
    	var iframe = document.getElementById(this.id);
    	if (iframe){
	    	var me = this;
	    	iframe.contentWindow.onhashchange = function(evt){
	    		var oldUrl = evt.oldURL;
	    		var newUrl = evt.newURL;
	    		if (newUrl.startsWith(oldUrl + '#')){
	    			me.fragment = newUrl.split('#').pop();
	    		}
	    	}
	   	}
    }*/
})