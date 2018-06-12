/**
 * 
 */

/* function called after a succesfull request is returned by the server.
 * The response is the response object.
 * This function will be registered to the EGSIM.configureForm (see bottom of this file)
 * where EGSIM is a Vue instance managing the main content of the current html page
 */
function createTrellisPlots(response){
    alert('ok!');
}

/* configure the EGSIM object with a url when the form is submitted and a callback
 * (just defined) when a response is successfully returned
 */
EGSIM.configureForm('get_trellis_plots', createTrellisPlots);