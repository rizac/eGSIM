/* language code */
var locale_local;

/* self invoking function call */
(function()
 {
     var locale_supported = { 'en': ['en-US', 'en-GB'], 'de': ['de-DE'] };
     locale_local = 'en'; // default locale

     if ($.cookie("lang")) {
         console.log($.cookie("lang"));
         locale_test = $.cookie("lang");
     } else {
         locale_test = navigator.language; // locale as per browser settings;
     }

     // test if current locale value is supported and if so assign it
     $.each(locale_supported, function(key, value) {
         if($.inArray(locale_test, value) >= 0){
             locale_local = key;
             return false; // break
         } else if (locale_test === key) {
             locale_local = key;
             return false; // break
         }
         //console.log(key, locale_supported[key]);
         return true;
     });

     // add click listener to 
     $(document).on('click', '#gfz_gmpe_language_dropdown_list li a', function() {
         locale_local = $(this).attr('value');
         $.cookie("lang", locale_local);
         localizeDocument();
     });
 }
)();

/* localize the whole web page based on local JSON files 
 * matches for <tag> class="gfz_deqhaz16_localisation" value-local="SOME_VALUE"</tag>
*/
var localize_document = function()
{
    // get the language script from the server and do something when done
    $.getScript('lang/lang.'+locale_local+'.js', function() {
        // localize each appropriate html element
        $('.gfz_gmpe_localisation').each(function() {
            // treat submit buttons differently
            if ($( this ).attr( 'type' ) === 'submit') {
                $( this ).attr( 'value', res_local[ $( this ).attr('value-local') ] );
            } else {
                $( this ).html( res_local[ $( this ).attr('value-local') ] );
            }
        });
        /*FIXME var cp = get_coordinate_plugin();
        if (cp) {
            console.log('localizing', locale_local);
            cp.localize();
        }*/
    });
};
