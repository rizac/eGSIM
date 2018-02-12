/**
 * Defines the main controller on the root scope.
 * Remember that child scopes can ACCESS the properties/methods defined in the parent scope, but
 * hide them if set on the child
 */

// Create a new module.
// Iterestingly, if we remove this line everything works fine. We should understand why.
//Is a global module ngApp created, and the line below retrieves it? Then why the need of such  a line?
// We comment for the moment keeping in mind that we should use it once understood that it's important
// var ngApp = angular.module('eGSIM', []);

ngApp.controller("mainController", ['$scope', 'gsimsInput', '$http', '$timeout',
    function($scope, gsimsInput, $http, $timeout) {

        // temp variables
        var _inputSelStr = "Input Selection";
        var _outStr = "Result";
        var _homeStr = 'Home';
 
        $scope.SERVICE_HOME = _homeStr;
        $scope.SERVICE_TRELLIS_PLOTS = 'Trellis Plots';
        $scope.SERVICE_DATA_ANALYSIS = 'Data Analysis';

        // services here is the eGSIM service, a SUBMENU of the main app.
        // NOT TO BE CONFUSED WITH ANGULAR SERVICE! (directory services) whereby we implement gsimsInput
        $scope.services = new SelMap([
            [_homeStr, new SelArray()],
            [$scope.SERVICE_TRELLIS_PLOTS, new SelArray(_inputSelStr, "Config. Scenario", _outStr).select(0)],
            [$scope.SERVICE_DATA_ANALYSIS, new SelArray(_inputSelStr, _outStr).select(0)]
        ]).select(_homeStr);
        

        // helper functions:
        $scope.serviceNames = Array.from($scope.services.keys());
        $scope.subMenuNames = function(serviceName){return $scope.services.get(serviceName);}
        // $scope.service exposes SelMap's and SelArray's methods in a more friendly way for
        // a html view's reader:
        $scope.service = {
                get name(){
                    return $scope.services.selKey;
                },
                set name(name){
                    $scope.services.selKey = name;
                    $scope.dropdown = false;  // hide dropdown menu
                },
                subMenu: {
                    get _(){
                        return $scope.subMenuNames($scope.services.selKey);
                    },
                    get index(){
                        return this._.selIndex;
                    },
                    set index(index){
                        this._.selIndex = index;
                    },
                    moveNext: function(){
                        this._.selNext();
                    },
                    moveBack: function(){
                        this._.selPrev();
                    },
                    get canMoveBack(){
                        return this._.selHasPrev;
                    },
                    get canMoveNext(){
                        return this._.selHasNext;
                    }
                }
        };

        $scope.post = function(...args){
            $scope.hasError = false;
            this._args = args;
            return {
                then(callback){
                    $http.post(...args).then(function(response) {
                        callback(response);
                        // set loading flags to false
                    }, function(response) {  // error function, print message
                        $scope.handleError(response);
                    });
                }
            }
        };

        $http.post("get_init_params", {}, {headers: {'Content-Type': 'application/json'}}).then(function(response) {
            gsimsInput.init(response.data.avalGsims);
            // set loading flags to false
        }, function(response) {  // error function, print message
            $scope.handleError(response);
        });

        $scope.gsimsInput = gsimsInput;
        $scope.temporarySelectedGsims = [];
        $scope.setSelectedGsims = function(){
            $scope.gsimsInput.addGsims($scope.temporarySelectedGsims);
            $scope.temporarySelectedGsims = [];
        }

        $scope.hasError = false;
        $scope.handleError = function(response){

            $scope.hasError = true;
            var iframe = document.getElementById('errFrame');
            iframe.contentWindow.document.open();
            iframe.contentWindow.document.write(response.data);
            iframe.contentWindow.document.close();
            // no-op (for the moment)
            var status = response.status; //the code
            var statusText = response.statusText; //the message
            var data = response.data;  // whatever else, sometimes a detailed page with the message or what we decided to write here server-side
        };

        $scope._trMapID = 'trMap';
        $scope.mapManager = new MapManager($scope._trMapID);
        $scope.filterSelected = function(){
            // delay the map setup so that the div is correctly laid out.
            // FIXME: this is horrible, better change it later
            if ($scope.filterTypeName == $scope.filterTypeNames[2] && !$scope.mapManager.ready){
                $timeout(function(){
                    $scope.mapManager.init($scope._trMapID);
                }, 1000);
            };
        };

        $scope.visibleGsimsCount = 0;
        $scope.filterText = '';
        $scope.filterRegexp = undefined;
        $scope.filterTypeNames = ['Name', 'Intensity Measure Type', 'Tectonic Region Type'];
        $scope.filterTypeName = $scope.filterTypeNames[0];
        function filterByName(gsim){
            return $scope.gsimsInput.matchesByName(gsim, $scope.filterRegexp);
        }
        function filterByImt(gsim){
            return $scope.gsimsInput.matchesByImt(gsim, $scope.filterRegexp);
        }
        function filterByTrt(gsim){
            return $scope.gsimsInput.matchesByTrt(gsim, $scope.filterRegexp);
        }
        $scope.filterTypes = new Map([
            [$scope.filterTypeNames[0], filterByName],
            [$scope.filterTypeNames[1], filterByImt],
            [$scope.filterTypeNames[2], filterByTrt]
        ]);
        $scope.filterTypeNames = Array.from($scope.filterTypes.keys());
        $scope.gsimsFilter = function(gsim, index, gsims) {
            var ret = true;
            if(index == 0){
                $scope.visibleGsimsCount = 0;
            }
            if ($scope.filterText){
                if(index == 0){
                    $scope.filterRegexp = new RegExp($scope.filterText.replace(/\*/g, '.*').replace(/\?/g, '.'), 'i');
                }
                ret = $scope.filterTypes.get($scope.filterTypeName)(gsim);
            }
            $scope.visibleGsimsCount += ret;
            return ret;
        };
    }
]);
