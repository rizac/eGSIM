/**
 * Represents a base form used in trellis, residuals, testing
 */
var _BASE_FORM = Vue.component('baseform', {
    props: {
        form: Object,
        url: String,
        post: Function,
        // urls properties are passed to the downloadselect for downloading the request:
        urls: {type: Object, default: () => {return {}}},
        // additional class for the imtselect:
        imtselectclasses: {type: String, default: "flexible"}
    },
    data: function () {
    	return {
        	responseDataEmpty: true,
            responseData: {},
            mounted: false,
            idRequestURLInput: this.url + '_requesturl_input_',
            requestURL: ''
        }
    },
    methods: {
        request: function(){
            this.post(this.url, this.form).then(response => {
                if (response && response.data){
                    this.responseData = response.data;
                } 
            });
        },
        resetDefaults: function(){
        	for (var key of Object.keys(this.form)){
        		if (this.form[key].initial !== undefined){
    				this.form[key].val = this.form[key].initial;
    			}
    		}
        },
        getQueryString: function(){
        	// little hack: get the json data of the current request.
        	// The url is inside this.urls, we get it by inspecting the url key
        	for(var [key, url] of this.urls.downloadRequest){
        		if (key.startsWith('json')){
        			this.post(url, this.form).then(response => {
		                if (response && response.data){
		                    var responseData = response.data;
		                    var retUrl = window.location.origin;
		                    if (!window.location.origin) {  // https://stackoverflow.com/a/25495161
								retUrl = window.location.protocol + "//" 
							    	+ window.location.hostname 
							    	+ (window.location.port ? ':' + window.location.port : '');
							}
		                    retUrl += (this.url.startsWith('/') ? '' : '/') + this.url;
		                    var prefix = '?';
		                    for (var paramName of Object.keys(responseData)){
		                    	retUrl += `${prefix}` + encodeURI(paramName) + '=' + encodeURI(responseData[paramName]);
		                    	prefix = '&';
		                    }
		                    console.log(retUrl);
		                    this.requestURL = retUrl;
		                } 
		            });
        		}
        	}
        },
        copyRequestURL: function(src){
        	var targetElement = src.currentTarget; // the button
        	// aria-label is used by balloon.css to display the tooltip
			// store the current one:
			var ariaLabel = targetElement.getAttribute('aria-label');
  			var successful = this.copyText(document.getElementById(this.idRequestURLInput));
  			// restore the old aria-label
  			if (ariaLabel){
	  			targetElement.setAttribute('aria-label', successful ? 'Copied' : 'Unable to copy');
	  			setTimeout(() => {
	  				targetElement.setAttribute('aria-label', ariaLabel);
	  			}, 1000);
        	}
        },
        copyText: function(element){
        	// https://www.w3schools.com/howto/howto_js_copy_clipboard.asp
        	element.focus();
			element.select();
			try {
    			var successful = document.execCommand('copy');
  			} catch (err) {
    			var successful = false;
  			}
  			return successful;
        }
    },
    mounted: function () {
    	// set the mounted variable in order to activate the transition after the
    	// whole component has been mounted
    	// the transition is used just to show up / hide the form
    	if (this.mounted){
    		return;
    	}
  		this.$nextTick(function () {
    		// Code that will run only after the
    		// entire view has been rendered
    		this.mounted = true;
  		})
	},
    watch: {
        responseData: {
            immediate: true, // https://forum.vuejs.org/t/watchers-not-triggered-on-initialization/12475
            handler: function(newVal, oldVal){
                this.responseDataEmpty = Vue.isEmpty(newVal); // defined in vueutil.js
                if (!this.responseDataEmpty){
                	this.$emit('responsereceived', newVal);
                }
            }
        }
    },
    computed: {
    	formObject: function(){
    		// returns a javascript object with keys mapped to each form element value
    		var data = {};
    		for (var key of Object.keys(this.form)){
    			data[key] = this.form[key].val;
    		}
    		return data;
    	}	
    },
    template: `
	<transition :name="mounted ? 'egsimform' : ''">
    <form novalidate v-on:submit.prevent="request"
        :class="[responseDataEmpty ? '' : ['shadow', 'border', 'bg-light', 'mb-1']]"
        class='d-flex flex-column flexible position-relative pb-4 align-self-center' style='z-index:10; border-color:rgba(0,0,0,.5) !important'
    >    
        <div class="d-flex flex-column flexible">
            
            <div class='d-flex flex-row justify-content-center p-1' style='background-color:rgba(5, 73, 113, .2)'>
				<button type="button"
	            	@click='resetDefaults'
	            	aria-label="Restore default parameters" data-balloon-pos="down" data-balloon-length="medium"
	            	class="btn btn-outline-dark border-0 ml-2"
	            >
	                <i class="fa fa-fast-backward"></i>
	            </button>
	            <downloadselect
					:urls="urls.downloadRequest"
					:post="post"
					:data="formObject"
					data-balloon-pos="down" data-balloon-length="medium"
					aria-label="Download the current configuration as text file. The file content can then be used in your custom code as input to fetch data (see POST requests in the API documentation for details)"
				/>
	            <button type="button"
	            	@click='getQueryString'
	            	aria-label="Show the URL of the current configuration. The URL can be used in your custom code to fetch data (see GET requests in the API documentation for details)" data-balloon-pos="down" data-balloon-length="medium"
	            	class="btn btn-outline-dark border-0 ml-2"
	            >
	                <i class="fa fa-link"></i>
	            </button>
	            <div class='d-flex flex-row flexible ml-2' style='flex-basis:1'>
	            	<input :id="idRequestURLInput" v-show='requestURL' type='text' v-model='requestURL' class='flexible'>
	            	<button type="button"
	            		@click="copyRequestURL"
	            		v-show='requestURL'
		            	aria-label="Copy the URL" data-balloon-pos="down" data-balloon-length="medium"
		            	class="btn btn-outline-dark border-0"
		            >
		                <i class="fa fa-copy"></i>
		            </button>
	            </div>
	        	<button type="button"
	            	v-show='!responseDataEmpty'
	            	@click='$emit("closebuttonclicked")'
	            	aria-label="Close form window" data-balloon-pos="down" data-balloon-length="medium"
	            	class="btn btn-outline-dark border-0 ml-2"
	            >
	                <i class="fa fa-times"></i>
	            </button>
	        </div>

            <div class="d-flex flexible flex-row mt-3" :class="[responseDataEmpty ? '' : ['mx-4']]">
                <div class="d-flex flexible flex-column">
                    <gsimselect :form="form" showfilter class="flexible" />
                </div>
                <div class="d-flex flex-column flexible ml-4">
					<imtselect :form="form" :class="imtselectclasses"></imtselect>
                	
                	<slot/> <!-- << HERE CUSTOM FORM ELEMENTS IN CHILD COMPONENTS -->
 					
 					<div class='d-flex flex-row justify-content-center mt-4'>
			            <div class='flexible' style='flex-basis:1'></div>
			            <button type="submit" class="btn btn-primary ml-2">
			                <i class="fa fa-play"></i> Display plots
			            </button>
		            </div>
            	</div>
            </div>
        </div>
    </form>
	</transition>`
})