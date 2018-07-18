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
            get asObject() {
                var ret = {};
                for (var key of this.keys()){
                    ret[key] = this.get(key);
                }
                return ret;
            }
        };
        Vue.colorMap = function () {
            return new ColorMap();
        }
    }
});
