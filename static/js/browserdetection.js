// functions for checking the browser version:
function getBrowser() {
    // returns the [name, version] list, where name is the current browser name and
    // version is the version (might be undefined)
    // This method is heuristic and should not be used for reliable code: we use it only to
    // display a warning message. For info see: https://stackoverflow.com/a/16938481
    var _pInt = function(value){
        return value===undefined || value === null || isNaN(parseInt(value)) ? undefined : parseInt(value);
    };

    var ua=navigator.userAgent;
    var tem;
    var M=ua.match(/(opera|chrome|safari|firefox|msie|trident(?=\/))\/?\s*(\d+)/i) || []; 
    if(/trident/i.test(M[1])){
        tem=/\brv[ :]+(\d+)/g.exec(ua) || []; 
        return {
            name:'IE',
            version: _pInt(tem[1])
        };
    }   
    if(M[1]==='Chrome'){
        tem=ua.match(/\bOPR|Edge\/(\d+)/)
        if(tem!=null){
            return {
                name:'Opera',
                version: _pInt(tem[1])
            };
        }
    }   
    M = M[2] ? [M[1], M[2]] : [navigator.appName, navigator.appVersion, '-?'];
    if((tem=ua.match(/version\/(\d+)/i))!=null){
        M.splice(1,1,tem[1]);
    }
    return {
        name: M[0].toLowerCase(),
        version: _pInt(M[1])
    };
}
function incompatibleBrowserMessage(allowedBrowsers, invalidBrowserMessage){
    // returns `invalidBrowserMessage` if the current browser does not match
    // any of `allowedBrowsers`. The latter is a list of [name, version] lists,
    // where name is the browser name (case insensitive) and version is the
    // browser minimum required version (int)
    var browser = getBrowser();
    for (var [testedBrowser, testedVersion] of allowedBrowsers){
        if (browser.name.toLowerCase() === testedBrowser.toLowerCase()){
            if (browser.version === undefined || browser.version < testedVersion){
                return invalidBrowserMessage;
            }else{
                return '';
            }
        }
    }
    return invalidBrowserMessage;
}