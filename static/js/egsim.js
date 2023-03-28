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
	template: `<nav class="d-flex flex-row navbar-dark bg-dark align-items-center position-relative" id='egsim-nav' style='color:lightgray'>
		<a v-for="n in components.names" class='menu-item' :class='selComponent == n ? "selected" : ""' @click="setComponent(n)">
			<i :class="['fa', components.tabs[n].icon, 'me-1']"></i>
			<span>{{ components.tabs[n].title }}</span>
		</a>
		<div class='menu-item invisible d-flex flex-row bg-danger text-white align-items-baseline'
			 style="flex: 1 1 auto" :style="{visibility: errorMsg ? 'visible !important' : 'hidden'}">
			<i class="fa fa-exclamation-circle" style="color:white"></i>&nbsp;
			<input type="text" :value="errorMsg" readonly class="p-0 m-0"
				   style="flex: 1 1 auto;background-color: rgba(0,0,0,0);color: white;outline: none;border-width: 0px;"/>
			<i class="fa fa-times ms-2" @click='setError("")' style="cursor: pointer"></i>
		</div>
		<div>
			<a class="menu-item" href="#" @click="toggleOptionsMenu">
				<i class="fa fa-bars"></i>
			</a>
			<div style="transform: scaleY(0);z-index:100; transition: transform .25s ease-out; transform-origin: top;"
				 ref='options-menu' class="m-0 d-flex flex-column bg-dark position-absolute end-0">
				<a style="display:none" class="menu-item" :href='newpageURLs.api' target="_blank">
					<i class="fa fa-info-circle"></i> <span>Tutorial (API Doc)</span>
				</a>
				<a class="menu-item" :href='newpageURLs.ref_and_license' target="_blank">
					<i class="fa fa-address-card-o"></i> <span>References & License</span>
				</a>
				<a class='menu-item' :href='newpageURLs.imprint' target="_blank">
					Imprint
				</a>
				<a class='menu-item' :href='newpageURLs.data_protection' target="_blank">
					Data Protection
				</a>
			</div>
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
		this.addCss();
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
			this.init(data.gsims, data.imt_groups, data.flatfile, data.regionalizations);
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
		addCss(){
			var style = document.createElement('style');
			style.type = 'text/css';
			style.innerHTML = this.getCss();
			document.head.appendChild(style);
		},
		getCss(){
			// custom css style to be added to <head>. Mainly for transition stuff (progressbar / components)
			return `
				@media (max-width: 975px){  /* narrow  screen (< 975px) */
					nav > .menu-item span { display: none !important; } /* hide menu texts */
				}
				/* waitbar. For info see: https://www.pexels.com/blog/css-only-loaders/ */
				.loader, .loader:before { height: 10px; }
				.loader {
					width: 100%;
					position: relative;
					overflow: hidden;
					background-color: #999;
				}
				.loader:before{
					display: block;
					position: absolute;
					content: "";
					left: -200px;
					width: 200px;
					background-color: #ffc107; /*#a2cd7e;*/
					animation: loading 2s linear infinite;
				}
				@keyframes loading {
					from {left: -200px; width: 30%;}
					50% {width: 30%;}
					70% {width: 70%;}
					80% { left: 50%;}
					95% {left: 120%;}
					to {left: 100%;}
				}
				/* Transitions when activating a main component: https://vuejs.org/guide/built-ins/transition.html */
				.fade-enter-active, .fade-leave-active { transition: opacity .4s ease-out; }
				.fade-enter, .fade-leave-to { opacity: 0; }
				/* nav menus anchors */
				nav#egsim-nav > * {  }
				nav#egsim-nav .menu-item { border-radius: .375rem; padding: .5rem; margin: .375rem; }
				nav#egsim-nav a.menu-item { color: lightgray; cursor: pointer; }
				nav#egsim-nav a.menu-item:hover, nav#egsim-nav a.menu-item.selected  { color: white; background-color: rgba(202, 214, 222, .25) }
				code{color: inherit;}
				/* tabs (e.g., flatfile page) */
				.nav-tabs .nav-link {color: inherit; opacity: .8;}
				.nav-tabs .nav-item.show .nav-link, .nav-tabs .nav-link.active {color: var(--bs-primary); opacity: 1; background-color: inherit}
			`;
		},
		init(gsims, imtGroups, flatfile, regionalizations){
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
					form.gsim['data-regionalizations'] = Vue.markRaw(regionalizations)
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
			var elm = this.$refs['options-menu'];
			var isShowing = () => { return elm.getAttribute('data-showing') === '1' };
			// define a function that hides / shows the popup:
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
				// show popup but attach also a listener to hide the
				// popup for any keystroke or mouse click everywhere on the document:
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
	tooltip.style.cssText = "font-size:smaller; font-family: Verdana, Tahoma, sans-serif; display:inline-block; position:fixed; overflow:hidden; z-index:100000; transform:scaleY(0); transition:transform .25s ease-out;";
	document.body.appendChild(tooltip);
	// functions to show / hide tooltip:
	function showTooltip(evt){
		var target = evt.target;
		var tooltipContent = target.getAttribute ? target.getAttribute('aria-label') : "";
		if(!tooltipContent){ return; }  // for safety
		tooltip.innerHTML = tooltipContent + "";
		// position tooltip
		var fsize = parseFloat(window.getComputedStyle(tooltip).getPropertyValue('font-size')); // in px
		if (isNaN(fsize) || fsize === null){ fsize = 18; }  // set it relatively big
		var rect = target.getBoundingClientRect();
		// tooltip vertical dimensions (max-height, top, bottom):
		var winH = window.innerHeight;   // window (viewport) height
		tooltip.style.height = 'auto';
		var spaceAbove = rect.top;
		var spaceBelow = winH - rect.bottom;  // note: rect.bottom = rect.top + rect.height
		if (spaceBelow > spaceAbove){  // place tooltip below
			tooltip.style.top = `${rect.bottom + 1.5*fsize}px`;
			tooltip.style.bottom = '';
			var tooltipMaxHeightPx = winH- rect.bottom - 3*fsize;
		}else{  // place tooltip above
			tooltip.style.top = '';
			tooltip.style.bottom = `${winH - rect.top + 1.5*fsize}px`;
			var tooltipMaxHeightPx = rect.top - 3*fsize;
		}
		tooltip.style.maxHeight = `${tooltipMaxHeightPx}px`;
		// tooltip horizontal dimensions (max-width, left, right):
		var winW = window.innerWidth;  // window (viewport) width, in px
		var maxWidth = '';  // tooltip max width (px)
		var spaceLeft = rect.right;  // note: rect.right = rect.left + rect.width
		var spaceRight = winW - rect.left;
		if (spaceRight > spaceLeft){  // align tooltip and target left sides
			tooltip.style.left = `${rect.left}px`;
			tooltip.style.right = '';
			maxWidth = winW - rect.left - 1.5 * fsize;
		}else{  // align tooltip and target right sides
			tooltip.style.left = '';
			tooltip.style.right = `${winW - rect.right}px`;
			maxWidth = rect.right - 1.5 * fsize;
		}
		// set max width according to font size, if available:
		tooltip.style.width = 'auto';
		tooltip.style.maxWidth = `${parseInt(100*maxWidth/winW)}vw`;
		// set scale and stop event propagation:
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