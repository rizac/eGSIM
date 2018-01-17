/** Zip File Reader class
 * <pre>wraps FileReader class
 * @constructor 
 * @param {} feature_id the id 
 * @property _file_id the html element's id where files are dropped
 * @property _submit_id the html element's id that receives submit events
 * @property _warning_id the html element's id where warnings are displayed
 * @property _mapobject the {Map} mapobject passed in through the init function
 * @property _reader a {FileReader} instance
 * @property _filename the zip file's file name
 */
function ZipFileReader(feature_id)
{
    this._file_id = feature_id + '_file';
    this._submit_id = feature_id + '_submit';
    this._warning_id = feature_id + '_warning';
}

/** initialization
 * adds a click listener to the submit element
 * @param {Map} mapobject 
 */
ZipFileReader.prototype.init = function(mapobject)
{
    this._mapobject = mapobject;
    $('#'+this._submit_id).on('click', this._on_submit_handler.bind(this));
};

/** reads a File object into a buffer
 * @private 
 * @param {Map} mapobject
 * @param {File} file a filename
 * @param {String} description TODO
 */
ZipFileReader.prototype._handle_zipfile = function(mapobject, file, description)
{
    this._reader = new FileReader();
    this._reader.onload = this._filereader_handler.bind(this);
    this._reader.readAsArrayBuffer(file);
};

/** converts an array buffer into a Leaflet vector layer and adds it to the map & layer control
 * @private 
 * @param {Map} mapobject
 * @param {ArrayBuffer} buffer the result property of a FileReader object
 * @param {String} description
 */
ZipFileReader.prototype._convert2layer = function(mapobject, buffer, description)
{
    shp(buffer).then(function(geojson){
        var layer = L.shapefile(geojson).addTo(mapobject.map());//More info: https://github.com/calvinmetcalf/leaflet.shapefile
        mapobject.layercontrol().addOverlay(layer, description);
    });
};

/** handler fn to be invoked when file reader load event is fired
 * it then converts the fetched ressources into a Leaflet layer
 * @see _convert2layer fn
 * @private 
 * @throws {} TODO
 */
ZipFileReader.prototype._filereader_handler = function()
{
    if (this._reader.readyState != 2 || this._reader.error){
        // TODO throw console.log('reader error');
        return;
    } else {
        //console.log('handling zip file', reader.result);                 
        this._convert2layer(this._mapobject, this._reader.result, this._filename);
    }
};

/** submit html element click event handler
 * prints out an error, a warning or reads the submitted file into a buffer
 * @see {@link _handle_zipfile} fn
 * @param {Object} e Event object, TODO - is this needed?
 */
ZipFileReader.prototype._on_submit_handler = function(e)
{
    var files = $('#'+this._file_id).prop('files'); // prop() returns http://api.jquery.com/Types/#Anything, but we probably expect a String here
    if (files.length === 0) {
        console.log('error - no file');
        return; //do nothing if no file given yet
    }
    var file = files[0]; // Blob or File - to be passed to readAsArrayBuffer
    if (file.name.slice(-3) != 'zip') { 
        $('#'+this._warning_id).html('Select .zip file');
        return;
    } else {
        $('#'+this._warning_id).html(''); //clear warning message.
        this._filename = file.name.substring(0, file.name.lastIndexOf(".")); // String
        this._handle_zipfile(this._mapobject, file, this._filename);
    }
};
