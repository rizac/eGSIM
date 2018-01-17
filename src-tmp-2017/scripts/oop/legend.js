/** leaflet legend wrapper
 * <pre>handles a legend that can be displayed in a corner of the map 
 * @constructor 
 * @property _legend a Leaflet control object containing a map legend
 * @property _prefix a unique prefix to be used on html tags
 * @param {Style} style a style object, containing the style definition for the layer
 * @param {String} prefix a unique prefix to be used on html tags
 */
function Legend(style, prefix)
{
    this._prefix = typeof prefix === 'undefined'? '': prefix;
    this._legend = this._create_legend(style);
    //console.log('legend', this._prefix);
}

/**
 * @returns {Object} the current Leaflet control legend object
 */
Legend.prototype.legend = function()
{
    return this._legend;
};


/** --- Private --- */

/** returns the top html tags of the infolegend element
 * @private 
 * @param {String} localisation_val TODO implement localization
 * @returns {String} the top html tags of the infolegend element
 */
Legend.prototype._infolegend_header = function(localisation_val)
{
    return '<div id="'+this._prefix+'_infolegend_column" class="col-xs-12 col-sm-12 col-md-12 col-lg-12">'+ // inner div bootstrap
        '<div class="'+this._prefix+'_infolegend_innerdiv">'+ // inner div
        '<h4 class="'+this._prefix+'_localisation" value-local="' + localisation_val + '"></h4>';
};

/** returns the bottom html tags of the infolegend element
 * @private 
 * @param {String} unit_vals the unit of displayed values or '' for no unit
 * @returns {String} returns the bottom html tags of the infolegend element 
 */
Legend.prototype._infolegend_footer = function(unit_vals)
{
    return '</br></br><i></i><span>' + unit_vals + '</span>' +
        '</div>' + // /END legend inner div
        '</div>'; // /END bootstrap col div  
};

/** creates a Leaflet control legend object that can be placed on a Leaflet map
 * @private 
 * @param {Style} style a Style object
 * @returns {Object} an L.Control.Legend Leaflet control object
 */
Legend.prototype._create_legend = function(style)
{
    var _legend = this;
    // create new legend custom control with add / remove functionality
    L.Control.Legend = L.Control.extend ({
        options: {position: 'bottomright'},
        onAdd: function (map) {
            map.legend = this;
            var div = L.DomUtil.create('div', 'info gfz_gmpe_legend_whole');
            div.id = 'legend';
            div.innerHTML = '<div class="'+_legend._prefix+'_infolegend_parentdiv col-xs-12 col-sm-12 col-md-12 col-lg-12">'; // parent div
            // create inner legend div
            var inner_legend = _legend._infolegend_header('SITE_TITLE'); // 
            var style_def = style.feature_style_definition();
            
            Object.keys(style_def).forEach(function (key) {
                inner_legend +=
                    '<i style="background:' + style_def[key] +  '"></i> ' +
                    '<a href="javascript:void(0)" class="'+_legend._prefix+'_infolegend_entry" data-zone="'+key+'">'+key+'</a>'+
                    '<br>';
            }); 
            
            //inner_legend += _legend._infolegend_footer(/*'$$'+UNIT_ACC+'$$'*/);
            div.innerHTML += inner_legend;
            
            div.innerHTML += '</div>'; // /END parent div
            return div;
        },
        onRemove: function (map) {
            delete map.legend;
        }
    });
    return new L.Control.Legend();
};
