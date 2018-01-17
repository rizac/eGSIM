/** wrapper class for style definitions for leaflet vector overlays 
 * @constructor 
 * @param {Object} layer_style a Leaflet style difining object, e.g.: { weight:aNumber, opacity:aNumber[0..1], color:aString, dashArray:aNumber, fillOpacity:aNumber[0..1] }
 * @param {String} feature_name the name of the feature by which to apply the styling
 * @param {Object} feature_style an object containing color definitions for features, e.g.: { feature1:color1, feature2:color2, ... }
 * @param {Function} callback a callback function that is invoked when a layer's feature has been clicked
 * @example 
 * //we can either set each style property seperately ... 
 * myshpfile.style().layer_style_definition( mystyle.layer_style_definition() );
 * myshpfile.style().feature_style_definition( mystyle.feature_style_definition() );
 * myshpfile.style().feature_property_name( mystyle.feature_property_name() ); // TECREG, TECTONICS 
 * myshpfile.style().feature_click_callback( mystyle.feature_click_callback() );
 * //... or pass the complete Style object in
 * myshpfile.style(mystyle);
 * // this adds a Json layer to the map
 * var myjsonlayer = mymap.add_json_layer('my overlay', 'json.geojson');
 */
function Style(layer_style, feature_name, feature_style, callback)
{
    /* default to value name 'value' here */ 
    this._feature_property_name = typeof feature_name === 'undefined'?'value':feature_name;
    this._feature_style_definition = typeof feature_style === 'undefined'?{}:feature_style;
    /* set some convenient default values here */ 
    this._layer_style_definition = typeof layer_style === 'undefined'?{ weight: 2, color: 'blue', dashArray: '2', opacity: 1.0 }:layer_style;
    /* layer feature click callback */
    this._callback = callback;
}

/** Getter and Setter */

/** gets or sets style definition of the layer 
 * @param {Object} newvalue a Leaflet style difining object
 * @returns {Boolean} True if the style definition is set to @param newvalue or returns the currently set style definition if no parameter is passed in 
 */
Style.prototype.layer_style_definition = function(newvalue)
{
    if (typeof newvalue === 'undefined') {
        return this._layer_style_definition;
    } else {
        this._layer_style_definition = newvalue;
        return true;
    }
};

/** gets or sets the name of the feature property on which coloring is based
 * @param {String} newvalue
 * @returns {Boolean} True if the property name is set to @param newvalue or returns the currently set property name if no parameter is passed in 
 */
Style.prototype.feature_property_name = function(newvalue)
{
    if (typeof newvalue === 'undefined') {
        return this._feature_property_name;
    } else {
        this._feature_property_name = newvalue;
        return true;
    }
};

/** gets or sets the object that contains the color definitions for each feature
 * @param {Object} newvalue
 * @returns {Boolean} True if the color definition is set to @param newvalue or returns the currently set color definition if no parameter is passed in
 */
Style.prototype.feature_style_definition = function(newvalue)
{
    if (typeof newvalue === 'undefined') {
        return this._feature_style_definition;
    } else {
        this._feature_style_definition = newvalue;
        return true;
    }
};

/** returns the callback function associated with this {Style} object if it exists
 * @param {Object} e an Event object
 * @throws {} TODO exception handling
 */
Style.prototype.callback = function(e)
{
    if (this._callback && typeof this._callback === "function") {
        this._callback(e);
    } else {
        // TODO throw error - see: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/throw
        console.log('error', 'no callback function or callback function is of wrong type');
    }
};

/** converts the color value of a feature, as defined by feature_style_definition, into an html rgba expression
 * @param {String} key the feature name by which colorizing is applied
 * @param {Integer} opacity [0..100]
 * @returns {String} an html rgba expression, e.g. rgba(255,255,255,0.5)
 */
Style.prototype.feature_style_definition_rgba = function(key, opacity)
{
    return this._hex2rgba(this._feature_style_definition[key], opacity);
};

/** gets or sets the layer feature click callback function
 * @param {Function} newvalue a callback function that is invoked when a layer's feature has been clicked 
 * @returns {Boolean} True if the callback function is set to @param newvalue, {Boolean} False if the function cannot be set or the callback function itself if no parameter has been passed in
 */
Style.prototype.feature_click_callback = function(newvalue)
{
    if (typeof newvalue === 'undefined') {
        return this._callback;
    } else {
        if (typeof newvalue === "function") {
            this._callback = newvalue;
            return true;
        } else {
            console.log('error in feature_click_callback', newvalue, 'cannot be set. not a function.');
            return false;
        }
    }
};

/** helper function that converts a hexadecimal color value into an rgba(r,g,b,t) string
 * @private 
 * @param {String} hex a color value in the form '#RRGGBB' or 'RRGGBB'
 * @param {Integer} opacity the opacity of the rgba expression [0..100]; is converted to an alpha value
 * @returns {String} an html rgba expression
 */
Style.prototype._hex2rgba = function(hex, opacity)
{
    if (typeof hex === 'undefined') {return false;};
    hex = hex.replace('#','');
    r = parseInt(hex.substring(0, hex.length/3), 16);
    g = parseInt(hex.substring(hex.length/3, 2*hex.length/3), 16);
    b = parseInt(hex.substring(2*hex.length/3, 3*hex.length/3), 16);

    result = 'rgba('+r+','+g+','+b+','+opacity/100+')';
    return result;
};
