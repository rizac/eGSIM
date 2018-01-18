/** cb fn to be invoked, when a new data set is available 
 * @param {Data} object the assembled data object
 * <pre> data object - structure is as follows (an object of objects of gmpe-objects)
 * <pre> properties are: GMPE-Name, Period, Rank, Weight, selected, ... maybe more
 * <pre> *********************************************************
 *  /----------------------------------------------------\
 *  |- zone1 - a gmpe name - gmpe object with properties |
 *  |        - a gmpe name - gmpe object with properties |
 *  |        - ...                                       |
 *  |- zone2 - a gmpe name - gmpe object with properties |
 *  |        - a gmpe name - gmpe object with properties |
 *  |        - ...                                       |
 *  |- ...                                               |
 *  \----------------------------------------------------/
 * *********************************************************
 */
function cb_data_ready(data)
{
    /* set the application's data object */
    mydata = data;
    /* resolve data ready deferred object */
    mydata_def.resolve('data ready');
    /* initialize the data displaying table */
    gmpe_table_init();
}

/** inits the map
 * <pre>behavior
 * - {@link cb_data_ready} callback fn that is to invoked when a {@link Data} object is ready
 *
 * <pre>design
 * - map view: a big map filling the whole visible pane
 * - data view: a view below the big map dedicated to data display (and manipulation)
 * - nav bar: a top bar that provides navigational shortcuts to directly jump to different views
 * - table: table display of data. data is stored in an object of @class {data}
 * - info view: a short table to display the current selected map feature
 * - legend: color encoded data legend
 * - modal map: if scrolled down, the map objects transfers from the big view into a smaller modal (and vice versa
 * - sidenbar: a sidebar object within the big map to provide control and setting options
 *
 * <pre>*********************************************************
 *  /------------------------------------------------------\
 *  |_______________________nav bar________________________|
 *  |S  |                                                  |                                                   
 *  |i  |                   big MAP                        |
 *  |d  |                                                  |
 *  |e  -----------                          --------------|    map view
 *  |b  |info view |                         |   legend    |
 *  |a  |          |                         |             |
 *  |r  |          |                         |             |
 *  \------------------------------------------------------/
 *  /      table       |                                   \
 *  |  -               |                   --------------- |
 *  |  -               |                   |   modal map | |
 *  |  -               |                   |             | |    data view
 *  |  -               |                   |             | |
 *  |  -               |                   --------------- |
 *  \------------------------------------------------------/
 * *********************************************************
 *
 * @param {String} [suffix=""] we add a suffix to map's html id, thus we can differentiate between big and modal map 
 * as well as apply unique css rules. default value for modal should be suffix='_modal' */
function map_init(suffix = "", shziplayer_path_prefix='')
{
    /* when switching between big and modal map display, we need to remove the current map object */
    if (typeof mymap !== 'undefined') {
        /* remove current map if exists */
        mymap.map().off();
        mymap.map().remove();
    }
    /** set up a new leaflet map wrapper object and add layers to it */
    mymap = new Map( MAP_ID, SIDEBAR_ID, ID_PREFIX );
    /* base layer */
    mymap.add_base_layer('OSM DE', 'http://{s}.tile.openstreetmap.de/tiles/osmde/{z}/{x}/{y}.png', osm_attrib);
    mymap.add_base_layer('Mapnik', 'http://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', osm_attrib);
    mymap.add_base_layer('B&W', 'http://{s}.tiles.wmflabs.org/bw-mapnik/{z}/{x}/{y}.png', osm_attrib);
    mymap.add_base_layer('Topo', 'http://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', topo_attrib);
    
    /* Add ESRI layers. This has to be done this way to conform to our OOP, whihc might be removed in the future */
    /* https://esri.github.io/esri-leaflet/api-reference/layers/basemap-layer.html */
    /*mymap.add_base_layer('Streets', "http://{s}.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}.png", '');
    mymap.add_base_layer('Topographic', "http://{s}.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}", '');
	mymap.add_base_layer('NationalGeographic', "http://{s}.arcgisonline.com/ArcGIS/rest/services/NatGeo_World_Map/MapServer/tile/{z}/{y}/{x}", '');
	mymap.add_base_layer('Oceans', "http://{s}.arcgisonline.com/arcgis/rest/services/Ocean/World_Ocean_Base/MapServer/tile/{z}/{y}/{x}", '');
	mymap.add_base_layer('Gray', "http://{s}.arcgisonline.com/ArcGIS/rest/services/C…/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}", '');
	mymap.add_base_layer('DarkGray', "http://{s}.arcgisonline.com/ArcGIS/rest/services/C…s/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}", '');
	mymap.add_base_layer('Imagery', "http://{s}.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", '');
	mymap.add_base_layer('ShadedRelief', "http://{s}.arcgisonline.com/ArcGIS/rest/services/World_Shaded_Relief/MapServer/tile/{z}/{y}/{x}", '');
	mymap.add_base_layer('Terrain', "http://{s}.arcgisonline.com/ArcGIS/rest/services/World_Terrain_Base/MapServer/tile/{z}/{y}/{x}", '');
	mymap.add_base_layer('USATopo', "http://{s}.arcgisonline.com/ArcGIS/rest/services/USA_Topo_Maps/MapServer/tile/{z}/{y}/{x}", '');
    
	b = L.esri.basemapLayer("Topographic");
    */
  
    /* vector layer */
    if (shziplayer_path_prefix && !shziplayer_path_prefix.endsWith("/")){  //append slash if not provided
    		shziplayer_path_prefix = shziplayer_path_prefix + "/";
    }
    shpfile_area = mymap.add_shpzip_layer('Area Source Model', shziplayer_path_prefix+'data/asmodal/ASModelVer6.1.zip', mystyle),
    shpfile_subd = mymap.add_shpzip_layer('Subduction', shziplayer_path_prefix+'data/asmodal/Subduction.zip', mystyle),
    shpfile_vran = mymap.add_shpzip_layer('Vrancea', shziplayer_path_prefix+'data/asmodal/VRANCEAv6.1.zip', mystyle);

    /** invoke init to set up the leaflet map and add it to the site */
    var bb = $.cookie('map_boundingbox')? $.cookie('map_boundingbox').split(','): [-13.37, 33.37, 36.66, 64.42],
        sw = L.latLng( parseFloat(bb[1]), parseFloat(bb[0]) ),
        ne = L.latLng( parseFloat(bb[3]), parseFloat(bb[2]) ),
        bounds = new L.LatLngBounds( sw, ne ),
        zoom = $.cookie('map_zoom')? $.cookie('map_zoom'): 4;
    
    //console.log('map init with', bb, bounds);
    
    /* add the map to the standard big view html anchor when there's no suffix, 
     * else add it to the modal anchor if the suffix says so, 
     * else throw an error */
    if (suffix === "") {
        mymap.init( { /*center: [58.3, 13.37], zoom: 4*/}, suffix );
        /* only add legend and info view in large display */
        mylegend = new Legend(mystyle, ID_PREFIX);
        mylegend.legend().addTo(mymap.map());
        /* create an info view when the data object is available, this fn handles this */
        infoview_create();
        /* let zones be selectable via clicking the respective legend entry */
        $('.gfz_gmpe_infolegend_entry').on('click', function(e) {
            zone = $( this ).attr( 'data-zone' );
            highlight_current_zone(zone);
        });
        /* fit map to current window extension */
        mymap.map().fitBounds( bounds );
        mymap.map().setZoom( zoom );
    } else if (suffix === "_modal") {
        /* add  map to modal */
        mymap.init( { /*zoom: 3*/ }, suffix );
        mymap.map().fitBounds( bounds );
        /* decrease zoom level in modal by one, b/c it doesn't fit within the same bounds elsewise. don't know if this is too hackish */
        mymap.map().setZoom(zoom-1);
    } else {
        /* throw an error */
        console.log('error adding map to', suffix);
    }

    /* grap the last selected state and apply it again, so the table and info view are as they were before removing the old map object */
    if ($.cookie('map_selected_zone')) {
        highlight_current_zone($.cookie('map_selected_zone'));
    }

    /** event hooks */
    mymap.map().on('moveend', function(e) {
        var bb = mymap.map().getBounds().toBBoxString();
        // TODO - disable saving state in modal, maybe?
        if (e.target._container.id.indexOf('_modal') !== -1) {
            zoom = mymap.map().getZoom()+1;
        } else {
            zoom = mymap.map().getZoom();
            if ($.cookie('map_selected_zone')) {
                highlight_current_zone($.cookie('map_selected_zone'));
            }
        }
        /* set cookies for boundingbox and zoom level to re-apply these values when reloading the application */
        $.cookie('map_boundingbox', bb);
        $.cookie('map_zoom', zoom);
        //console.log('map moveend event', e.target._container.id, e, 'bounds', mymap.map().getBounds(), 'zoom', bb, mymap.map().getZoom());
    });

    /* adds a listener to table rows that will react to user-interaction with the tabled data representation */
    gmpe_table_add_row_clicklistener();
    
    /** instancestate 
     * FIXME - write a class to store all instance states of the app. do we actually need this? */
    instancestate = new Instancestate();
    
    /** add some esri overlays. they look nice, so why not */
    //esri = L.esri.basemapLayer("Topographic");
    //esri.addTo(mymap.map());
    //mymap.layercontrol().addOverlay(esri, 'esri map');
}

/** inits the modal that contains the map when scrolled down 
 * <pre>our site technically can scroll down forever, so we want some behavior that keeps the map visible when the big map is scrolled out of the visible pane 
 * we therefor transfer the map object into a modal that keeps hovering at the right side of the window
 * the map is transfered back when the big map view container becomes visible within the pane 
 * <pre>see: {@link https://www.w3schools.com/bootstrap/bootstrap_modal.asp} */
function map_modal_init(shziplayer_path_prefix='')
{
    /*  */
    $('body').scrollspy({ target: '#gfz_gmpe_scrollspy', offset: 150 });
    $('#gfz_gmpe_scrollspy').on('activate.bs.scrollspy', function (e) {
        if ( $(e.target.innerHTML)[0].hash === '#map' ) {
            $('#myModal').modal('hide');
        } else if ( $(e.target.innerHTML)[0].hash === '#data' ) {
            $('#myModal').modal('show');
        }
    });

    /* let the modal be draggable on top and bottom part of the frame */
    $(".modal-dialog").draggable({
        handle: '.modal-frame-element'
    });

    /* adds an indicator to the modal that makes it resizable by dragging */
    $(".modal-content").resizable({
        minHeight: 300,
        minWidth: 300
    });

    /* Occurs when the modal is about to be shown 
     * see: {@link https://www.w3schools.com/bootstrap/bootstrap_ref_js_modal.asp}
     * the modal is shown when the application is scrolled down
     * or when the "data" navigation item in the top bar is clicked */
    $("#myModal").on('show.bs.modal', function() {
        /* transfer the map from the big view into the modal */
        map_init('_modal', shziplayer_path_prefix);
        /* adad some css to fit it quite right on the screen */
        $(this).find('.modal-body').css({
            'max-height':'75%'
        });
        var offset = 330;
        $(this).find('.modal-body').attr('style','max-height:'+($(window).height()-offset)+'px !important;');
    });

    /* Occurs when the modal is fully shown (after CSS transitions have completed)
     * see: {@linkhttps://www.w3schools.com/bootstrap/bootstrap_ref_js_modal.asp}
     * we apply some minor css stuff here, put the modal to the front, rescale the map if rescaled, etc
     * */
    $("#myModal").on('shown.bs.modal', function() {
        //mymap.sidebar();
        /* allow scrolling of underlying site */
        $("body").removeClass("modal-open");
        /* allow interaction with underlying site */
        //$('#myModal').css( "zIndex", 1 );
        /* remove click events from the modal backdrop */
        $('#myModal').css( "pointer-events", 'none' );
        /* re-add click events to the modal window only */
        $('.modal-content').css( "pointer-events", 'auto' );
        /* allow modal window to be layered above upper nav bar */
        $('#myModal').css( "zIndex", 1050 );
        $('.modal-backdrop').hide();
        /* adjust map to modal dimensions */
        mymap.map().invalidateSize();
    });
    
    /* Occurs when the modal is fully hidden (after CSS transitions have completed)
     * see: {@link}https://www.w3schools.com/bootstrap/bootstrap_ref_js_modal.asp}
     * the modal is hidden, either by scrolling up or clicking the map entry in the top bar
     * so we transfer the map from the modal to the big view
     * */
    $("#myModal").on('hidden.bs.modal', function() {
        map_init('', shziplayer_path_prefix);
        mymap.map().invalidateSize();
        //$('#myModal').css( "zIndex", 1050 );
    });
}

/** inits a table to display all data, for now the table is displayed in one of the tabs at the bottom of the page
 * <pre>we currently have two views on the data: one sorted by zone (that's the default) the other by gmpe. they can be switched between with a button 
 * <pre>the zone sorted view is created by an @class {DataDisplay} object 
 * <pre>the gmpe sorted view is created by "hand" (maybe we don't even need it)
 * @param {String} [which=zone]  zone to display
 * @return {nil}
 * @throws Error TODO - throw an error if @param which doesn't match a proper value
 * @todo recycle table views and don't recreate them everytime they are switched */
function gmpe_table_init(which='zone')
{
    /* clear possibly existing table */
    $('#gfz_gmpe_data_table_wrapper').html('');
    /* prepare new table */
    $('#gfz_gmpe_data_table_wrapper').append('<table id="gfz_gmpe_data_table" class="table table-striped table-bordered table-hover table-condensed">');
    
    if (which === 'zone') {
        /* add table to html anchor */
        $('#gfz_gmpe_data_table').append( mydatadisplay.table_from_data(mydata, mystyle) );
        
    } else if (which === 'gmpe') {
        /* print table head */
        $('#gfz_gmpe_data_table').append('<thead><tr>');
        $('#gfz_gmpe_data_table').append('<th>Zone</th><th>Period</th>');
        $('#gfz_gmpe_data_table').append('</tr></thead>');
        /* print table body */
        $('#gfz_gmpe_data_table').append('<tbody><tr>');
        $.each(mydata.data(), function(key, object) {
            // ...
            $.each(object, function(index, entry) {
                // ...
                row_with_this_gmpe = $('#gfz_gmpe_data_table tbody').find('tr th').filter(function(){
                    return $(this).text() === entry.feature("GMPE-Name");
                });

                if (row_with_this_gmpe.length === 0) {
                    /* add this entry-name as a sub-header element, but just once */
                    $('#gfz_gmpe_data_table').append('<tr data-data-sort="'+which+'"'+'data-entry-GMPE-Name="'+entry.feature("GMPE-Name")+'">'+
                                                     '<th colspan="2">'+entry.feature("GMPE-Name")+'</th></tr>');
                }
                
                row_with_this_gmpe.parent().after('<tr style="background-color:'+mystyle.feature_style_definition_rgba(key, 50)+
                                                  '" class="gfz_gmpe_tablerow"'+' data-data-sort="'+which+'" '+ ' data-data-key="'+key+'" data-entry-GMPE-Name="'
                                                  +entry.feature("GMPE-Name")+'" data-entry-Period="'+entry.feature("Period")+'">'+
                                                  '<td>'+key+'</td>'+
                                                  '<td>'+entry.feature("Period")+'</td>'+
                                                  '</tr>');
            });
        });
    } else {
        /* throw error b/c which didn't match a proper value */
        console.log('error while creating data view table!');
    }
    /* add all closing tags */
    $('#gfz_gmpe_data_table').append('</tr></tbody>');
    $('#gfz_gmpe_data_table_wrapper').append('</table>');
}

/** adds a click listener to table rows */
function gmpe_table_add_row_clicklistener()
{
    /** highlight clicked table rows 
     * unbind existing listener first, then bind again
     */
    $('.table > tbody > tr').off('click').on('click', function(e) {
        /* switch this gmpe in the gmpes data array */
        sort = $( this ).attr( 'data-data-sort' );
        zone = $( this ).attr( 'data-data-key' );
        gmpe = $( this ).attr( 'data-entry-GMPE-Name' );
        period = $( this ).attr( 'data-entry-Period' );
        console.log($( this ).hasClass('info')?'row de-selected':'row selected', 'zone:', zone, 'gmpe:', gmpe, 'period:', period, this);
        /* the table has subheader rows and data rows containing data belonging to a subheader
         * in the zone table-view the subheader is the zone (Active, Azores-Gibralter, ...) and the rows are the gmpes
         * we distinguish what kind of row has been clicked by looking at the data- html attributes of the respective row
         * precisely at which data- attributes are missing. there are 3 to be expected: data-entry-Period, data-entry-GMPE-Name and data-data-key
         * in our case data-data-key is the zone, data-entry-GMPE-Name is the gmpe, data-entry-Period is the period
         * if all three are present it's a data row, if period is missing but gmpe is present it's a header in gmpe view, else one in zone view
         * the following table shows what data-html attributes to expect
         * 
         * zone gmpe period
         *   ✓    x    x   (list header zone)
         *   x    ✓    x   (list header gmpe)
         *   ✓    ✓    ✓   (list row)
         *
         * something table just has been clicked, so we first look at the period data- attribute ...
         */
        if (typeof period !== 'undefined') { /* ... it's a non-subheader row */
            /* switch the selected attribute toggle in the data object */
            mydata.data(zone,gmpe+period).selected( !mydata.data(zone,gmpe+period).selected() );
            /* select the same row in the table as well as in the info view */
            other_element_class = '.gfz_gmpe_tablerow';
            if ($( this ).hasClass('gfz_gmpe_tablerow')) {
                other_element_class = '.gfz_gmpe_info_tablerow';
            }
            /* criteria by which to find the other row */
            other_element_attribs = '[data-data-key="'+zone+'"]'+
                '[data-entry-GMPE-Name="'+gmpe+'"]'+
                '[data-entry-GMPE-Name="'+gmpe+'"]'+
                '[data-entry-Period="'+period+'"]';
            
            if (sort === 'zone' || sort === 'infoview' ) {
                /* select or deselect the clicked table row */
                if ($( this ).hasClass('info')) {
                    $( this ).removeClass('info');
                    $(other_element_class+other_element_attribs).removeClass('info');
                } else {
                    $( this ).addClass('info');
                    $(other_element_class+other_element_attribs).addClass('info');
                }
            } else if (sort === 'gmpe') {
                /* highlight rows with of the same zone */
                highlight_current_zone(zone);
            } else {
                /* throw an eror */
                console.log('error detected clicked target', this);
            }
        } else if (typeof gmpe !== 'undefined') {
            /* ... a header in the list (gmpe) */
        } else if (typeof zone !== 'undefined') {
            /* ... a header in the list (zone) */
            highlight_current_zone(zone);
        } else {
            /* throw error */
            console.log('error while processing clicked row!');
        }
    });
}

/** creates an info view that is to be displayed in a corner of the map 
 * <pre>this view displays the last shp layer feature that has been interacted with (e.g. clicked)
 * <pre>we need to wait for the data object to be available, so we implement it as a promise
 * see: {@link https://api.jquery.com/jquery.when/}
 * the deferred object mydata_def is resolved @fn {@link cb_data_ready}
 */
function infoview_create()
{
    $.when( mydata_def ).done( function(msg) {
        console.log('infoview create: mydata', msg, mydata);
        /* set the info object that we use to change the content of the info view
         * via its update fn */
        info = mydatadisplay.infoview(mydata, mystyle);
        /* add the info view to the map */
        info.addTo(mymap.map());
    });
}

/** creates an @class Style object that may be used to style the map's vector overlays
 * @param {Object} [style_def = {}] a style def object
 * @returns {Style} a style object to be used as parameter when creating the shp layer
 */
function vector_shp_styling(style_def = {})
{
    var feature_style_def = style_def,
        feature_property_name = 'TECREG',
        layer_style_def = {weight: 2, 
                           opacity: 0.2,
                           color: 'blue',
                           dashArray: '2',
                           fillOpacity: 0.51
                          },
        cb = function(e) {
            var zone = e.target.feature.properties.TECREG;
            highlight_current_zone(zone);
        };
    return new Style(layer_style_def, feature_property_name, feature_style_def, cb);
}

/** highlights a zone in the table when a subheader is clicked and updates the info view
 * @param {String} zone
 */
function highlight_current_zone(zone)
{
    /** update the info field within the map, unless it hasn't been created yet */
    if (typeof info !== 'undefined') info.update(zone);
    /** save to cookie */
    $.cookie('map_selected_zone', zone);
    /** highlight current zone in table */
    $('.gfz_gmpe_tablerow').each(function() {
        if ( $( this ).attr( 'data-data-key' ) === zone ) {
            //$( this ).attr( 'value', res_local[ $( this ).attr('value-local') ] );
            $( this ).addClass('success');
            //console.log($(this), $(this).attr('data-data-key'), $(this).attr('type'));      
        } else {
            $( this ).removeClass('success');
            //$( this ).html( res_local[ $( this ).attr('value-local') ] );
        }
    });
}

/** initializes some global variables
 * 
 */
function init_variables()
{
    /** @global */
    SIDEBAR_ID = 'sidebar',
    /** @global */
    ID_PREFIX = 'gfz_gmpe',
    /** @global */
    MAP_ID = 'leafletmap';
    /** @global */
    feature_style_def = {'Active':'#e4808c',
                         'Azores-Gibraltar':'#efa6a6',
                         'OC':'#f9d1bf',
                         'Ridge':'#fae6dd',
                         'SCR-Ext':'#fbfbfb',
                         'SCR-NoExt':'#bee8ff',
                         'SCR-Shield':'#73b2ff',
                         'Volcanic':'#ffaa00',
                         'Subduction Interface':'#b2d12b',
                         'Subduction-Inslab':'#aaa62a',
                         'Inslab':'#55a62a',
                         'Vrancea':'#16a841'
                        },
    /** @global */
    mydata_def = $.Deferred(),
    /** @global */
    mydatadisplay = new DataDisplay( ['GMPE-Name', 'Rank', 'Weight', 'Period'] );
    /** @global */
    top_entries = {},
    /** @global */
    bottom_entries = {},
    /** @global */
    osm_attrib = '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    /** @global */
    topo_attrib = 'Map data: &copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>, '+
        '<a href="http://viewfinderpanoramas.org">SRTM</a> | Map style: &copy; <a href="https://opentopomap.org">OpenTopoMap</a>'+
        ' (<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-SA</a>)',
    /** @global */
    zipfilereader = new ZipFileReader('feature_dropfield_layer');
    /* FIXME - invoke mock script to get some data. remove when we have actual data! */
    //$.getScript( "scripts/test/mock.js", function( data, textStatus, jqxhr ) { /*...*/ } );
}
