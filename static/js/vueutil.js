// Add global property / method / directives to Vue (https://vuejs.org/v2/guide/plugins.html)
Vue.use({
    install : function (Vue, options) {
        // 1. add global method or property by means of which we can say:
        // var colors = Vue.colors()
        // var color = colors(
        class ColorMap extends Map {
            constructor() {
                super();
                this._defaults = {
                        index: 0,
                        colors: ['#1f77b4',  // muted blue
                            '#ff7f0e',  // safety orange
                            '#2ca02c',  // cooked asparagus green
                            '#d62728',  // brick red
                            '#9467bd',  // muted purple
                            '#8c564b',  // chestnut brown
                            '#e377c2',  // raspberry yogurt pink
                            '#7f7f7f',  // middle gray
                            '#bcbd22',  // curry yellow-green
                            '#17becf']  // blue-teal
                }
            }
            get(key){
                var color = super.get(key);
                if (color === undefined){
                    var colors = this._defaults.colors;
                    color = colors[(this._defaults.index++) % colors.length];
                    this.set(key, color);
                }
                return color;
            }
            transparentize(hexcolor, alpha) {
                // Returns the corresponding 'rgba' string of `hexcolor` with the given alpha channel ( in [0, 1], 1:opaque)
                // If `hexcolor` is an integer, it indicates the index of the default color to be converted
                if (typeof hexcolor == 'number'){
                    hexcolor = this._defaults.colors[parseInt(hexcolor) % this._defaults.colors.length];
                }
                if (hexcolor.length == 4){
                    var [r, g, b] = [hexcolor.substring(1, 2), hexcolor.substring(2, 3), hexcolor.substring(3, 4)];
                    var [r, g, b] = [r+r, g+g, b+b];
                }else if(hexcolor.length == 7){
                    var [r, g, b] = [hexcolor.substring(1, 3), hexcolor.substring(3, 5), hexcolor.substring(5, 7)];
                }else{
                    return hexcolor;
                }
                var [r, g, b] = [parseInt(r, 16), parseInt(g, 16), parseInt(b, 16)];
                return `rgba(${r}, ${g}, ${b}, ${alpha})`;
            }
        };
        Vue.colorMap = function () {
            return new ColorMap();
        };
        Vue.isEmpty = function(obj){
        	return (obj === null) || (obj === undefined) || ((typeof obj === 'object') && Object.keys(obj).length === 0);
        };
        Vue.isFormObject = function(obj){
            if (typeof obj !== 'object'){
                return false;
            }
            return Object.keys(obj).every(key => {
                var elm = obj[key];
                return (typeof elm === 'object') && ('val' in elm) && ('err' in elm);
            });
        };
        Vue.getMIMEType = function(filename){
        	// returns the mimeType associated to filename inferring it
        	// from its extension (ignoring the case). filename can also be the extension alsone,
        	// with or without prefixing period 
        	// Recognized extensions are: 'json', 'yaml', 'csv'. Any non-recognized  extension
        	// defaults to 'text/plain'
        	// Details here:
        	// https://developer.mozilla.org/en-US/docs/Web/HTTP/Basics_of_HTTP/MIME_types/Complete_list_of_MIME_types
        	// and here: https://stackoverflow.com/a/332159
        	var spl = (filename || "").split('.');
    		var ext = (spl.length > 1 ? spl[spl.length-1] : "").toLowerCase();
    		if (ext == 'json'){
    			mimeType = 'application/json';
    		}else if (ext == 'yaml'){
    			mimeType = 'application/x-yaml';
    		}else if (ext == 'csv'){
    			mimeType = 'text/csv';
    		}else{
    			mimeType = 'text/plain';
    		}
    		return mimeType;
        };
        Vue.download = function(content, filename, mimeType){
        	// downloads the file with given name `filename` and content `content`
        	// in the browser download directory.
        	// content can be any object, if mimeType is 'applicaion/json' and content
        	// is not a string, it will be converted with JSON.stringify, otherwise
        	// content.toString().
        	// If mimeType is missing or falsy, it will be inferred from filename
        	// (see Vue.getMIMEType)
        	// Supported filename extensions: (ignoring the case):
        	// json -> application/json
        	// csv -> text/csv
        	// yaml -> application/x-yaml
        	// (mimeType missing or falsy) -> text/plain
        	if (!mimeType){
        		mimeType = Vue.getMIMEType(filename);
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
        }
    }
});
