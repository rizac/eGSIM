/** class to handle display of {@link Data} objects
 * @constructor 
 * @property _header a table header array, see @param header
 * @param {Object} header a table header array to be used when displaying the data as table, e.g. ['GMPE-Name', 'Rank', 'Weight', 'Period'] 
 **/
function DataDisplay(header = {})
{
    this._header = header;
}

/** sets or gets the to be displayed data object
 * @param {Data} data a {@link Data} object
 * @returns {Boolean|Data} 
 */
DataDisplay.prototype.data = function(data)
{
    if (typeof data === 'undefined') {
        return this._data;
    } else {
        this._data = data;
        return true;
    }
};

/** sets or gets the @param header object
 * @param {Object} header a table header array, see @ctor param header
 * @returns {Boolean|Object} 
 */
DataDisplay.prototype.header = function(header)
{
    if (typeof header === 'undefined') {
        return this._header;
    } else {
        this._header = header;
        return true;
    }
};

/** creates an html table string from a data object
 * @param {Data} data a data object containing the to be displayed data
 * @param {Style} style a style object that defines how the data is to be displayed
 * @returns {String} a html table
 */
DataDisplay.prototype.table_from_data = function(data, style)
{
    /* create table & table header objects */
    var table = '',
        table_header = '',
        which = 'zone';
    /* print table head */
    table_header +=  '<thead><tr>';
    /* iterate the table header */
    $.each(this._header, function(_, column_name) {
        table_header += '<th>'+column_name+'</th>';
    });
    table_header += '</tr></thead>';
    /* add the header to the table object */
    table += table_header;
    /* add table body */
    table += '<tbody><tr>';
    
    $.each(data.data(), function(key, object) {
        /* append a new table section to the wrapper element */
        table_sub_header = '<tr class="gfz_gmpe_tableheader" style="background-color:'+style.feature_style_definition_rgba(key, 50)+
            '" data-data-sort="'+which+'"'+ '" data-data-key="'+key+'"><th colspan="4">'+key+'</th></tr>';
        
        /* add a colored (by feature color) subheader to the table */
        table += table_sub_header;
        /** iterate this */
        $.each(object, function(index, entry) {
            /* retrieve array of keys from this iteration's data object 
             * do this every iteration, b/c the object's structure might change */
            keys = Object.keys(entry.feature());
            /* start a new row */
            var row_entries = '<tr class="gfz_gmpe_tablerow"'+' data-data-sort="'+which+'" '+ 'data-data-key="'+key+'"';
            /* add the current data object's features as "data-" html attributes, we need this later
             * when working with the table's data */
            $.each(keys, function(k,v) {
                row_entries += ' data-entry-'+v+'="'+entry.feature(v)+'"';
            });
            row_entries += '">';
            /* iterate over entry feature keys */
            $.each( keys , function(k,v) {
                row_entries += '<td>'+entry.feature(v)+'</td>';
            });
            /* append the built html block */
            table += row_entries + '</tr>';
        });
    });
    return table;
};


/** creates a Leaflet control object that can be put on the map
 * @param {Data} data a data object containing the to be displayed data
 * @param {Style} style a style object that defines how the data is to be displayed
 * @returns {Object} a Leaflet control object
 */
DataDisplay.prototype.infoview = function(data, style)
{
    var _info = L.control({
        position : 'bottomleft'
    });
    _info.onAdd = function(map) {
        this._div = L.DomUtil.create('div', 'info listview'); // create a div with a class "info"
        this._div.id = 'info';//divid?divid:""; // from param                                                                           
        this.update();
        return this._div;
    };
    _info.update = function(key) {
        if ( typeof key === 'undefined' ) { key = ''; }
        if ( typeof data !== 'undefined' && Object.keys(data.data()).length > 0 ) {
            var content = '';
            /* prepare new table */
            content += '<table id="gfz_gmpe_data_table" class="table table-striped table-bordered table-hover table-condensed">';
            content += '<thead><tr style="background-color:'+style.feature_style_definition_rgba(key, 50)+'"><th colspan="4" data-data-key="'+key+'">'+
                       key+'</th></tr></thead>';
            /* print table head */
            content += '<thead><tr>';
            content += '<th>GMPE-Name</th><th>Rank</th><th>Weight</th><th>Period</th>';
            content += '</tr></thead>';
            /* print table body */
            content += '<tbody><tr>';
            
            $.each( data.data(key), function( index, result ) {
                infoclass = result.selected()?' info': '';
                content += '<tr class="gfz_gmpe_info_tablerow'+infoclass+'" data-data-sort="infoview" data-data-key="'+
                           key+'" data-entry-GMPE-Name="'+result.feature("GMPE-Name")+'" data-entry-Period="'+result.feature("Period")+'">'+
                           '<td>'+result.feature("GMPE-Name")+'</td>'+
                           '<td>'+result.feature("Rank")+'</td>'+
                           '<td>'+result.feature("Weight")+'</td>'+
                           '<td>'+result.feature("Period")+'</td>'+
                           '</tr>';
            });
            
            content += '</tr></tbody>';
            content += '</table>';
            _info._div.innerHTML = content;
            
        } else {
            // clear content          
            //this._div.innerHTML = '<h4 id="gfz_gmpe_info_empty">Locations</h4>' +  (props ? content : 'shows something');
        }
    };
    return _info;
};
