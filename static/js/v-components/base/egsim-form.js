/* Form components */

/* Sends Post request with Form objects as data.
Base class for Form components. See README.md for details */
var FormDataHTTPClient = {
	props: {
		form: Object,  // field names mapped to Objects describing <input>s or <select>
					   // (the keys 'value' and 'error' are mandatory)
		url: String,  // the request URL after form submission
	},
	methods: {
		postFormData(url=null){
			// send a POST request to `url` (defaults to `this.url`) with this form data
			if(!url){
				url = this.url;
			}
			// send a post request to the given url using this.form as POST data. Returns
			// a `Promise` object that can be chained (see e.g. `this.request`)
			for (var key of Object.keys(this.form)){  // clear errors first
				this.form[key].error = "";
			}
			var [data, config] = this.getPostDataAndConfig();
			return axios.post(url, data, config).then(response => {
				if (response && response.data){
					return response; // allows .then on the Promise
				}
				// throw new Error('response empty');  // should allow to .catch the promise in case
			}).catch(response => {
				var errData = (response.response || {}).data;
				var error = (errData || {}).error || {};
				// set the data field errors
				var errors = error.errors || [];
				for (var err of errors){
					var paramName = err.location;
					for (attrName of Object.keys(this.form)){
						var formField = this.form[attrName];
						if (formField.name === paramName){
							formField.error = err.message || 'invalid: unknown error';
						}
					}
				}
				throw response;   // https://www.peterbe.com/plog/chainable-catches-in-a-promise
			});
		},
		getPostDataAndConfig(){
			// Returns the arguments for a POSt request in the form of the Array
			// [postData, config], where data is either an Object or a
			// FormData object, and config is an Object with varying keys depending on
			// the data of `this.form` (basically: this.form has files or not)
			var form = this.form;
			var hasFiles = Object.keys(form).some(elm => form[elm].value instanceof File);
			if (hasFiles){
				const config = {
					headers: {
						'content-type': 'multipart/form-data'
					}
				};
				return [this.formToFormData(), config];
			}
			return [this.formToJSON(), {}];
		},
		formToJSON(){
			// Return `this.form` as JSON serializable Object
			data = {};
			for (var key of Object.keys(this.form)){
				var field = this.form[key];
				if (!field.disabled){
					// assign value to object up to be sent, use the "name" as key:
					data[field.name] = field.value;
				}
			}
			return data;
		},
		formToFormData(){
			// snippet from:
			// https://www.codegrepper.com/code-examples/javascript/axios+upload+a+multipart%2Fform-data
			const formData = new FormData();
			var formObj = this.formToJSON();
			for (var name of Object.keys(formObj)){
				// https://stackoverflow.com/a/63340869:
				// in form-data content, null will be converted to "null". Either replace
				// (but how to get a default?) or simply remove:
				var val = formObj[name];
				if ((val !== null) && (val !== undefined)){
					formData.append(name, val);
				}
			}
			return formData;
		},
	}
};

/**Egsim form used in trellis, residuals, testing. Main features:
- emits a 'submitted' on response successfully received, after submit
- implements a toolbar for IO operations such as get Form in YAML or JSON config
- Deals with hiding and transforming the form into a dialog popup after first submit*/
EGSIM.component('egsim-form', {
	mixins: [FormDataHTTPClient, DataDownloader],
	props :{
		downloadUrl: String,  // url for downloading the current form as config yaml/json
		visibilityToggle: {type: Boolean, default: true},  // variable to toggle form visibility from external components
	},
	data() {
		return {
			show: true,
			showAsDialog: false,  // appearance control
			requestURL: ''
		}
	},
	emits: ['submitted'],
	methods: {
		submit(){
			this.postFormData().then(response => {
				this.show = !this.show;
				this.showAsDialog = true;
				setTimeout(() => {
					// notify asynchronously after the form has been hidden:
					this.$emit('submitted', response);
				}, 200);
			});
		},
		// toolbar methods:
		fetchRequestURL(){
			/* Fetch the current config (request) as dict and builds this.requestURL
			Returns an axios Promise to which a user can attach functions to
			be executed when the POST request returns successfully
			*/
			return this.postFormData(this.downloadUrl + '.json').then(response => {
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
					this.requestURL = retUrl;
				}
			});
		},
		copyRequestURL(src){
			var targetElement = src.currentTarget; // the button
			// aria-label is used by balloon.css to display the tooltip
			// store the current one:
			var ariaLabel = targetElement.getAttribute('aria-label');
			var successful = this.copyText(this.$refs.copyURLInput);
			// restore the old aria-label
			if (ariaLabel){
				targetElement.setAttribute('aria-label', successful ? 'Copied' : 'Unable to copy');
				setTimeout(() => {
					targetElement.setAttribute('aria-label', ariaLabel);
				}, 1000);
			}
		},
		copyText(element){
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
		readLocalJSON(src){
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
					form[key].value = obj[key];
				}
			};
			reader.readAsText(file);
		},
		downloadTriggered(event){
			var selectElement = event.target;
			if(selectElement.selectedIndex > 0){
				this.downloadFormAsConfig(event.target.value);
			}
			selectElement.selectedIndex = 0;
		},
		downloadFormAsConfig(format){
			var url = this.downloadUrl + "." + format;
			// note that when sending this.formToJSON() with an uploaded File
			// object, the browser converts it to {}. By chance, this means that
			// the backend Django Form will see no flatfile and thus
			// the returned 'flatfile error' will make sense. We could
			// try a better message (e.g. 'provided flatfile non serializable')
			// but it's actually quite complex
			this.download(url, this.formToJSON());  // defined in DataDownloader
		}
	},
	watch: {
		visibilityToggle(newVal, oldVal){
			this.show = !this.show;
		},
		form: {
			deep: true,
			handler(newVal, oldVal){
				// changing the form reset requestURL. We should listen only for each form.value
				// field actually, but it's simple like this:
				if (this.requestURL){
					this.requestURL = "";
				}
			}
		}
	},
	template: `<form novalidate @submit.prevent="submit"
		class="flex-column position-relative pb-4 align-self-center"
		:class="[showAsDialog ? ['shadow', 'border', 'bg-body', 'mt-1', 'mb-3'] : '']"
		style="flex: 1 1 auto;z-index:10; border-color:rgba(0,0,0,.3) !important"
		:style="{'display': show ? 'flex' : 'none'}">

		<div class="d-flex flex-column" style="flex: 1 1 auto">

			<div class='d-flex flex-row justify-content-center align-items-baseline p-1 mb-3 bg-light'>

				<button type="button" onclick='this.nextElementSibling.click()'
						data-balloon-pos="down" data-balloon-length="medium"
						aria-label="Load a configuration from a local JSON-formatted text file. This can be, e.g., a configuration previously saved as JSON (see 'Download as')"
						class="btn btn-outline-dark border-0">
					<i class="fa fa-upload"></i>
				</button>
				<!-- NOTE: the control below must be placed immediately after the control above! -->
				<input style='display:none' type="file" id="file-input" @change='readLocalJSON'>

				<select @change="downloadTriggered" style='width:initial !important'
						class="ms-2 form-control form-control-sm bg-transparent border-0"
						data-balloon-pos="down" data-balloon-length="medium"
						aria-label="Download the current configuration as text file. The file content can then be used in your custom code as input to fetch data (see POST requests in the API documentation for details)">
					<option value="">Download as:</option>
					<option value="json">JSON</option>
					<option value="yaml">YAML</option>
				</select>

				<button type="button" @click='fetchRequestURL'
						data-balloon-pos="down" data-balloon-length="medium"
						aria-label="Show the API URL of the current configuration. The URL can be used in your custom code to fetch data (see GET requests in the API documentation for details). You can also paste it in the browser to see the results (e.g., Firefox nicely displays JSON formatted data)"
						class="btn btn-outline-dark border-0 ms-2">
					<i class="fa fa-link"></i>
				</button>

				<input ref="copyURLInput" type='text' v-model='requestURL'
					   :style= "requestURL ? {} : { 'visibility': 'hidden'}"
					   class="form-control form-control-sm ms-2 bg-transparent border-0"
					   style="flex: 1 1 auto;width:initial !important"/>

				<button type="button" v-show='requestURL' @click="copyRequestURL"
						aria-label="Copy the URL" data-balloon-pos="down" data-balloon-length="medium"
						class="btn btn-outline-dark border-0">
					<i class="fa fa-copy"></i>
				</button>

				<button type="button" v-show='showAsDialog' @click="show=!show"
						aria-label="Close form window" data-balloon-pos="down" data-balloon-length="medium"
						class="btn btn-outline-dark border-0 ms-2">
					<i class="fa fa-times"></i>
				</button>

			</div>

			<div class="d-flex flex-row" :class="[showAsDialog ? ['mx-4'] : '']"
				 style="flex: 1 1 auto">
				<div class="d-flex flex-column" style="flex: 1 1 auto">
					<slot name="left-column"></slot>
				</div>

				<div class="d-flex flex-column ms-4" style="flex: 1 1 auto">

					<slot name="right-column"></slot>

					<div class='d-flex flex-row justify-content-center mt-4'>
						<div style='flex: 1 1 auto'></div>
						<button type="submit" class="btn btn-primary">
							<i class="fa fa-play"></i> Display results
						</button>
					</div>
				</div>
			</div>
		</div>
	</form>`
});
