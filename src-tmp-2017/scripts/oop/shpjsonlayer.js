/** shapefile layer 
 * inherits from {@link JsonLayer}
 * <pre>ctor 
 * @constructor 
 * @param {String} description see parent class
 * @param {String} url see parent class
 * @param {Function} callback see parent class
 * @param {Style} style see parent class
 */
function ShpJsonLayer(description, url, callback, style)
{
    /* call parent ctr to store passed in params */
    this.JsonLayer_ctr.call(this, description, url, callback, style);
    /* this wrapped layer object 
     * at this point we already handled the @param params object potentially being empty
     */
    this._layer = new L.Shapefile(url, this._default_params_object());
    this.json_fetched_cb(this);
}

/** inherit from @class JsonLayer and thus also inherit from @class Layer */
ShpJsonLayer.prototype = Object.create(JsonLayer.prototype);
/** get reference to parent ctr  */
ShpJsonLayer.prototype.JsonLayer_ctr = JsonLayer;
