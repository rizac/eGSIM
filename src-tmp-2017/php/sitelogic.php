<?php

/** prints a warning if no js is detected */
function print_nojswarning($id)
{
    echo '<div id="'.$id.'" class="alert alert-warning alert-dismissable"><button type="button" class="close" data-dismiss="alert" aria-hidden="true">&times;</button><p>Javascript is disabled. This site does not work without it.</p></div>';
}

/** echoes a sidebar's entry header */
function add_sidebar_header($value_local)
{
    echo '<h1 class="sidebar-header"><span class="gfz_gmpe_localisation" value-local="'.$value_local.'"></span>
              <span class="sidebar-close"><i class="fa fa-caret-left"></i></span>
          </h1>';
}

function add_sidebar_toggle($desc_local, $toggle_id)
{
    echo '<div id="gfz_gmpe_lower_elements_wrapper" class="container-fluid">
             <div class="row">
                <div id="" class="col-xs-6 col-sm-6 col-md-6 col-lg-6">
                   <span class="gfz_gmpe_localisation" value-local="'.$desc_local.'" style="float:left"></span>
                </div>
                <div id="" class="col-xs-6 col-sm-6 col-md-6 col-lg-6">
                   <!-- checkbox toggle -->
                   <input id="'.$toggle_id.'" checked type="checkbox">
                </div>
             </div>
          </div>';
}

/** @return does what the func name sayeth */
function phpinfo2var()
{
    ob_start () ;
    phpinfo () ;
    $phpinfo = ob_get_contents () ;
    ob_end_clean () ;
    return $phpinfo;
}

/** contructs the complete header
 * @param $header a @class Header object
 */
function populize_header($header)
{
    $SCHEME = '';
    $s = $header->add_script('https://code.jquery.com/jquery-3.1.0.min.js', 'jQuery - https://jquery.com/');
    /* $s->get()->comment(''); */
    $header->add_script($SCHEME.'plugins/cookies/jquery.cookie.js', 'cookie: http://plugins.jquery.com/cookie/');
    $header->add_comment('LOCALIZATION');
    $header->add_script($SCHEME.'lang/lang.en.js', 'language localisation file');
    $header->add_script($SCHEME.'scripts/lang_funcs.js', 'language helper file');
    $header->add_comment('LEAFLET');
    $header->add_link('https://unpkg.com/leaflet@1.0.1/dist/leaflet.css', 'leaflet style def');
    $header->add_link($SCHEME.'styles/gmpe_mapstyle.css', 'own leaflet style def');
    $header->add_script('https://unpkg.com/leaflet@1.0.1/dist/leaflet.js', 'leaflet distribution');
    $header->add_link($SCHEME.'plugins/coordinates/src/Control.Coordinates.css', 'see: https://github.com/MrMufflon/Leaflet.Coordinates');
    $header->add_comment('[if lte IE 8]><link rel="stylesheet" href="leaflet/plugins/coordinates/src/Control.Coordinates.ie.css" /><![endif]');
    $header->add_script($SCHEME.'plugins/coordinates/src/Control.Coordinates.js', 'see: https://github.com/MrMufflon/Leaflet.Coordinates');
    $header->add_script($SCHEME.'plugins/coordinates/src/util/NumberFormatter.js', 'see: https://github.com/MrMufflon/Leaflet.Coordinates');
    $header->add_link($SCHEME.'styles/font-awesome/css/font-awesome.css', 'font awesome (e.g. required by easybutton & sidebar) see: http://fontawesome.io/icons/');

    $header->add_comment('SIDEBAR');
    $header->add_link($SCHEME.'plugins/sidebar/leaflet-sidebar.css', 'see: https://github.com/Turbo87/sidebar-v2');
    $header->add_script($SCHEME.'plugins/sidebar/leaflet-sidebar.min.js', 'see: https://github.com/Turbo87/sidebar-v2');
    $header->add_script($SCHEME.'scripts/sidebar_funcs.js', 'see: https://github.com/Turbo87/sidebar-v2');

    $header->add_comment('BOOTSTRAP (3.3.7)');
    $header->add_comment('must be loaded below / after autocomplete!');
    $header->add_link($SCHEME.'plugins/bootstrap/bootstrap/css/bootstrap.min.css', 'see: http://getbootstrap.com/javascript/');
    $header->add_script($SCHEME.'plugins/bootstrap/bootstrap/js/bootstrap.min.js', 'see: http://getbootstrap.com/javascript/');
    $header->add_script($SCHEME.'plugins/bootstrap/tabscollapse/bootstrap-tabcollapse.js', 'bootstrap collapsable tabs plugin - see: https://github.com/flatlogic/bootstrap-tabcollapse');
    $header->add_script($SCHEME.'plugins/bootstrap/autohidingnavbar/jquery.bootstrap-autohidingnavbar.min.js', 'bootstrap auto hiding navbar plugin - see: http://www.virtuosoft.eu/code/bootstrap-autohidingnavbar/');
    $header->add_link($SCHEME.'plugins/bootstrap/slider/bootstrap-slider.min.css', 'bootstrap slider plugin - see: https://github.com/seiyria/bootstrap-slider');
    $header->add_script($SCHEME.'plugins/bootstrap/slider/bootstrap-slider.min.js', 'bootstrap slider plugin - see: https://github.com/seiyria/bootstrap-slider');
    $header->add_link('https://gitcdn.github.io/bootstrap-toggle/2.2.2/css/bootstrap-toggle.min.css', 'bootstrap toogle plugin - see: http://www.bootstraptoggle.com/');
    $header->add_script('https://gitcdn.github.io/bootstrap-toggle/2.2.2/js/bootstrap-toggle.min.js', 'bootstrap toogle plugin - see: http://www.bootstraptoggle.com/');
    $header->add_comment('MATHJAX');
    $header->add_comment('MathJax Online Editor: http://www.codecogs.com/latex/eqneditor.php');

    $header->add_comment('JQUERY UI');
    $header->add_script('https://code.jquery.com/ui/1.10.3/jquery-ui.js', 'jquery ui: https://jqueryui.com/');
    $header->add_link('https://code.jquery.com/ui/1.11.3/themes/smoothness/jquery-ui.css', 'jquery ui: https://jqueryui.com/');
    
    $header->add_comment('ESRI PLUGINS');
    $header->add_script('https://unpkg.com/esri-leaflet@2.0.7', 'see: http://esri.github.io/esri-leaflet/examples/');
    
    $header->add_comment('SHAPEFILE');
    $header->add_script($SCHEME.'plugins/shapefile/leaflet.shpfile.js', 'leaflet shapefile plugin - see: https://github.com/calvinmetcalf/leaflet.shapefile');
    //$header->add_script('plugins/shapefile/catiline.js', 'leaflet shapefile plugin - see: https://github.com/calvinmetcalf/leaflet.shapefile');
    $header->add_script($SCHEME.'plugins/shapefile/shp.js', 'leaflet shapefile plugin - see: https://github.com/calvinmetcalf/leaflet.shapefile');
    
    $header->add_comment('LOOSE ADDITIONS');
    $header->add_script($SCHEME.'plugins/finger/jquery.finger.min.js', 'jQuery finger plugin - see: https://github.com/ngryman/jquery.finger');
    
    $header->add_comment('MAP FRAMEWORK SCRIPTS');
    // TODO - remove leaflet_funcs soon
    //$header->add_script('scripts/leaflet_funcs.js', 'legacy own leaflet functions');
    $header->add_script($SCHEME.'scripts/oop/site.js', 'site class');
    $header->add_script($SCHEME.'scripts/oop/map.js', 'base framework map class');
    $header->add_script($SCHEME.'scripts/oop/style.js', 'framework layer style definition wrapper class');
    $header->add_script($SCHEME.'scripts/oop/layerstyle.js', 'framework layer styling class');
    $header->add_script($SCHEME.'scripts/oop/legend.js', 'framework layer legend class');
    $header->add_script($SCHEME.'scripts/oop/layer.js', 'framework vector overlay parent class');
    $header->add_script($SCHEME.'scripts/oop/baselayer.js', 'framework tile baselayer class');
    $header->add_script($SCHEME.'scripts/oop/jsonlayer.js', 'framework json overlay class');
    $header->add_script($SCHEME.'scripts/oop/shpjsonlayer.js', 'framework shp overlay class');
    $header->add_script($SCHEME.'scripts/oop/zipfilereader.js', 'framework zip filereader class');
    $header->add_script($SCHEME.'scripts/oop/instancestate.js', 'framework zip instacestate class');
}

    
?>
