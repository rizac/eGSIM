/** class to handle vector layer style definitions 
 * @constructor 
 * @param {Style} styleobj the style object to be used for this layerstyle
 */
function LayerStyle(styleobj)
{
    /* style object */
    this._style = styleobj;
    //console.log('layerstyle style', styleobj);
}


/*** --- Getter & Setter --- **/

/** gets or sets this class' @class Style object
 * @param {Style} newvalue
 * @returns {Boolean} True if @param newvalue is set or the currently set {@link Style} object if no parameter is passed in
 */
LayerStyle.prototype.style = function(newvalue)
{
    if (typeof newvalue === 'undefined') {
        return this._style;
    } else {
        this._style = newvalue;
        return true;
    }
};


/** --- Private --- */

/** a default style definition
 * @private 
 * @returns {Object} a default styling object in the form {style:aStyle, onEachFeature:aCbFunction}
 */
LayerStyle.prototype._default_params_object = function()
{
    var ret = { style: this._style_default.bind(this), onEachFeature: this._on_each_feature.bind(this) };
    return ret;
};

/** vector layer mouse interaction definition
 * highlight layer on mouseover, reset highlight on mouseout, @function _feature_on_click callback on layer mouseclick
 * @private 
 * @param {Object} feature a Leaflet feature type object that was interacted with
 * @param {Object} layer a Leaflet layer object
 */
LayerStyle.prototype._on_each_feature = function(feature, layer)
{
    layer.on({
        mouseover: this._feature_highlight,
        mouseout: this._feature_reset_highlight.bind(null, this),
        click: this._feature_on_click.bind(this)
    });
};


/** sets layer highlight style definition to a highlighted appearance
 * @private
 */
LayerStyle.prototype._feature_highlight = function()
{
    /* TODO - still hardwired */
    this.setStyle({
        // weight: weight,
        color: '#226',
        dashArray: '',
        opacity: 0.8
    });
};

/** resets a layer's feature styling
 * @private 
 * @param {Layer} c a layer object, the Leaflet layer that received a callback (mouseover, mouseout, ...)
 * @param {Object} e an Event object that e.g. contains the feature it has been fired on
 */
LayerStyle.prototype._feature_reset_highlight = function(c, e)
{
    e.target.setStyle(c._style_default(e.target.feature));
};

/** passes an event {Object} to the callback function of this layerstyle's style object
 * @private 
 * @param {Object} e an event object
 * @throws {} TODO exception handling
 */
LayerStyle.prototype._feature_on_click = function(e)
{
    this._style.callback(e);
};

/** returns a default style for the vector layer
 * @private
 * @description {color:aColor,dashArray:aNumber,fillColor:aColor,fillOpacity:aNumber[0..1],opacity:aNumber[0..1],weight:aNumber}
 * @param {Object} feature a Leaflet vector layer feature object
 * @returns {Object} a default style for the vector layer 
 */
LayerStyle.prototype._style_default = function(feature)
{
    /* pre-set a styling value for the fill color based on the passed in feature parameter */
    var ret = { fillColor: this._feature_color(feature.properties[ this._style.feature_property_name() ]) };
    /* get reference to feature styling object */
    var styledef = this._style.layer_style_definition();
    Object.keys(this._style.layer_style_definition()).forEach(function (key) {
        ret[key] = styledef[key];
    });
    return ret;
};

/** feature styling color fetch fn 
 * @private 
 * @param {String} feature_property a feature property by which the styling of the layer's features is determined
 * @returns {String} a color String
 */
LayerStyle.prototype._feature_color = function(feature_property)
{
    /* set a default feature styling value */
    var ret = '#0000ff';
    /* get reference to feature styling object */
    var styledef = this._style.feature_style_definition();
    /* return feature style based on feature property @param feature_property */
    Object.keys(styledef).forEach(function (key) {
        if (key === feature_property) {ret = styledef[key];}
    });
    return ret;
};
