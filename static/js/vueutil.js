/** 
 * Add global property / method / directives to Vue (https://vuejs.org/v2/guide/plugins.html) 
*/
Vue.use({
    install : function (Vue, options) {
    	// defines ColorMap class extensing Map and retrievable via Vue.colorMap() (see below):
        class ColorMap extends Map {
            constructor() {
                super();
                this._defaults = {
                        index: 0,
                        colors: [
                        	'#1f77b4',  // muted blue
                            '#ff7f0e',  // safety orange
                            '#2ca02c',  // cooked asparagus green
                            '#d62728',  // brick red
                            '#9467bd',  // muted purple
                            '#8c564b',  // chestnut brown
                            '#e377c2',  // raspberry yogurt pink
                            '#7f7f7f',  // middle gray
                            '#bcbd22',  // curry yellow-green
                            '#17becf'   // blue-teal
                        ]
                }
            }
            get(key){
            	// sets a color mapping `key` if `key` is not in this Map
            	// (the color will be set incrementally based on `this._defauls.colors`).
            	// Eventually, it returns the color (hex string) mapped to `key`, as the superclass does
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
        	// global function returning true if `obj` is null, undefined or an empty Object
        	return (obj === null) || (obj === undefined) || ((typeof obj === 'object') && Object.keys(obj).length === 0);
        };
        Vue.isFormObject = function(obj){
        	// global function returning true if `obj` is a form Object, i.e. an Object where each of its
        	// properties is a form field name (string) mapped to the form field (Object)
            if (typeof obj !== 'object'){
                return false;
            }
            // check if all form fields have two mandatory properties of the Object: val and err (there are more,
            // but the two above are essential)
            return Object.keys(obj).every(key => {
                var elm = obj[key];
                return (typeof elm === 'object') && ('val' in elm) && ('err' in elm);
            });
        };
        Vue.init = function(data){
        	// Creates the globally available
        	// Vue.eGSIM Object via the data passed from the server via Django (see egsim.html)
	        var gsims = data;
	        // data is an Array of Arrays: each Array element represents a GSIM:
	        // [gsimName, [imtName1, ... imtNameN], TrtName, gsimOpenQuakeWarning] 
	        var gsimNames = Object.keys(gsims).sort();
	        var imtNames = new Set();
	        var trtNames = new Set();
	        gsimNames.forEach(gsimName => {
	        	gsims[gsimName][0].forEach(imt => imtNames.add(imt));
	        	trtNames.add(gsims[gsimName][1]);
	        });
	        // create the globally available Vue.eGSIM variable:
	        Vue.eGSIM = {
	        	gsims: gsimNames,
	            imts: Array.from(imtNames),
	            trts: Array.from(trtNames),
	        	imtsOf: function(gsim){ return gsims[gsim][0]; },
				trtOf: function(gsim){ return gsims[gsim][1]; },
				warningOf: function(gsim){ return gsims[gsim][2]; }	
	        }
	    };
    }
});
