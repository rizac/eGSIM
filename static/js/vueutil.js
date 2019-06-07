// Add global property / method / directives to Vue (https://vuejs.org/v2/guide/plugins.html)
Vue.use({
    install : function (Vue, options) {
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
    }
});
