<?php
/** POST'ed */

include_scripts();

if(isset($_POST['action']) && !empty($_POST['action'])) {
    $action = $_POST['action'];
    /* init db & access */
    $db = new Database('GMPE');
    switch($action) {
    case 'gmpe' : mock_data_query_gmpe($db);break;
    }
}

function include_scripts()
{
    /** 
     * === GMPE-Service: frontend ===
     */

    /**
     * remote debug: https://developer.mozilla.org/de/docs/Tools/Remote_Debugging/Firefox_for_Android !!!
     * adb forward tcp:6000 localfilesystem:/data/data/org.mozilla.firefox/firefox-debugger-socket
     */

    /** includes */
    /* config file */
    require_once '../../config/config.php';
    /* include script with all site logic helper functions */
    include_once LOGIC_FILE_PATH;
    /* include translation language file here according to pseudo-url 'lang' argument */
    include LANG_FILE_PATH;
    /* include interfaces script */
    include INTERFACES_FILE_PATH;
    /* include header class */
    include HEADER_CLASS_PATH;
    /* include sidebar class */
    include SIDEBAR_CLASS_PATH;
    /* include database class */
    include DB_FILE_PATH;
}

function mock_data_query_gmpe($db)
{
    $gmpes = mock_data_query_gmpe_names($db);
    $zones = mock_data_query_gmpe_zones($db);
    $result = [];
    $result['gmpes'] = $gmpes;
    $result['zones'] = $zones;
    echo json_encode($result);
}

function mock_data_query_gmpe_names($db)
{
    $gmpes_columns = array('`GMPE-Name`'); 
    $gmpes_tables = array('GMPE');
    $gmpes_res = $db->query_db($gmpes_tables, $gmpes_columns);
    return $db->to_js_object('gmpes');
}

function mock_data_query_gmpe_zones($db)
{
    $zones_columns = array('`GMPE-Name`', 'Rank', 'ROUND(Weight,3) as Weight', 'IFNULL(Period,"") as Period');
    $zones_tables = array('Active','`Azores-Gibraltar`','OC','Ridge','`SCR-Ext`','`SCR-NoExt`','`SCR-Shield`',/* 'Subduction Interface',*/
                          'Volcanic', '`Subduction-Inslab`',/* 'Inslab',*/ 'Volcanic','Vrancea');
    $zones_res = $db->query_db($zones_tables, $zones_columns);
    return $db->to_js_object('mydbresult');
}


?>
