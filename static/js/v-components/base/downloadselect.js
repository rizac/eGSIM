/**
 * Implements a component for downloading data from within the browser
 */
Vue.component('downloadselect', {
    //https://vuejs.org/v2/guide/components-props.html#Prop-Types:
    props: {
    	// urls is an Array of [key (string), url] elements
    	// any url starting with 'file:///' will simply download the data
    	// with the file name specified after 'file:///'
        urls: {type: Array, default: () => { return []; }},
        // data is the data associated with this component passed to the
        // POST function (see below)
        data: {type: Object, default: () => { return {}; }},
        // post function to query via the selcted url:
        post: Function,
        // this is an id of the plotly element. If specified, the download as image is active:
        plotlydivid: {type: String, default: ''},  
    },
    data: function () {
    	// parse the given model, create an Array of labels and an Object of callbacks
    	var self = this;
    	var filename = '';  // inferred from the urls, used if plotlydivid is specified
    	var callbacks = this.urls.map(item => {
    		var [key, url] = item;
    		if (url.startsWith('file:///')){
    			url = url.substring('file:///'.length);
    			// use this filename and store it without extension, plotly needs it
    			// (if plotfivid is specified, see below):
    			if (!filename){
    				filename = this.splitext(url)[0];
    			}
    			var callback = () => {
    				self.download.call(self, self.data, url);
    			};
    		}else{
    			var callback = () => {
    				self.fetchAndDownload.call(self, url);
    			};
    		}
    		return [key, callback];
    	});
    	
    	if (this.plotlydivid && filename){
    		// if filename could not be inferred (see above), do not dislay
    		// download as image as the filename (without extension) is needed by plotly
    		callbacks = callbacks.concat([
    			['png (displayed plots)', () => {this.downloadAsImage('png')}],
    			['jpeg (displayed plots)', () => {this.downloadAsImage('jpeg')}],
    			['svg (displayed plots)', () => {this.downloadAsImage('svg')}]
    		]);
    	}

    	var emptyValue = "/*:_\\" + new Date().getTime().toString();  // something not present in this.urls keys
    	return {
    		emptyValue: emptyValue,
    		selKey: emptyValue,
    		callbacks: callbacks,
    		// download options required by Plotly. Ignored if plotlyelement is missing/ falsy. Note that
	        // most of the image options are not used for the moment
	        downloadAsImgOptions: {
	            width: null,
	            height: null,
	            filename: filename,
	            // scale 5 increases the image size, thus increasing the resolution
	            // Note that you cannot provide any number (e.g. scale 10 raises Exception)
	            scale: 5
	        }
        }
    },
    created: function(){
    	// create an empty value and insert it at index 0:
    	
    },
    watch: {
    	'selKey': function (newVal, oldVal){
            // we do not attach onchange on the <select> tag because of this: https://github.com/vuejs/vue/issues/293
            for (item of this.callbacks){
            	if (item[0] === newVal){
            		item[1]();
            		break;
            	}
            }
            this.selKey = this.emptyValue;
        }
    },
    computed: {
    	// no-op
    },
    template: `<div v-if='callbacks.length' class='d-flex flex-row text-nowrap align-items-baseline'>
		<i class="fa fa-download"></i>
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
            	v-for='item in callbacks'
            	:value='item[0]'
            >
            	{{ item[0] }}
            </option>
        </select>
    </div>`,
    methods: {
    	fetchAndDownload: function(url){
			this.post(url, this.data).then(response => {
                if (response && response.data){
                	var filename = (response.headers || {})['content-disposition'];
                	if (filename){
	                    var iof = filename.indexOf('filename=');
	                    if (iof > -1){
	                    	filename = filename.substring(iof + 'filename='.length);
	                    	if (filename){
			                    this.download(response.data, filename);
			                }
		                }
	                }
                }
            });
		},
		downloadAsImage: function(format){  // format can be png, jpeg, svg
            
            if (!format){  // for safety
                return;
            }
            
        	var props = this.downloadAsImgOptions;

            // FIXME: 1. props.size = 5 seems to increase resolution (by simply increasing the size)
            // However, the fonts and the lines should be increased, too
            // 2. legend is not present. If we want to add a legend, better would be to do it automatically
            // (only one trace VISIBLE => no legend, otherwise yes), but then consider plotting on a new div, where
            // we temporarily set this.defaultlayout.showlegend=true (currently, by changing showlegedn on the fly
            // (e.g. in setBackround below) raises
            // 3. Font size is not preserved in the image. But this has lower priority, as it turns out the
            // font image (at least on Chrome + MacOsX) is a default Helvetica-like font which might be preferable
            // as very common and readable
            
            var props = Object.assign({}, props);  // Object.assign(target, ...sources);
            props.format = format;
            var elm = document.getElementById(this.plotlydivid);
            var [width, height] = [elm.offsetWidth, elm.offsetHeight];
            if (!(props.width)){
                props.width = (props.height ? width*props.height/height : width); // + 'px';
            }
            if (!(props.height)){
                props.height = (props.width ? height*props.width/width : height); // + 'px';
            }

            function setBackground(gd) {
                // https://community.plot.ly/t/plotly-toimage-background-color/8099
                
                // this function actually allows the user to configure the plot
                // before rendering it to imag (why is it called like this
                // in plotly?) but note that not all modifications work as expected:
                
                // the paper bg color is set to transparent by default. However,
                // jpeg does not support it and thus we would get black background.
                // Therefore:
                if(format == 'jpeg'){
                    gd._fullLayout.paper_bgcolor = 'rgba(255, 255, 255, 1)';
                }
                
                // this actually does not work (raises) if we change the showlegend:
                // thus, more work is needed to setting showlegend=true temporarily and then
                // drawing on a new div
                // gd._fullLayout.showlegend = true;
            }
            props.setBackground = setBackground;

            Plotly.downloadImage(elm, props);
	        
			/*
            // Plotly.toImage will turn the plot in the given div into a data URL string
            // toImage takes the div as the first argument and an object specifying image properties as the other
            Plotly.toImage(elm, {format: 'png', width: width, height: height}).then(function(dataUrl) {
                // use the dataUrl
            })
            */
        },
        download: function(content, filename, mimeType){
        	// downloads the file with given name `filename` and content `content`
        	// in the browser download directory.
        	// content can be any object, if mimeType is 'applicaion/json' and content
        	// is not a string, it will be converted with JSON.stringify, otherwise
        	// content.toString().
        	// If mimeType is missing or falsy, it will be inferred from filename
        	// (see this.getMIMEType)
        	// Supported filename extensions: (ignoring the case):
        	// json -> application/json
        	// csv -> text/csv
        	// yaml -> application/x-yaml
        	// (mimeType missing or falsy) -> text/plain
        	if (!mimeType){
        		mimeType = this.getMIMEType(filename);
        	}
        	if (typeof content !== 'string'){
        		content = mimeType === 'application/json' ? JSON.stringify(content, null, 4) : content.toString();
        	}
        	// Encode and download (for details see https://stackoverflow.com/a/30800715):
        	var encodedStr = encodeURIComponent(content);
		    var dataStr = `data:${mimeType};charset=utf-8,${encodedStr}`;
		    var downloadAnchorNode = document.createElement('a');
		    downloadAnchorNode.setAttribute("href",     dataStr);
		    downloadAnchorNode.setAttribute("download", filename);
		    document.body.appendChild(downloadAnchorNode); // required for firefox
		    downloadAnchorNode.click();
		    downloadAnchorNode.remove();
        },
        getMIMEType: function(filename){
        	// returns the mimeType associated to filename inferring it
        	// from its extension (ignoring the case). filename can also be the extension alsone,
        	// with or without prefixing period 
        	// Recognized extensions are: 'json', 'yaml', 'csv'. Any non-recognized  extension
        	// defaults to 'text/plain'
        	// Details here:
        	// https://developer.mozilla.org/en-US/docs/Web/HTTP/Basics_of_HTTP/MIME_types/Complete_list_of_MIME_types
        	// and here: https://stackoverflow.com/a/332159
        	var ext = this.splitext(filename)[1].toLowerCase();
    		if (ext == '.json'){
    			mimeType = 'application/json';
    		}else if (ext == '.yaml'){
    			mimeType = 'application/x-yaml';
    		}else if (ext == '.csv'){
    			mimeType = 'text/csv';
    		}else{
    			mimeType = 'text/plain';
    		}
    		return mimeType;
        },
        splitext: function(filename){
        	// same as Python os.path.splitext, returns [filename, ext_with_dot]
        	var lio = filename.lastIndexOf('.');
        	if (lio > -1){
        		return [filename.substring(0, lio), filename.substring(lio, filename.length)];
        	}
        	return [filename, ""];
        }
    }
})