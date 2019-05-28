/**
 * Represents a base form used in trellis, residuals, testing
 */
var _BASE_FORM = Vue.component('baseform', {
    props: {
        form: Object,
        url: String,
        // Additional urls Object (string key mapped to urls).
		// This should contain e.g., urls for downloading responses as text
        // Note: use a function for the 'default' key to prevent sharing the same object (https://github.com/vuejs/vue/issues/1032#issuecomment-120212888)
        urls: {type: Object, default: () => {return {}}},
        response: {type: Object, default: () => {return {}}},
        post: Function,
        filename: {type: String, default: ''}
    },
    data: function () {
    	// Build an Object 'responseDownloadFunctions': it is a Map of (string, function) entries
    	// where the keys (string) describes the download type (e.g. 'JSON', 'text/csv' ...)
    	// and might be used to display the download in an associated GUI control,
    	// and the function performs the download of the response data.
    	// It might seem weird to couple 'responseDownloadFunctions' with this object
    	// which deals with RESPONSES, but it makes the code DRY.
    	var responseDownloadFunctions = new Map();  // Map preserves the insertion order
    	if (this.filename){
    		// download as JSON (needs only a response object):
	    	responseDownloadFunctions.set('json',
				() => { Vue.download.call(this, this.responseData, this.filename + '.response.json'); });  // see vueutil.js
			// define a function for downloading as text (basically calls the 'this.post'
			// with a provided URL)
			var downloadAsCsv = (url) => {
	    		var fname =  this.filename + '.response.csv'
				this.post(url + "/" + fname, this.responseData).then(response => {
	                if (response && response.data){
	                    Vue.download(response.data, fname);
	                } 
	            });
			}
			// now try to see if we have the download as text urls passed in this.urls:
			if (this.urls.downloadResponseCsv){
				responseDownloadFunctions.set("text/csv",
					() => { downloadAsCsv.call(this, this.urls.downloadResponseCsv); });
			}
			if (this.urls.downloadResponseCsvDecComma){
				responseDownloadFunctions.set("text/csv, decimal comma",
					() => { downloadAsCsv.call(this, this.urls.downloadResponseCsvDecComma); });
			}
 		}
 		// now create the functions for the request download:
 		var requestDownloadFunctions = {};
 		if (this.filename && this.urls.downloadRequest){
 			var [jsonfname, yamlfname] = [this.filename + '.request.json', this.filename + '.request.yaml'];
 			requestDownloadFunctions = {
 				json: () => { this.download.call(this, jsonfname); },
 				yaml: () => { this.download.call(this, yamlfname); }
 			}
 		}
    	return {
        	responseDataEmpty: true,
            responseData: this.response && this.response.data ? this.response.data : {},
            requestDownloadFunctions: requestDownloadFunctions,
            responseDownloadFunctions: responseDownloadFunctions
        }
    },
    methods: {
        request: function(){
            var form = this.form;
            this.post(this.url, form).then(response => {
                if (response && response.data){
                    this.responseData = response.data;
                } 
            });
        },
        download: function(filename){
        	var form = this.form;
        	this.post(this.urls.downloadRequest + "/" + filename, form).then(response => {
                if (response && response.data){
                    Vue.download(response.data, filename);
                } 
            });
        }
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
    template: `
	<transition name="egsimform">
    <form novalidate v-on:submit.prevent="request"
        :class="[responseDataEmpty ? '' : ['shadow', 'border', 'bg-light']]"
        class='d-flex flex-column flexible position-relative mb-3 align-self-center' style='z-index:10'>
        
        <div class="d-flex flex-column flexible" :class="[responseDataEmpty ? '' : ['mx-4', 'mt-4', 'mb-3']]">
            <div class="d-flex flexible flex-row mb-3">

                <div class="d-flex flexible flex-column">
                    <gsimselect :form="form" showfilter class="flexible"></gsimselect>
                </div>
                
                <slot/> <!-- << HERE CUSTOM FORM ELEMENTS IN CHILD COMPONENTS -->

            </div>
        
			<div class='d-flex flex-row justify-content-center border-top pt-3'>
				<downloadselect :model="requestDownloadFunctions">
					Download request as:
				</downloadselect>
	            <button type="submit" class="btn btn-primary ml-2">
	                <i class="fa fa-play"></i> Display plots
	            </button>
	            <button type="button" class="btn btn-primary ml-2"
	            	v-show='!responseDataEmpty'
	            	@click='$emit("closebuttonclicked")'
	            >
	                <i class="fa fa-times"></i> Close
	            </button>
            </div>

        </div>
        
    </form>
	</transition>`
})