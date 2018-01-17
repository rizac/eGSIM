/** data class to provide data in a structured manner
 * @constructor
 * @property _data data to be used by the application
 * <pre>data structure is as follows:
 *  /--------------------------------------------\
 *  |- key_outer_1 - key_inner_11 - a data entry |
 *  |              - key_inner_12 - a data entry |
 *  |              - ...                         |
 *  |- key_outer_2 - key_inner_21 - a data entry |
 *  |              - key_inner_22 - a data entry |
 *  |              - ...                         |
 *  |- ...                                       |
 *  \--------------------------------------------/
 * <pre>this class is specified as data-entry structure agnostic as possible
 * this means a data entry can be of any class or object structure
 */
function Data()
{
    //this._globals = { map: { MIN_ZOOM_WORLD:1, MAX_ZOOM_WORLD:19 } };
    //this._layers = { base: [], overlay: [] };
    this._data = {};
}


/*** --- Getter & Setter --- ***/

/** get or set data
 * <pre> depending on the number of passed in parameter, this function behaves differently
 * - no parameter: return the data object
 * - one parameter p: return data[p]
 * - two parameter p1,p2: return data[p1][p2]
 * - three parameter p1,p2,e: set data[p1][p2] = e
 * <pre>
 * @param {String} [key_outer] the outer key string according to the data specification
 * @param {String} [key_inner] the inner key string according to the data specification
 * @param {Gmpe} [data_entry] a data entry
 * @returns {Boolean|Object}
 **/
Data.prototype.data = function(key_outer, key_inner, data_entry)
{
    /* if there are neither an outer nor an inner key or data entry parameter passed in, return the whole data object */
    if (typeof key_outer === 'undefined') {return this._data;};
    /* if there's been an outer key parameter passed in, we look at the inner key parameter */
    if (typeof key_inner === 'undefined') {
        if (typeof this._data[key_outer] === 'undefined') {
            /* if the outer key parameter cannot be found in the data */
            return false; /* FIXME - figure out if this is a special case */
        } else {
            /* return the whole data structure related to the outer key parameter */
            return this._data[key_outer];
        }
    } else {
        /* if there's been an inner key parameter passed in, we look at the data entry parameter */
        if (typeof data_entry === 'undefined') {
            if (typeof this._data[key_outer][key_inner] === 'undefined') {
                /* if there's no data entry to the outer and inner key combination return */
                return false; /* FIXME - figure out if this is a special case */
            } else {
                /* return the data entry related to this outer and inner key combination */
                return this._data[key_outer][key_inner];
            }
        } else {
            if (typeof this._data[key_outer] === 'undefined') { this._data[key_outer] = {}; }
            //if (this._data[key_outer][key_inner] === 'undefined') { this._data[key_outer][key_inner] = {}; }
            /* set the data entry */
            this._data[key_outer][key_inner] = data_entry;
            return true;
        }
    }
};

