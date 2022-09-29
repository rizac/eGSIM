/** base skeleton implementation for the main Vue instance. See egsim.html */
var EGSIM_BASE = {
	data: function(){
		return {
			// NOTE: do not prefix data variable with underscore: https://vuejs.org/v2/api/#data
			gsims: [],
			imtGroups: [],
			loading: false,
			initialErrorMsg: "",
			errors: {},  // populated in created()
			selComponent: '',
			componentProps: {}, // component names (e.g. 'trellis') -> Object
			postfuncDefaultConfig: {},  // default HTTPClient config
			flatfileUploadUrl: '', // used when we upload a flatfile
		}
	},
	created(){
		// this.httpClient is provided in egsim.html. Making `this` as listener means
		// that when httpClient.post is called, then this object is notified
		// (see postrequest* method(s) below):
		this.$httpClient.listeners = [this];
		// Create a "template" Array of gsims and imts, to be copied as field choices
		var reg = /[A-Z]+[^A-Z0-9]+|[0-9]+|.+/g; //NOTE safari does not support lookbehind/aheads!
		// converts the gsims received from server from an Array of Arrays to an
		// Array of Objects:
		var imts = new Set();
		var imtGroups = this.imtGroups;
		var gsimObjects = this.gsims.map(elm => {  // elm: Array of 2 or 3 elements
			var gsimName = elm[0];
			var gsimImts = imtGroups[elm[1]];
			// add the model imts to the global imt collection:
			gsimImts.forEach(imt => imts.add(imt));
			return {
				value: gsimName,
				disabled: false,
				innerHTML: gsimName.match(reg).join(" "),
				imts: gsimImts,
				warning: elm[2] || "",
			}
		});
		// convert imts (Set) into Array:
		imts = Array.from(imts);
		// Setup fields data:
		var regionalization = this.regionalization;
		for (var [name, form] of this.forms()){
			if (form.gsim){
				// set form.gsim.choices as a deep copy of gsimObjects:
				form.gsim.choices = gsimObjects.map(elm => Object.assign({}, elm));
				form.gsim.value || (form.gsim.value = []); // assure empty list (not null)
				form.gsim['data-regionalization'] = {
					url: regionalization.url,
					choices: regionalization.names.map(elm => [elm, elm]),
					value: Array.from(regionalization.names)
				}
			}
			if (form.imt){
				// set form.imt as a deep copy of imts:
				form.imt.choices = Array.from(imts);
				form.imt.value || (form.imt.value = []); // assure empty list (not null)
			}
			// set flatfile Field the url for uploading a flatfile:
			if (form.flatfile){
				form.flatfile['data-url'] = this.flatfileUploadUrl;
			}
		}
		// setup the errors dict:
		for(var key of Object.keys(this.componentProps)){
			this.errors[key] = this.initialErrorMsg || "";
		}
	},
	computed: {
		selComponentProps(){  // https://stackoverflow.com/a/43658979
			return this.componentProps[this.selComponent];
		},
		errorMsg(){
			return this.errors[this.selComponent];
		}
	},
	methods: {
		setComponent(name){
			this.selComponent = name;
			this.setUrlInBrowser(name);
		},
		setUrlInBrowser(menu){
			var location = window.location;
			if (!location.pathname.startsWith(`/${menu}`)){
				var newHref = `${location.origin}/${menu}`
				// https://developer.mozilla.org/en-US/docs/Web/API/History_API
				window.history.replaceState({}, document.title, newHref);
			}
			return false; // in case accessed from within anchors
		},
		// These functions are called when this.httpClient.post is called:
		postRequestStarted(){
			this.clearErrors();
			this.loading = true;
		},
		postRequestEnded(){
			this.loading = false;
		},
		postRequestFailed(response){
			var errData = (response.response || {}).data;
			if (errData instanceof ArrayBuffer){
				// sometimes we might want to download png and json, we then
				// need to return an ArrayBuffer (see download.js).
				// The ArrayBuffer might "hide" a JSON formatted string. Thus,
				// try to convert to string and then json.parse:
				try{
					// copied from: https://developers.google.com/web/updates/2012/06/How-to-convert-ArrayBuffer-to-and-from-String
					// Uint8 because we send data as UTF8
					errData = JSON.parse(String.fromCharCode.apply(null, new Uint8Array(errData)));
				}catch(exc){
					errData = {};
				}
			}
			var error = (errData || {}).error || {};
			// set the global error message:
			this.setError(error.message || response.message ||  'Unknown error');
		},
		clearErrors(){
			this.setError('');
			// clear all param-specific errors in the current form, if found:
			for (var [name, form] of this.forms()){
				if (name === this.selComponent){
					Object.keys(form).forEach(fieldname => {
						form[fieldname].error = '';
					});
				}
			}
		},
		setError(error){
			this.errors[this.selComponent] = error;
		},
		forms(){
			var ret = [];
			Object.keys(this.componentProps).forEach(name => {
			   var compProps = this.componentProps[name];
			   if (typeof compProps === 'object'){
				   Object.keys(compProps).forEach(pname => {
					   var elm = compProps[pname];
					   for (element of (Array.isArray(elm) ? elm : [elm])){
						   if (this.isFormObject(element)){
							   ret.push([name, element]);
						   }
					   }
				   });
			   }
			});
			return ret;
		},
		isFormObject(obj){
			// global function returning true if `obj` is a form Object, i.e. an Object where each of its
			// properties is a form field name (string) mapped to the form field (Object)
			if (typeof obj !== 'object'){
				return false;
			}
			// check if all form fields have two mandatory properties of the Object: val and err (there are more,
			// but the two above are essential)
			return Object.keys(obj).every(key => {
				var elm = obj[key];
				return (typeof elm === 'object') && ('value' in elm) && ('error' in elm);
			});
		}
	}
};

class HTTPClient{
	constructor(defaultConfig, ...listeners){
		this.postfuncDefaultConfig = defaultConfig || {};
		this.listeners = listeners || [];
	}
	post(url, data, config){
		var config = Object.assign(config || {}, this.postfuncDefaultConfig);
		var jsonData = data || {};
		var ls = this.listeners || [];
		// emit the starting of a POST:
		ls.forEach(l => {if(l.postRequestStarted){l.postRequestStarted();}});
		// merge passed config with default config in a new config Object:
		var config = Object.assign(config || {}, this.postfuncDefaultConfig);
		var jsonData = data || {};
		return axios.post(url, jsonData, config).then(response => {
			ls.forEach(l => {if(l.postRequestCompleted){l.postRequestCompleted(response);}});
			// allow chaining this promise from sub-components:
			return response;  // https://github.com/axios/axios/issues/1057#issuecomment-324433430
		}).catch(response => {
			ls.forEach(l => {if(l.postRequestFailed){l.postRequestFailed(response);}});
			// allow chaining this promise from sub-components:
			throw response;   // https://www.peterbe.com/plog/chainable-catches-in-a-promise
		}).finally(() => {
			ls.forEach(l => {if(l.postRequestEnded){l.postRequestEnded();}});
		});
	}
	download(url, postData){
		/**
		 Send a POST request and download the response data on the client OS.

		 The responses attributes 'content-disposition' ('attachment; filename=...')
		 and 'content-type' must be specified.

		 Those two attributes are enough ONLY for GET requests opened in a new tab or
		 window, but with AJAX POST requests (as in our case) the response is received
		 but no "save as" dialog pops up. Hence, the workaround implemented here.
		 */

		// the post function needs to have the 'responseType' set in order
		// to work with `window.URL.createObjectURL` (info extracted from the "messy":

		this.post(url, postData, {responseType: 'arraybuffer'}).then(response => {
			// ref on `responseType` above (long thread with several outdated hints):
			// https://stackoverflow.com/questions/8022425/getting-blob-data-from-xhr-request
			if (response && response.data){
				var filename = (response.headers || {})['content-disposition'];
				if (!filename){ return; }
				var iof = filename.indexOf('filename=');
				if (iof < 0){ return; }
				filename = filename.substring(iof + 'filename='.length);
				if (!filename){ return; }
				var ctype = (response.headers || {})['content-type'];
				this.save(response.data, filename, ctype);
			}
		});
	}
	saveAsJSON(data, filename){
		/**
		 Save the given JavaScript Object `data` on the client OS as JSON
		 formatted string

		 Parameters:
		 data: the JavaScript Object or Array to be saved as JSON
		 */
		var sData = JSON.stringify(data, null, 2);  // 2 -> num indentation chars
		this.save(sData, filename, "application/json");
	}
	save(data, filename, mimeType){
		/**
		 Saves data with the given filename and mimeType on the client OS

		 Parameters:
			data: a Byte-String (e.g. JSOn.stringify) or an ArrayBuffer
				(https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/ArrayBuffer)
			filename: the string that is used as default name in the save as dialog
			mimeType: s atring denoting the MIME type
				 (https://developer.mozilla.org/en-US/docs/Web/HTTP/Basics_of_HTTP/MIME_types/Complete_list_of_MIME_types)
		 */
		var blob = new Blob([data], {type: mimeType});
		var downloadUrl = window.URL.createObjectURL(blob);
		var downloadAnchorNode = document.createElement('a');
		downloadAnchorNode.setAttribute("href", downloadUrl);
		downloadAnchorNode.setAttribute("download", filename);
		document.body.appendChild(downloadAnchorNode); // required for firefox
		downloadAnchorNode.click();
		downloadAnchorNode.remove();
		// as we removed the node, we should have freed up memory,
		// but let's be safe:
		URL.revokeObjectURL( downloadUrl );
	}
	createDownloadActions(downloadUrl, data){
		/* Return an Array of for downloading on the client OS) the given data.
		The returned Array has elements of the form `[format, download_callback]`,
		where format is 'json' 'csv', 'csv (comma separated)'. See <plot-div> and
		<testing-table> components for details

		 Parameters:
		  downloadUrl: a string identifying a download url, usually sent from the server
		  data: the data returned from a response (e.g., trellis residuals or
			testing data) that needs to be downloaded
		*/
		// Populate with the data to be downloaded as non-image formats:
		var downloadActions = [];
		// Download as JSON does not need to query the server, the data is here:
		downloadActions.push(["json", () => {
			var filename =  downloadUrl.split('/').pop() + '.json';
			this.saveAsJSON(data, filename);
		}]);
		// CSV download actions send data to the server and expects back converted:
		downloadActions.push(["text/csv", () => {
			var url =  downloadUrl + '.csv';
			this.download(url, data);
		}]);
		downloadActions.push(["text/csv, decimal comma", () => {
			var url =  downloadUrl + '.csv_eu';
			this.download(url, data);
		}]);
		return downloadActions;
	}
}