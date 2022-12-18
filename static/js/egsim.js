/** base skeleton implementation for the main Vue instance. See egsim.html */
const EGSIM = Vue.createApp({
	data(){
		return {
			// NOTE: do not prefix data variable with underscore: https://vuejs.org/v2/api/#data
			loading: false,
			errors: {},  // populated in created()
			selComponent: '',
			components: {}, // component names (e.g. 'trellis') -> Object
			newpageURLs: {}
		}
	},
	template: `<nav class="d-flex flex-row navbar-dark bg-dark align-items-center position-relative" id='egsim-nav'
		style='color:lightgray'>
		<a v-for="n in components.names" class='menu-item ms-3' :style='menuStyle(n)'
		   @click="setComponent(n)" onmouseover="this.style.color='white'" onmouseout="this.style.color='inherit'">
			<i :class="['fa', components.tabs[n].icon, 'me-1']"></i>
			<span>{{ components.tabs[n].title }}</span>
		</a>
		<div class='invisible d-flex flex-row m-2 p-2 bg-danger text-white rounded-2 align-items-baseline'
			 style="flex: 1 1 auto" :style="{visibility: errorMsg ? 'visible !important' : 'hidden'}">
			<i class="fa fa-exclamation-circle" style="color:white"></i>&nbsp;
			<input type="text" :value="errorMsg" readonly
				   style="flex: 1 1 auto;background-color: rgba(0,0,0,0);color: white;outline: none;border-width: 0px;"/>
			<i class="fa fa-times ms-2" @click='setError("")' style="cursor: pointer"></i>
		</div>
		<a class="menu-item me-3" href="#" @click="toggleOptionsMenu"
		   :style='menuStyle()' onmouseover="this.style.color='white'" onmouseout="this.style.color='inherit'">
			<i class="fa fa-bars"></i>
		</a>
		<div style="transform: scaleY(0);z-index:100; transition: transform .25s ease-out; transform-origin: top;"
			 ref='options-menu' class="sub-menu d-flex flex-column p-2 bg-dark position-absolute end-0">
			<a class="p-2" :style='menuStyle()' onmouseover="this.style.color='white'" onmouseout="this.style.color='inherit'"
			   :href='newpageURLs.api' target="_blank">
				<i class="fa fa-info-circle"></i> <span>Tutorial (API Doc)</span>
			</a>
			<a class="p-2" :style='menuStyle()' onmouseover="this.style.color='white'" onmouseout="this.style.color='inherit'"
			   :href='newpageURLs.ref_and_license' target="_blank">
				<i class="fa fa-address-card-o"></i> <span>References & License</span>
			</a>
			<a class='p-2' :href='newpageURLs.imprint' target="_blank"
			   :style='menuStyle()' onmouseover="this.style.color='white'" onmouseout="this.style.color='inherit'">
				Imprint
			</a>
			<a class='p-2' :href='newpageURLs.data_protection' target="_blank"
			   :style='menuStyle()' onmouseover="this.style.color='white'" onmouseout="this.style.color='inherit'">
				Data Protection
			</a>
		</div>
	</nav>

	<div class='d-flex flex-column position-relative' style="flex: 1 1 auto">
		<div v-show='loading' class="position-absolute start-0 end-0" style='z-index:200;'>
			<div class="loader"></div>
		</div>
		<div v-if="!!selComponent" class='d-flex m-0' style="flex: 1 1 auto">
			<transition name="fade" mode="out-in">
				<keep-alive>
					<component v-bind:is="selComponent"
							   v-bind="selComponentProps"
							   :class="['home', 'apidoc'].includes(selComponent) ? 'm-0' : 'm-3 mt-4'">
					</component>
				</keep-alive>
			</transition>
		</div>
	</div>`,
	created(){
		this.configureHTTPClient();
	},
	mounted(){
		setupTooltipObserver(this.$el.parentNode);   // https://vuejs.org/api/component-instance.html#el
		cfg = {
			headers: { 'content-type': 'application/json; charset=utf-8' }
		};
		data = {
			browser: this.getBrowser(),
			selectedMenu: window.location.pathname.split("/").pop()
		};
		axios.post('/init_data', data, cfg).then(response => {
			data = response.data;
			this.components = data.components;
			// setup the errors dict:
			for(var key of Object.keys(this.components.props)){
				this.errors[key] = data.invalid_browser_message || "";
			}
			this.newpageURLs = data.newpage_urls;
			this.init(data.gsims, data.imt_groups, data.flatfile, data.regionalization);
			this.selComponent = data.sel_component;
		});
	},
	computed: {
		selComponentProps(){  // https://stackoverflow.com/a/43658979
			return this.components.props[this.selComponent];
		},
		errorMsg(){
			return this.errors[this.selComponent];
		}
	},
	methods: {
		menuStyle(componentName){
			var ret = { color: 'lightgray', cursor: 'pointer' };
			if (componentName === this.selComponent){
				ret.color = 'white'
			}
			return ret;
		},
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
		configureHTTPClient(){
			// Configures the HTTPClient (currently axios library)

			axios.interceptors.request.use((config) => {
				// Do something before request is sent
				this.setError('');
				this.loading = true;
				return config;
			}, (error) => {
				this.setError(this.getErrorMsg(error));
				this.loading = false;
				throw error;
			});

			// Add a response interceptor
			axios.interceptors.response.use((response) => {
				this.loading = false;
				return response;
			}, (error) => {
				this.setError(this.getErrorMsg(error));
				this.loading = false;
				throw error;
			});
		},
		init(gsims, imtGroups, flatfile, regionalization){
			// Create a "template" Array of gsims and imts, to be copied as field choices
			var reg = /[A-Z]+[^A-Z0-9]+|[0-9]+|.+/g; //NOTE safari does not support lookbehind/aheads!
			// converts the gsims received from server from an Array of Arrays to an
			// Array of Objects:
			var imts = new Set();
			var gsimObjects = gsims.map(elm => {  // elm: Array of 2 or 3 elements
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
			// create global like Object:
			gsimObjects = Object.freeze(Vue.markRaw(gsimObjects));
			// convert imts (Set) into Array:
			imts = Array.from(imts);
			// Setup fields data:
			for (var [name, form] of this.forms()){
				if (form.gsim){
					// set form.gsim.choices as a deep copy of gsimObjects:
					form.gsim.choices = gsimObjects;
					form.gsim.value || (form.gsim.value = []); // assure empty list (not null)
					form.gsim['data-regionalization'] = Vue.markRaw({
						url: regionalization.url,
						choices: regionalization.names.map(elm => [elm, elm]),
						value: Array.from(regionalization.names)
					})
				}
				if (form.imt){
					// set form.imt as a deep copy of imts:
					form.imt.choices = Array.from(imts);
					form.imt.value || (form.imt.value = []); // assure empty list (not null)
				}
				// set flatfile Field the url for uploading a flatfile:
				if (form.flatfile){
					form.flatfile['data-url'] = flatfile.upload_url;
					form.flatfile.choices = flatfile.choices;
				}
			}
		},
		getErrorMsg(errorResponse){
			// get the error message (str) from an axios errorResponse and return it
			var errData = (errorResponse.response || {}).data;
			if (errData instanceof ArrayBuffer){
				// this might happen if, e.g., we requested png. The JSON error response
				// is then returned in the same ArrayBuffer format, so:
				try{
					// see https://developers.google.com/web/updates/2012/06/How-to-convert-ArrayBuffer-to-and-from-String
					// (Uint8 because we send data as UTF8)
					errData = JSON.parse(String.fromCharCode.apply(null, new Uint8Array(errData)));
				}catch(exc){
					errData = {};
				}
			}
			var error = (errData || {}).error || {};
			return error.message || errorResponse.message ||  'Unknown error';
		},
		setError(error){
			this.errors[this.selComponent] = error;
		},
		forms(){
			var ret = [];
			Object.keys(this.components.props).forEach(name => {
			   var compProps = this.components.props[name];
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
		},
		getBrowser() {
			// Return the browser name (string) and version (numeric or null).
			// This code uses heuristics and should be used to display information only
			// (https://stackoverflow.com/a/16938481)
			var [name, version ] = ['', null];
			var ua=navigator.userAgent;
			var tem;
			var M=ua.match(/(opera|chrome|safari|firefox|msie|trident(?=\/))\/?\s*(\d+)/i) || [];
			if(/trident/i.test(M[1])){
				tem=/\brv[ :]+(\d+)/g.exec(ua) || [];
				name = 'ie';
				version = tem[1];
			}else if(M[1]==='Chrome' && (tem=ua.match(/\bOPR|Edge\/(\d+)/))!=null){
				name = 'opera';
				version = tem[1];
			}else{
				M = M[2] ? [M[1], M[2]] : [navigator.appName, navigator.appVersion, '-?'];
				if((tem=ua.match(/version\/(\d+)/i))!=null){
					M.splice(1,1,tem[1]);
				}
				name = (M[0] || "").toLowerCase();
				version = M[1];
			}
			var isnan = isNaN(parseFloat(version));
			return {'name': name, 'version': isnan ? null : parseFloat(version)};
		},
		toggleOptionsMenu(evt){
			var elm = this.$refs['options-menu']; // document.getElementById('options-menu');
			var isShowing = () => { return elm.getAttribute('data-showing') === '1' };
			function popup(visible, timeout=0){
				if (isShowing() == visible){ return; }
				setTimeout(() => {
					elm.style.transform = visible ? 'scaleY(1)' : 'scaleY(0)';
					elm.setAttribute('data-showing', visible ? '1': '');
				}, timeout);
			}

			if (isShowing()){
				// hide component:
				popup(false);
			}else{
				evt.stopPropagation();
				// set top (for safety) and show component
				elm.style.top = `${document.getElementById('egsim-nav').offsetHeight}px`;
				// show popup:
				popup(true);
				function hidePopup(evt){
					if (!evt.type.startsWith('key') || evt.keyCode == 9){
						popup(false, 100);
						document.removeEventListener('click', hidePopup);
						document.removeEventListener('keydown', hidePopup);
					}
				}
				document.addEventListener('click', hidePopup);
				document.addEventListener('keydown', hidePopup);
			}
		}
	}
});


/* Register home page (simple) here: */
EGSIM.component('home', {
	props: {src: String},
	template: `<iframe style='flex: 1 1 auto' :src='src'></iframe>`
});


const DataDownloader = {
	methods: {
		download(url, postData, config){
			/** send `postData` to `url`, and download the response on the client OS */
			config = config || {};
			// provide a default responseType. For info (long thread with several outdated hints):
			// https://stackoverflow.com/questions/8022425/getting-blob-data-from-xhr-request
			if (!config.responseType){
				config.responseType = 'arraybuffer';
			}
			axios.post(url, postData, {responseType: 'arraybuffer'}).then(response => {
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
		},
		saveAsJSON(data, filename){
			/* Save the given JavaScript Object `data` on the client OS as JSON
			formatted string

			data: the JavaScript Object or Array to be saved as JSON
			*/
			var sData = JSON.stringify(data, null, 2);  // 2 -> num indentation chars
			this.save(sData, filename, "application/json");
		},
		save(data, filename, mimeType){
			/* Save `data` with the given filename and mimeType on the client OS

			data: a Byte-String (e.g. JSON.stringify) or an ArrayBuffer
				(https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/ArrayBuffer)
			filename: the string that is used as default name in the save as dialog
			mimeType: a string denoting the MIME type
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
	}
}

function setupTooltipObserver(observedRootElement){
	// Setup tooltips on elements with "aria-label" attr, showing the attr value as tooltip text
	// create tooltip <div>:
	var tooltip = document.createElement('div');
	tooltip.classList.add('shadow', 'p-2', 'bg-dark', 'bg-gradient', 'text-white');
	tooltip.style.cssText = "font-family: Tahoma, Verdana, sans-serif; display:inline-block; position:fixed; overflow:hidden; z-index:100000; transform:scaleY(0); transition:transform .25s ease-out;";
	document.body.appendChild(tooltip);
	// functions to show / hide tooltip:
	function showTooltip(evt){
		var target = evt.target;
		var tooltipContent = target.getAttribute ? target.getAttribute('aria-label') : "";
		if(!tooltipContent){ return; }  // for safety
		tooltip.innerHTML = tooltipContent + "";
		// position tooltip
		var M = 16;  // tooltip margin(s), in px
		var rect = target.getBoundingClientRect();
		// tooltip vertical dimensions (max-height, top, bottom):
		var winH = window.innerHeight;  // window (viewport) height
		tooltip.style.height = 'auto';
		var spaceAbove = rect.top;
		var spaceBelow = winH - rect.bottom;  // note: rect.bottom = rect.top + rect.height
		if (spaceBelow > spaceAbove){  // place tooltip below
			tooltip.style.top = `${rect.bottom + M}px`;
			tooltip.style.bottom = '';
			tooltip.style.maxHeight = `${winH- rect.bottom - 2*M}px`;
		}else{  // place tooltip above
			tooltip.style.top = '';
			tooltip.style.bottom = `${winH - rect.top + M}px`;
			tooltip.style.maxHeight = `${rect.top - 2*M}px`;
		}
		// define tooltip horizontal dimensions (max-width, left, right):
		var winW = window.innerWidth;  // window (viewport) width
		tooltip.style.width = 'auto';
		var spaceLeft = rect.right;  // note: rect.right = rect.left + rect.width
		var spaceRight = winH - rect.left;
		if (spaceRight > spaceLeft){  // align tooltip and target left sides
			tooltip.style.left = `${rect.left}px`;
			tooltip.style.right = '';
			tooltip.style.maxWidth = `${winW - rect.left -M}px`;
		}else{  // align tooltip and target right sides
			tooltip.style.left = '';
			tooltip.style.right = `${winW - rect.right}px`;
			tooltip.style.maxWidth = `${rect.right - M}px`;
		}
		tooltip.style.transform = 'scaleY(1)';
		evt.stopPropagation();  // for safety
	};
	function hideTooltip(evt){
		tooltip.style.transform='scaleY(0)';
	};
	// start observing all changes inside observedRootElement and attach/remove tooltip event listeners according to the aria-label attr:
	new MutationObserver((mutations) => {
		for (let mutation of mutations) {
			var target = mutation.target;
			var nodes = [];
			if (mutation.type == 'childList'){
				nodes = target.querySelectorAll('[aria-label], [data-tooltip-text]');
			}else if (mutation.type == 'attributes' && mutation.attributeName == 'aria-label') {
				nodes = [target];
			}
			for (var node of nodes){
				var tooltip = node.getAttribute('aria-label') || "";
				var tooltipRemainder = node.getAttribute('data-tooltip-text') || "";
				// tooltip empty / missing => remove event listener if tooltipReminder not empty
				// tooltip not empty => add event listener if tooltipReminder is different
				if (!tooltip && tooltipRemainder) {
					node.removeAttribute('data-tooltip-text');
					node.removeEventListener('mouseenter', showTooltip);
					node.removeEventListener('mousedown', hideTooltip);
					node.removeEventListener('mouseleave', hideTooltip);
				}else if (tooltip && tooltip != tooltipRemainder){
					node.setAttribute('data-tooltip-text', tooltip);
					node.addEventListener('mouseenter', showTooltip);
					node.addEventListener('mousedown', hideTooltip);
					node.addEventListener('mouseleave', hideTooltip);
				}
			}
		}
	}).observe(observedRootElement, {
		childList: true,
		attributes: true,
		subtree: true,
	});

}