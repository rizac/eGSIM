/** JSON layer wrapper class
 * <pre>inherits from {@link Layer}
 * <pre>wrapper class for Leaflet geojson layer objects
 * retrieves json geo data from a url, wraps a jQuery getJSON fn call around a leaflet geoJson fn call
 * the result is passed to the map class object via a callback fn
 * @constructor 
 * @param {String} description the description of the layer as it is displayed in the map control widget
 * @param {String} url the URL where json file is to be found
 * @param {Function} callback function to call when the json data has been fetched
 * @param {Style} [style] a style parameter object
 */
function JsonLayer(description, url, callback, style)
{
    /* handle style object non empty */
    if (typeof style === 'undefined') {style = new Style();}

    //style = this._default_params_object();
    /* call parent ctrs to store passed in params */
    this.Layer_ctr.call(this, description, url, callback, style);
    this.LayerStyle_ctr.call(this, style);
    /* this wrapped layer object 
     * see: http://api.jquery.com/jquery.getjson/ */
    jqxhr = $.getJSON(url, function(data) {
        // ...
    });
    /* bind this context to the anonymous fn call */
    jqxhr.done(this._L_geoJson.bind(this));
    /* TODO fail cb */
}

/** inherit from @class Layer */
JsonLayer.prototype = Object.create(Layer.prototype);
/** get reference to parent ctors  */
JsonLayer.prototype.Layer_ctr = Layer;
JsonLayer.prototype.LayerStyle_ctr = LayerStyle;

/** multi inherit
 * @mixin {@link JsonLayer} multi inherits from {@link Layer} and {@link LayerStyle} 
 * so it copies over {@link LayerStyle}'s protoype members
 */
void function mixin_parent() {
    var keys = Object.keys(LayerStyle.prototype);
    var i, len;
    for(i = 0, len = keys.length; i < len; ++i) {
        JsonLayer.prototype[keys[i]] = LayerStyle.prototype[keys[i]];
    }
}();


/**
 * wrapper fn for leaflet @function geoJson
 * TODO pass in property param object
 * @param {Json} data json data object
 * @private
 */
JsonLayer.prototype._L_geoJson = function(data)
{
    /* async fetch done! */
    /* init a leaflet geojson object */
    var json = L.geoJson(data, this.parameter());
    /* add the leaflet geoJson response as layer to this object */
    this._layer = json;
    /* invoke the callback function and return this JsonLayer object to the map object */
    if (this.json_fetched_cb && typeof this.json_fetched_cb === "function") {
        this.json_fetched_cb(this);
    } else {
        // TODO throw error - see: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/throw
    }
};

