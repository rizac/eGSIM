/**
 * Implements a component for downloading data
 */
Vue.component('downloadselect', {
    //https://vuejs.org/v2/guide/components-props.html#Prop-Types:
    props: {
    	// urls is an Array of [key, url] elements (both strings)
    	// any url starting with 'file:///' will simply download the data
    	// with the file name specified after 'file:///'
        urls: {type: Array, default: () => { return []; }},
        // data is the POST data to be sent with the 'post' function below
        // It can be static (Object) or a callback(key, url) which is assumed
        // to return the data (Object) associated with [key, url].
        // In general, data below is NOT the data to be downloaded, but the POST data
        // sent to fetch the data to be downloaded (see comment on 'specialKeys' below
        // for a special case where `data` is actually the data to be downlaoded)
        data: [Object, Function],
        // post function to use for fetching the data to be downloaded:
        post: Function
    },
    data: function () {
    	// find special Keys, i.e. keys not mapped to a URL string but
    	// to the JSON serialized string '{"file": "...", "mimetype": "..."}'
    	// that string indicates that the given key should simply download the
    	// post data (`data` property of this component) without any server call
    	var specialKeys = {};
    	for (var [key, url] of this.urls){
    		try {
    			// Something that throws exception
    			data = JSON.parse(url);
    			if (('file' in data) && ('mimetype' in data)){
    				specialKeys[key] = data;
    				continue;
    			}
			}catch (e) {
				continue;
			}
        }
    	var emptyValue = "/*:_\\" + new Date().getTime().toString();  // something not present in this.urls keys
    	return {
    		emptyValue: emptyValue,
    		selKey: emptyValue,
    		specialKeys: specialKeys
        }
    },
    created: function(){
    	// create an empty value and insert it at index 0:
    	
    },
    watch: {
    	'selKey': function (newVal, oldVal){
    		// wacth for changes in the <select> and download
    		// note: we might have attached an onchange on the <select> tag,
    		// but: https://github.com/vuejs/vue/issues/293
 
    		if (newVal === this.emptyValue){
    			return;
    		}
    		for (var [key, url] of this.urls){
            	if (key === newVal){
            		var postdata = this.data;
            		if (typeof postdata === "function"){
            			postdata = postdata(key, url);
            		}
        			if (key in this.specialKeys){
        				var filename = this.specialKeys[key].file;
        				var mimeType = this.specialKeys[key].mimetype;
        				// stringify the data because this.download expects strings or ArrayBuffers
        				// Also note, use tabs as indentations because the resulting file might be really really
        				// lighter in size!
        				// FIXME: what about non ascii characters in postdata?
        				this.download.call(this, JSON.stringify(postdata, null, '\t'), filename, mimeType);
        			}else{
        				// fetch data and download it:
        				// the method below is the same as 'download' above
        				// but requires an intermediate step to get the
        				// data to download from the server
        				this.fetchAndDownload.call(this, url, postdata);
            		}
            		break;
            	}
            }
            this.selKey = this.emptyValue;
        }
    },
    computed: {
    	// no-op
    },
    template: `<div v-if='urls.length' class='d-flex flex-row text-nowrap align-items-baseline'>
		<select
			v-model='selKey'
			class='form-control ml-2'
		>	
		    <option
                :value='emptyValue'
                :disabled="true"
            >
                Download as:
            </option>
            <option
            	v-for='[key, _] in urls'
            	:value='key'
            >
            	{{ key }}
            </option>
        </select>
    </div>`,
    methods: {
    	fetchAndDownload: function(url, postData){
    		/**
    		 * Fetches the given data and downloads the result.
    		 * Note that if we redirected to the result url in the browser
    		 * (new tab or page) the browser would download the content
    		 * automatically as long as the response content disposition is
    		 * set accordingly. But since we retreieve the response in an ajax
    		 * call, we have to download the content manually (see this.download)
    		 */
    		 
    		// the post function needs to have the 'responseType' set in order
    		// to work with window.URL.createObjectURL (used in this.download).
    		// For info see (also check there is a lot of old code to skip
    		// and comments in the answers to look at):
    		// https://stackoverflow.com/questions/8022425/getting-blob-data-from-xhr-request
			this.post(url, postData, {responseType: 'arraybuffer'}).then(response => {
                if (response && response.data){
                	var filename = (response.headers || {})['content-disposition'];
                	if (filename){
	                    var iof = filename.indexOf('filename=');
	                    if (iof > -1){
	                    	filename = filename.substring(iof + 'filename='.length);
	                    	if (filename){
			                    var ctype = (response.headers || {})['content-type'];
			                    this.download(response.data, filename, ctype);
			                }
		                }
	                }
                }
            });
		},
        download: function(data, filename, mimeType){
        	/**
        	 * Downloads data with the given filename and mimeType
        	 * (https://developer.mozilla.org/en-US/docs/Web/HTTP/Basics_of_HTTP/MIME_types/Complete_list_of_MIME_types)
        	 * data is supposed to be a Byte-String ot an ArrayBuffer (https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/ArrayBuffer)
        	 * issued from `fetchAndDownload`
        	 */
        	// refs:
        	// https://www.bennadel.com/blog/3472-downloading-text-using-blobs-url-createobjecturl-and-the-anchor-download-attribute-in-javascript.htm
			// https://stackoverflow.com/a/47197970
			// https://developer.mozilla.org/en-US/docs/Web/API/Blob
			// https://gist.github.com/javilobo8/097c30a233786be52070986d8cdb1743
        	var blob = new Blob([data], {type: mimeType});
        	var downloadUrl = window.URL.createObjectURL(blob);
        	var downloadAnchorNode = document.createElement('a');
        	downloadAnchorNode.setAttribute("href", downloadUrl);
		    downloadAnchorNode.setAttribute("download", filename);
		    document.body.appendChild(downloadAnchorNode); // required for firefox
		    downloadAnchorNode.click();
		    downloadAnchorNode.remove();
		    // as we removed the node, we should have freed up memopry,
		    // but let's be safe:
		    URL.revokeObjectURL( downloadUrl );
        }
    }
})