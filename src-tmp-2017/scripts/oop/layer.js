/** "abstract" layer class for leaflet map overlays
 * <pre>wraps a raster or vector leaflet overlay, to be overwritten by child classes
 * this class is intended to be inherited from by other classes that wrap specific types of layers (e.g. raster or vector layer)
 * provides functions that are commonly used among any layer type
 * @constructor 
 * @abstract 
 * @param {String} description this layers layer control description
 * @param {String} url the url from where to fetch this layer's vector data
 * @param {Function} callback callback fn to invoke when this class object is done fetching data
 * @param {T} params this layer's parameter object (e.g. style)
 * @example MyLayer.prototype = Object.create(Layer.prototype);
 * @property {boolean} _added switch to indicate whether this class object has been added to the map
 * @property {Function} json_fetched_cb callback fn to invoke when this class object is done fetching data;
 * @property {T} _params this layer's parameter object (e.g. style);
 * @property {String} _description this layers layer control description;
 * @property {String} _url the url from where to fetch this layer's vector data;
 */
function Layer(description, url, callback, params)
{
    /* store the relevant parameters */
    this._store_ctr_params(description, url, callback, params);
}


/** --- getter --- */
/** sets this class' object to an added state or returns the state
 * @param {Boolean} [added] set's wheter this object has been added or not
 * @returns {Boolean} True if @param added is passed in or @member {Boolean} added if not
 */
Layer.prototype.added = function(added)
{
    if (typeof added === 'undefined') {
        return this._added;
    } else {
        this._added = added;
        return true;
    }
};

/** sets the parameter for this class or returns the current parameter object
 * @param {T} [params] a parameter object
 * @returns {Boolean} True if a params object is passed in or @member {T} params if not
 */
Layer.prototype.parameter = function(params)
{
    if (typeof params === 'undefined') {
        return this._params;
    } else {
        this._params = params;
        return true; /* return sthg here just b/c of lint :( */
    }
};

/** "promise" function
 * <pre>this fn probably doesn't need to exist b/c of JS's duck-typed nature
 * however it will return any @member _layer object property of the child class 
 * the _layer property is set at some point in the future
 * @returns {T} a layer object
 */
Layer.prototype.layer = function()
{
    return this._layer;
};

/**
 * 
 * @returns {String} @member description
 */
Layer.prototype.description = function()
{
    return this._description;
};

/**
 * 
 * @returns {String} @member url
 */
Layer.prototype.url = function()
{
    return this._url;
};


/** --- private --- */
/**
 * @private 
 * @param {String} description this layers layer control description
 * @param {String} url the url from where to fetch this layer's vector data
 * @param {Function} callback callback fn to invoke when this class object is done fetching data
 * @param {T} params this layer's parameter object (e.g. style)
 */
Layer.prototype._store_ctr_params = function(description, url, callback, params)
{
    this._added = false;
    /* the fn to call when the json data is done fetching */
    this.json_fetched_cb = callback;
    /* style parameters of this layer */
    this._params = params;
    /* the description of this layer */
    this._description = description;
    /* the url to fetch this layer's vector data from */
    this._url = url;
};
