/*** data fetch 
 ** for now we fetch the data using php scripts
 ** FIXME - data fetch interface?
 **/
(function () {
    var mydata = new Data(), data_gmpes, data_zones;
    /* async call to some php scripts that fetch data to work with */
    function get_data_function(callback)
    {
        $.ajax({ url: 'php/test/mock.php',
                 data: { action: 'gmpe' },
                 type: 'POST',
                 success: function(output) {
                     _out = JSON.parse(output);
                     data_gmpes = _out.gmpes.GMPE;
                     data_zones = _out.zones;
                     /* done - call back */
                     //callback();
                     data_assemble_done();
                     console.log('async return output', 'gmpes', data_gmpes, 'zones', data_zones);
                 },
                 error: function (xhr, ajaxOptions, thrownError) {
                     console.log('error fetching data', xhr.status, thrownError);
                 }
        });
    }
    /** php is done fetching - let's create a data object to work with */
    function data_assemble_done()
    {
        /* populate data object */
        $.each(data_zones, function(zone, gmpes){
            //mydata[zone] = {};
            $.each(gmpes, function(i, gmpe){
                mydata.data(zone, gmpe['GMPE-Name']+gmpe['Period'], new Gmpe(gmpe));
            });
        });     
        console.log('--- data objects ---', 'data zones', data_zones, 'data', mydata/*, 'zones', zones*/);
        /** pass the data object back to the application */
        cb_data_ready(mydata);
    }
    /* get data ~ */
    get_data_function();
})();
/*** /data fetch **/
