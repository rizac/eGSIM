<?php

    
/** --- framework related global defines --- */
    
/* development switch */
define('DEVEL', true);
/* HTML ID prefix */
define('HTML_ID_PREFIX', 'gfz_gmpe');
/* base dir | web root */
define('BASE_DIR', '/home/rs/prehn/git/gmpeservice/gmpeservice/web/app/static/');
/* php language init script */
define('LANG_FILE_PATH', BASE_DIR . 'php/oop/language.php');
/* php interfaces */
define('INTERFACES_FILE_PATH', BASE_DIR . 'php/oop/interfaces.php');
/* php header php class */
define('HEADER_CLASS_PATH', BASE_DIR . 'php/oop/header.php');
/* php sidebar php class */
define('SIDEBAR_CLASS_PATH', BASE_DIR . 'php/oop/sidebar.php');


/** --- GMPE-Service global defines --- */
    
/* php site logic functions */
define('LOGIC_FILE_PATH', BASE_DIR . 'php/sitelogic.php');
    
/* FIXME db credentials */
define('CONN_FILE_PATH', BASE_DIR . 'config/connection.ini');
/* db data access file */
define('DB_FILE_PATH', BASE_DIR . 'php/oop/database.php');
/* FIXME db json util file */
define('JSONUTIL_FILE_PATH', BASE_DIR . 'db_access/db_jsonutil.php');

    
?>  