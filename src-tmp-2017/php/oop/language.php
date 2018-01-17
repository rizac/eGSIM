<?php
/** GMPE-Service language init script */
session_start();
header('Cache-control: private'); // IE 6 FIX

if(isSet($_GET['lang'])) {
    $lang = $_GET['lang'];
    // register the session and set the cookie
    $_SESSION['lang'] = $lang;

    setcookie('lang', $lang, time() + (3600 * 24 * 30)); // 30 days
} else if(isSet($_SESSION['lang'])) {
    $lang = $_SESSION['lang'];
} else if(isSet($_COOKIE['lang'])) {
    $lang = $_COOKIE['lang'];
} else {
    $lang = 'en';
}

switch ($lang) {
case 'en':
    $lang_file = 'lang.en.php';
    break;
case 'de':
    $lang_file = 'lang.de.php';
    break;
default:
    $lang_file = 'lang.en.php';
}

//include_once /*'lang/'.*/$lang_file;

?>