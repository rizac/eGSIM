/**
 * Defines the main controller on the root scope.
 * Remember that child scopes can ACCESS the properties/methods defined in the parent scope, but
 * hide them if set on the child
 */

ngApp.controller("mainController", ['gsimsInput', '$http', '$timeout',
    function(gsimsInput, $http, $timeout) {

        var me = this;
        // temp variables
        var _inputSelStr = "Input Selection";
        var _outStr = "Result";
        var _homeStr = 'Home';
 
        me.SERVICE_HOME = _homeStr;
        me.SERVICE_TRELLIS_PLOTS = 'Trellis Plots';
        me.SERVICE_DATA_ANALYSIS = 'Data Analysis';

        // services here is the eGSIM service, a SUBMENU of the main app.
        // NOT TO BE CONFUSED WITH ANGULAR SERVICE! (directory services) whereby we implement gsimsInput
        me.services = new SelMap([
            [_homeStr, new SelArray()],
            [me.SERVICE_TRELLIS_PLOTS, new SelArray(_inputSelStr, "Config. Scenario", _outStr)],
            [me.SERVICE_DATA_ANALYSIS, new SelArray(_inputSelStr, _outStr)]
        ]);
        me.services.selection = _homeStr;
        for(let entry of me.services){
            entry[1].selection = 0;
        }

        // helper functions:
        me.serviceNames = Array.from(me.services.keys());
        me.subMenuNames = function(serviceName){return me.services.get(serviceName);}
        // me.service exposes SelMap's and SelArray's methods in a more friendly way for
        // a html view's reader:
        me.service = {
                get name(){  // reutrns the current service name
                    return me.services.selection;
                },
                set name(name){  // sets current service name
                    me.services.selection = name;
                    me.dropdown = false;  // hide dropdown menu
                },
                subMenu: {
                    get _(){
                        return me.subMenuNames(me.services.selection);
                    },
                    get index(){
                        return this._.selection;
                    },
                    set index(index){
                        this._.selection = index;
                    },
                    moveNext: function(){
                        if (this.canMoveNext){this.index += 1;}
                    },
                    moveBack: function(){
                        if (this.canMoveBack){this.index -= 1;}
                    },
                    get canMoveBack(){
                        return this.index > 0;
                    },
                    get canMoveNext(){
                        return this.index < this._.length -1;
                    }
                }
        };

        me.post = function(...args){
            me.hasError = false;
            this._args = args;
            return {
                then(callback){
                    $http.post(...args).then(function(response) {
                        callback(response);
                        // set loading flags to false
                    }, function(response) {  // error function, print message
                        me.handleError(response);
                    });
                }
            }
        };

        $http.post("get_init_params", {}, {headers: {'Content-Type': 'application/json'}}).then(function(response) {
            gsimsInput.init(response.data.avalGsims);
            // set loading flags to false
        }, function(response) {  // error function, print message
            me.handleError(response);
        });

        me.gsimsInput = gsimsInput;
        me.temporarySelectedGsims = [];
        me.setSelectedGsims = function(){
            me.temporarySelectedGsims.forEach(function(gsim){me.gsimsInput.gsims.selection.add(gsim)});
            me.temporarySelectedGsims = [];
        }

        me.hasError = false;
        me.handleError = function(response){

            me.hasError = true;
            var iframe = document.getElementById('errFrame');
            iframe.contentWindow.document.open();
            iframe.contentWindow.document.write(response.data);
            iframe.contentWindow.document.close();
            // no-op (for the moment)
            var status = response.status; //the code
            var statusText = response.statusText; //the message
            var data = response.data;  // whatever else, sometimes a detailed page with the message or what we decided to write here server-side
        };

        me._trMapID = 'trMap';
        me.mapManager = new MapManager(me._trMapID);
        me.filterSelected = function(){
            // delay the map setup so that the div is correctly laid out.
            // FIXME: this is horrible, better change it later
            if (me.filterTypeName == me.filterTypeNames[2] && !me.mapManager.ready){
                $timeout(function(){
                    me.mapManager.init(me._trMapID);
                }, 1000);
            };
        };

        me.visibleGsimsCount = 0;
        me.filterText = '';
        me.filterRegexp = undefined;
        me.filterTypeNames = ['Name', 'Intensity Measure Type', 'Tectonic Region Type'];
        me.filterTypeName = me.filterTypeNames[0];
        function filterByName(gsim){
            return me.gsimsInput.matchesByName(gsim, me.filterRegexp);
        }
        function filterByImt(gsim){
            return me.gsimsInput.matchesByImt(gsim, me.filterRegexp);
        }
        function filterByTrt(gsim){
            return me.gsimsInput.matchesByTrt(gsim, me.filterRegexp);
        }
        me.filterTypes = new Map([
            [me.filterTypeNames[0], filterByName],
            [me.filterTypeNames[1], filterByImt],
            [me.filterTypeNames[2], filterByTrt]
        ]);
        me.filterTypeNames = Array.from(me.filterTypes.keys());
        me.gsimsFilter = function(gsim, index, gsims) {
            var ret = true;
            if(index == 0){
                me.visibleGsimsCount = 0;
            }
            if (me.filterText){
                if(index == 0){
                    me.filterRegexp = new RegExp(me.filterText.replace(/\*/g, '.*').replace(/\?/g, '.'), 'i');
                }
                ret = me.filterTypes.get(me.filterTypeName)(gsim);
            }
            me.visibleGsimsCount += ret;
            return ret;
        };
    }
]);
