/** data model for GMPEs
 * inherits from {@link JsonLayer}
 * @constructor 
 * @property {Boolean} _selected whether this GMPE has been selected or not (e.g. in a table)
 * @property {Object} _properties e.g. { 'GMPE-Name':'', 'Period':'', 'Rank':'', 'Weight':'' }
 * @property {} _zones
 * @param {Object} feature_object object containing key value pairs of features, e.g. { 'GMPE-Name':'', 'Period':'', 'Rank':'', 'Weight':'' }  
 */
function Gmpe(feature_object)
{
    this._selected = false;
    this._init_properties(feature_object);
}

/** inherit from @class JsonLayer and thus also inherit from @class Layer */
//ShpJsonLayer.prototype = Object.create(JsonLayer.prototype);
/** get reference to parent ctr  */
//ShpJsonLayer.prototype.JsonLayer_ctr = JsonLayer;


/*** --- Getter & Setter --- ***/

/** sets or gets a feature from this class' properties 
 * <pre> depending on the number of passed in parameter, this function behaves differently
 * - no parameter: return the properties object
 * - one parameter k: return propertiers[k]
 * - two parameter k,v: set properties[k] = v
 * @param {String} [feature_key]
 * @param {String} [feature_value] 
 * @returns {Boolean|Object} 
 */
Gmpe.prototype.feature = function(feature_key, feature_value)
{
    /* if there's neither a key nor value parameter, return the whole properties object */
    if (typeof feature_key === 'undefined') {return this._properties;};
    /* if there's a key parameter, we look at the value parameter */
    if (typeof feature_value === 'undefined') {
        if (this._properties[feature_key] === 'undefined') {
            /* if the value to the key is undefined */
            return false; /* FIXME - figure out if a key w/o value is a special case */
        } else {
            /* return the key's value */
            return this._properties[feature_key];
        }
    } else { /* TODO - what was this meant for? we have no variable value */
        /* set the value for the property key */
        this._zones = value;
        return true;
    }
};

/** sets or gets the selected status of this class' object
 * @param {Boolean} selected
 * @returns {Boolean} the selected status of this gmpe
 * @throws {} TODO 
 */
Gmpe.prototype.selected = function(selected)
{
    if (typeof selected === 'undefined') {
        return this._selected;
    } else if (typeof selected !== 'boolean') {
        /* throw error */
        console.log('error', selected, 'must be of type boolean');
        return false;
    } else {
        this._selected = selected;
        return true;
    }
};


/*** --- Private --- ***/

/** transforms a key value paired object into properties
 * @private 
 * @param {Object} feature_object a JS object, e.g. { 'GMPE-Name':'', 'Period':'', 'Rank':'', 'Weight':'' }
 */
Gmpe.prototype._init_properties = function(feature_object)
{
    if (typeof feature_object === 'undefined') {
        /* default to ... */
        this._properties = { 'GMPE-Name':'', 'Period':'', 'Rank':'', 'Weight':'' };
    } else {
        /* iterate over feature_object and make this our new properties object */
        var _p = {};
        $.each(feature_object, function(k,v) {
            _p[k] = v;
        });
        this._properties = _p;
    }
};
