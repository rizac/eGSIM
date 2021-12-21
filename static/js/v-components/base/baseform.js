/**
 * Represents a base form used in trellis, residuals, testing
 */
var _BASE_FORM = Vue.component('baseform', {
    props: {
        form: Object,
        url: String,
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
            requestURL: '',
            watchers: []
        }
    },
    methods: {
        request: function(){
            Vue.post(this.url, this.form).then(response => {  // defined in `vueutil.js`
                if (response && response.data){
                    this.responseData = response.data;
                } 
            });
        },
        resetDefaults: function(){
        	// reset the parameters to their defaults as implemented
        	// server side.
        	// Note that there are functions here calling this function
        	for (var key of Object.keys(this.form)){
        		if (this.form[key].initial !== undefined){
    				this.form[key].val = this.form[key].initial;
    			}
    		}
        },
        fetchRequestURL: function(){
        	// Fetches
        	// the current config (request) as dict and builsd this.requestURL
        	// Returns an axios Promise to which a user can attach functions to
        	// be executed when the POST request returns successfully
        	
        	// *NOTE*: in Chrome only, after clicking on the button calling this
        	// function, when we move out of it, the tooltip stays there: to make it disappear,
        	// we need to focus something else. This is annoying but we could not fix it
        	// (we tried implementing awrapper method, which was hiding the aria-label
        	// and then restoring it later inside a `then` attached to the returned promise
        	// below). If you want the source button, pass src as argument and access
        	// src.currentTarget
        	
        	for(var [key, url] of this.urls.downloadRequest){
        		if (key.startsWith('json')){
        			return Vue.post(url, this.form).then(response => {  // defined in `vueutil.js`
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
		                    	retUrl += `${prefix}` + encodeURIComponent(paramName) + '=' + encodeURIComponent(responseData[paramName]);
		                    	prefix = '&';
		                    }
		                    this.watchForValueChanges(true);
		                    this.requestURL = retUrl;
		                } 
		            });
        		}
        	}
        },
        watchForValueChanges: function(watch){
        	if (watch == !!this.watchers.length){
        		return;
        	}
        	if (watch){
        		for (var key of Object.keys(this.form)){
        			this.watchers.push(this.$watch(`form.${key}.val`, (newVal, oldVal) => {
        				this.requestURL ='';
        				this.watchForValueChanges(false);
        			}));
        		}
        		return;
        	}
        	// unwatch: simply call the stored callback
        	this.watchers.forEach(wacther => wacther());
        	this.watchers = [];
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
        },
        readLocalJSON: function(src){
        	// reads a local uploaded file from src.currentTarget
        	// copied and modified from http://researchhubs.com/post/computing/javascript/open-a-local-file-with-javascript.html
        	var fileInput = src.currentTarget;
            var file = fileInput.files[0];
  			if (!file) {
    			return;
  			}
  			var form = this.form;
  			var self = this;
  			var reader = new FileReader();
			reader.onload = function(e) {
				var contents = e.target.result;
				// clear the file value otherwise when clicking again on the same file
				// we do not get the change event:
				// setting an empty string seems not to call again the change event
				// but in any case this method should return immediately (see if above)
				fileInput.value = "";
				// Display file content
				var obj = {};
				try{
				    var obj = JSON.parse(contents);
				    // FIXME remove
				    // parse imt in case it has 'SA' with periods (e.g. 'SA(0.2)')
//				    if (('imt' in obj) && ('sa_period' in form)){
//					    var imts = (obj.imt || []).filter(elm => !elm.startsWith('SA('));
//						var periods = (obj.imt || []).filter(elm => elm.startsWith('SA('));
//						if (periods.length && !imts.includes('SA')){
//							imts.push('SA');
//						}
//						obj.imt = imts;
//						obj.sa_period = periods.map(elm => elm.substring(3, elm.length-1)).join(' ');
//					}
				}catch(error){
				    // although discouraged, this.$root is the easiest way to notify the main root
				    // and display the error:
				    self.$root.setError('Invalid file. Check that you loaded a JSON-formatted text file');
				}
				for (var key of Object.keys(obj)){
					if (!(key in form)){
					    self.$root.setError(`Invalid JSON. "${key}" is not a valid parameter`);
						return;
					}
				}
				self.resetDefaults.call(self);
				for (var key of Object.keys(obj)){
					form[key].val = obj[key];
				}
			};
			reader.readAsText(file);
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
  		});
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
        // no-op
    },
    template: `
	<transition :name="mounted ? 'egsimform' : ''">
    <form novalidate @submit.prevent="request"
        :class="[responseDataEmpty ? '' : ['shadow', 'border', 'bg-light', 'mb-2']]"
        class='d-flex flex-column flexible position-relative pb-4 align-self-center' style='z-index:10; border-color:rgba(0,0,0,.5) !important'
    >    
        <div class="d-flex flex-column flexible">
            
            <div class='d-flex flex-row justify-content-center align-items-center p-1' style='background-color:rgba(5, 73, 113, .2)'>
				<button type="button"
	            	@click='resetDefaults'
	            	aria-label="Restore default parameters" data-balloon-pos="down" data-balloon-length="medium"
	            	class="btn btn-outline-dark border-0"
	            >
	                <i class="fa fa-fast-backward"></i>
	            </button>
	            <button type="button"
	            	onclick='this.nextElementSibling.click()'
	            	data-balloon-pos="down" data-balloon-length="medium"
	            	aria-label="Load a configuration from a local JSON-formatted text file. This can be, e.g., a configuration previously saved as JSON (see 'Download as')"
	            	class="btn btn-outline-dark border-0"
	            >
	                <i class="fa fa-upload"></i>
	            </button>
	            <!-- NOTE: the control below must be placed immediately after the control above! -->
	            <input style='display:none' type="file" id="file-input" @change='readLocalJSON'>
	            <downloadselect
					:urls="urls.downloadRequest"
					:data="form"
					:selectelementclasses="'form-control-sm bg-transparent border-0'"
					class='ml-2'
					data-balloon-pos="down" data-balloon-length="medium"
					aria-label="Download the current configuration as text file. The file content can then be used in your custom code as input to fetch data (see POST requests in the API documentation for details)"
				/>
	            <button type="button"
	            	@click='fetchRequestURL'
	            	data-balloon-pos="down" data-balloon-length="medium"
	            	aria-label="Show the API URL of the current configuration. The URL can be used in your custom code to fetch data (see GET requests in the API documentation for details). You can also paste it in the browser to see the results (e.g., Firefox nicely displays JSON formatted data)"
	            	class="btn btn-outline-dark border-0 ml-2"
	            >
	                <i class="fa fa-link"></i>
	            </button>
            	<input :id="idRequestURLInput" type='text' v-model='requestURL'
            		:style= "requestURL ? {} : { 'visibility': 'hidden'}"
            		class='flexible form-control form-control-sm ml-2 bg-transparent border-0'
            		style='width:initial !important'
            	/>
            	<button type="button"
            		@click="copyRequestURL"
            		v-show='requestURL'
	            	aria-label="Copy the URL" data-balloon-pos="down" data-balloon-length="medium"
	            	class="btn btn-outline-dark border-0"
	            >
	                <i class="fa fa-copy"></i>
	            </button>
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
			                <i class="fa fa-play"></i> Display results
			            </button>
		            </div>
            	</div>
            </div>
        </div>
    </form>
	</transition>`
})