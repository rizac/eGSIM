/** base Map class
 * initializes a new Map object
 * this class takes care of all Leaflet Map related functionality
 * @constructor
 * @property {Object} _globals global values related to the leaflet map
 * @property {Object} _layers object to store base and overlay layer arrays
 * @property {Object} _ids object to store map and sidebar HTML ids
 * @param {String} _map_id the id of the leaflet map container w/o project specific prefix
 * @param {String} sidebar_id the id of the map attached sidebar element
 * @param {String} id_prefix a project specific prefix for id elements
 */
function Map( map_id, sidebar_id, id_prefix )
{
    this._globals = { map: { MIN_ZOOM_WORLD:1, MAX_ZOOM_WORLD:19 } };
    this._layers = { base: [], overlay: [] };
    this._ids4js = {};
    
    this._add_id4js('prefix', id_prefix);
    var ids = new Ids( this._create_id(id_prefix, sidebar_id), this._create_id(id_prefix, map_id) );
    $.each(this._ids4js, function(k,v) {
        //console.log('adding',k, ' => ', v, 'to window.ids', window.ids);
        ids[k] = v;
    });
    
    /* store sidebar and map ids here
     * ids is an object of @class Ids
     */
    this._ids = ids.get(); //{ map: 'map', sidebar: 'sidebar' };
}

/** *** initializes a new Leaflet map object and layer control object ***
 * adds the sidebar to the Leaflet map
 * sidebar and map HTML ids are fetched from a window.ids object which is created by sidebar.php class ...
 * ... the Map class constructer fetches this object and assigns it to this._ids property
 * @param {Object} [params] a Leaflet parameter object, e.g. { center: [51.3, 13.37], zoom: 6} 
 * @param {String} [suffix=""] TODO - not used
 */
Map.prototype.init = function(params, suffix="")
{
    if (typeof params === 'undefined') { params = { center: [51.3, 13.37], zoom: 4 }; }
    this.base_maps = {};
    for (i = 0; i<this._layers.base.length; ++i) {
        this.base_maps[this._layers.base[i].description()] = this._layers.base[i].layer();
    }
        
    /* private property
     * init map object with first layer selected 
     */
    this._map = L.map(this._ids.map + suffix, {
        center: params.center,
        zoom: params.zoom,
        layers: [this._layers.base[0].layer()]
    });
    
    /* private property
     * create the layers control 
     */
    this._layerControl = new L.control.layers(this.base_maps, null, { collapsed: true }).addTo(this._map);

    /* TODO - handle JsonLayer geojson not yet finished fetching when this function executes */
    for (i = 0; i<this._layers.overlay.length; ++i) {
        if (! (this._layers.overlay[i].added() || typeof this._layers.overlay[i].layer() === 'undefined') ) {
            this._map_add_layer(this._layers.overlay[i]);
        }
    }
    
    /* add the sidebar to the map html container */
    this.sidebar();
};

/** *** ***
 * @returns this Leaflet map object
 */
Map.prototype.map = function()
{
    return this._map;
};

/** *** ***
 * @returns this Leaflet ids object
 */
Map.prototype.ids = function()
{
    return this._ids;
};

/** *** ***
 * @returns this Leaflet layercontrol object
 */
Map.prototype.layercontrol = function()
{
    return this._layerControl;
};


/** *** pushes a new @class BaseLayer object to the data structure ***
 * @param description the description of the layer as it is displayed in the map control widget
 * @param url the URL string of this layer
 * @param attribution the attribution string, e.g. layer reference
 */
Map.prototype.add_base_layer = function(description, url, attribution)
{
    this._layers.base.push( new BaseLayer(description, url, attribution) );
};

/** *** adds a new vector layer from a json file to the map ***
 * @param description the description of the layer as it is displayed in the map control widget
 * @param url the URL where json file is to be found
 * @param [params] a style parameter object
 */
Map.prototype.add_json_layer = function(description, url, params)
{
    var l = new JsonLayer(description, url, this._json_callback_fn.bind(this), params );
    //this._layers.overlay.push(l);
    //console.log('params', params, 'new json layer', l);
    return l;
};

/** *** adds a new vector layer from an ESRI shapefile file to the map ***
 * @param description the description of the layer as it is displayed in the map control widget
 * @param url the URL where the zipped shapefile file is to be found
 * @param [params] a style parameter object
 */

Map.prototype.add_shpzip_layer = function(description, url, params)
{
    var l = new ShpJsonLayer(description, url, this._json_callback_fn.bind(this), params );
    //this._layers.overlay.push(l);
    //console.log('params', params, 'new shp layer', l);
    return l;
};


/** *** returns the map object's overlay array ***
 * @return this map object's array of added vector overlays
 */
Map.prototype.overlays = function()
{
    return this._layers.overlay;
};

/** *** adds the sidebar to the map ***
 * requires the @https://github.com/Turbo87/sidebar-v2 Leaflet sidebar plugin
 * @param id the HTML id of the sidebar 
 */
Map.prototype.sidebar = function()
{
    this.sidebar = L.control.sidebar(this._ids.sidebar);
    /* make sure the sidebar isn'n covered by other html objects */
    $('#'+this._ids.sidebar).css( "zIndex", 1001 );
    $('.sidebar-content').css( "zIndex", 1001 );
    //this.sidebar.on('show', onSidebarShow);
    this.sidebar.addTo(this._map);
};

/** *** private ***
 * callback fn that gets called from an object of @class JsonLayer or one of it's child classes ...
 * ... once that object is done fetching the geojson layer object that it wraps
 * the response wrapped geojson object is added to the leaflet map from here
 * @param response a @class JsonLayer object 
 */
Map.prototype._json_callback_fn = function(response)
{
    console.log('callback', response, 'this', this);
    this._layers.overlay.push(response);
    this._map_add_layer(response);
};

/** *** private ***
 * adds a layer to the map and to the layer control
 * @param layerobj an object of @class JsonLayer or one of it's child classes
 * property layer the layer to add to the map and the layer control 
 * property description the layer's description in the layer control
 */
Map.prototype._map_add_layer = function(layerobj)
{
    /* test if this layer already has been added */
    if (!layerobj.added()) {
        /* if the leaflet map hasn't been created we cannot add stuff to it */
        if (typeof this._map === 'undefined') {
            // TODO - error handling
        } else {
            /* mark this layer as added */
            layerobj.added(true);
            /* add the layer to map and layer control */
            layerobj.layer().addTo(this._map);
            this._layerControl.addOverlay(layerobj.layer(), layerobj.description());
        }
    }
};




Map.prototype._add_id4js = function(key, value)
{
    this._ids4js[key] = value;
};

Map.prototype._create_id = function(id_prefix, id_postfix)
{
    return (id_prefix.length === 0)? id_postfix : id_prefix + '_' + id_postfix;
};


/** ----------------------------------------------------- **/


/** creates an id object
 * @constructor 
 * @todo do we need this
 * @param {String} s the sidebar html id string
 * @param {String} m the map html id string
 */
function Ids(s,m){this._i={map:m,sidebar:s};}
Ids.prototype.get=function(){return this._i;};
