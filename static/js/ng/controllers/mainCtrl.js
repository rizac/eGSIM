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
    		$scope.services.names = Array.from($scope.services.keys());
    		
    		$scope.isServiceName = function(name){
    			return $scope.services.selKey === name;
    		};
    		$scope.isSubmenuIndex = function(index){
    			return $scope.services.get($scope.services.selKey).selIndex === index;
    		};
    		
    		$scope.selectNext = function(){
    			if ($scope.services.get($scope.services.selKey)){
    				$scope.services.get($scope.services.selKey).selNext();
    			}
    		};
    		
    		$scope.selectPrev = function(){
    			if ($scope.services.get($scope.services.selKey)){
    				$scope.services.get($scope.services.selKey).selPrev();
    			}
    		};
    		// expose the property we need 
    		// with clearer names and provide angular with arrays instead of Sets/ Maps
    		// all these are function for avoiding typos
    		
    		// services.names array
    		// services.selected = name  //select new service
    		// services.selected.name string
    		// services.selected.subMenus.names array
    		// services.selected.subMenus.selected = name  // select new service
    		// services.selected.subMenus.selected.name string
    		// services.selected.subMenus.selected.hasNext bool
    		// services.selected.subMenus.selected.hasPrev bool
    		// services.selected.subMenus.selected.selNext() func
    		// services.selected.subMenus.selected.selPrev() func
    		
    		
    		
    		// serviceNames
    		// serviceName
    		// serviceSubmenus
    		// serviceSubmenu
    		
//    		$scope.selectedServiceSubmenus = function(){
//    			return Array.from($scope.services.get($scope.services.selKey));
//    		}; // angular complains when ng-repeat not iterated over Array
    		
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
	    				this._callback = callback;
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
    									]
    								);
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


// defining the search filer. FIXME: maybe implement it elsewhere?
//ngApp.filter('reverse', function() {
//	return function(input, type) {  //type can be 'text', 'zonation' or what?
//		input = input || '';
//		var out = '';
//		if 
//		
//		for (var i = 0; i < input.length; i++) {
//			out = input.charAt(i) + out;
//		}
//		// conditional based on optional argument
//		if (uppercase) {
//			out = out.toUpperCase();
//		}
//		return out;
//	};
//})

