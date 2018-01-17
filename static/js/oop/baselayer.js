/** base layer class 
 * inherits from @class Layer, initializes a new Leaflet TileLayer object
 * @constructor 
 * @param {String} description the description of the layer as it is displayed in the map control widget
 * @param {String} url the URL string of this layer
 * @param {String} params the attribution string, e.g. layer reference
 */
function BaseLayer(description, url, params)
{
    /* call parent fn to store passed in params */
    this._store_ctr_params(description, url, params);
    /* this wrapped layer object */
    this._layer = this.tilelayer( this._layer_attrib(this.url(), this.parameter()) );
    //var gshaporgdisc = new L.TileLayer(GSHAP_TILESERVER_URL + "/mapservice/tiles/org/{z}/{x}/{y}.png", {minZoom: 1, maxZoom: 19, attribution: 'ref'});
}

/** inherit from {@link Layer} */
BaseLayer.prototype = Object.create(Layer.prototype);

/** private
 * @param {String} url the layers URL string
 * @param {String} attribution the attribution string, e.g. layer reference
 * @returns {Object} a layer attribution object in the form { url:url, attribution:attribution }
 */
BaseLayer.prototype._layer_attrib = function(url, attribution)
{
    return { url:url, attribution:attribution };
};

/** 
 * @param {Object} layer_attrib a layer attribution object, e.g. { center: [51.3, 13.37], zoom: 6}
 * @returns {TileLayer} a new Leaflet TileLayer object
 */
BaseLayer.prototype.tilelayer = function(layer_attr)
{
    return new L.TileLayer(layer_attr.url, { minZoom: 1, maxZoom: 19, attribution: layer_attr.attribution });
};
