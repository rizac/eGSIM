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

ngApp.controller("mainController", ['$scope', 'inputSelection', '$http',
	function($scope, inputSelection, $http) {
	
		// temp variables
		var _inputSelStr = "Input Selection";
		var _outStr = "Result";
		var _homeStr = 'Home';
		
		$scope.SERVICE_HOME = _homeStr;
		$scope.SERVICE_TRELLIS_PLOTS = 'Trellis Plots';
		$scope.SERVICE_DATA_ANALYSIS = 'Data Analysis';
		
		// services here is the eGSIM service, a SUBMENU of the main app.
		// NOT TO BE CONFUSED WITH ANGULAR SERVICE! (directory services) whereby we implement inputSelection
    		$scope.services = new SelMap([
    									[_homeStr, new SelArray()],
    									[$scope.SERVICE_TRELLIS_PLOTS, new SelArray(_inputSelStr, "Config. Scenario", _outStr).select(_inputSelStr)],
    									[$scope.SERVICE_DATA_ANALYSIS, new SelArray(_inputSelStr, _outStr).select(_inputSelStr)]
    								 ]).select(_homeStr);
    		
    		// helper functions:
    		$scope.services.names = Array.from($scope.services.keys());
    		
    		$scope.isServiceName = function(name){
    			return $scope.services.selKey === name;
    		};
    		$scope.isSubmenuIndex = function(index){
    			return $scope.services.get($scope.services.selKey).selIndex === index;
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
    		
    		
    		$http.post("get_init_params", {}, {headers: {'Content-Type': 'application/json'}}).then(function(response) {
    			inputSelection.init(response.data.avalGsims);
    			// set loading flags to false
    	    }, function(response) {  // error function, print message
    	    		$scope.handleError(response);
    	    });
    		
    		$scope.inputSelection = inputSelection;
    		$scope.temporarySelectedGsims = [];
    		$scope.setSelectedGsims = function(){
    			$scope.inputSelection.addGsims($scope.temporarySelectedGsims);
    			$scope.temporarySelectedGsims = [];
    		}

    		$scope.handleError = function(response){
    			// no-op (for the moment)
    			var status = response.status; //the code
    			var statusText = response.statusText; //the message
    			var data = response.data;  // whatever else, sometimes a detailed page with the message or what we decided to write here server-side
    		};
    		
    		$scope.visibleGsimsCount = 0;
    		$scope.filterText = '';
    		$scope.filterRegexp = undefined;
    		$scope.filterTypeName = 'Name';
    		function filterByName(gsim){
    			return $scope.inputSelection.matchesByName(gsim, $scope.filterRegexp);
    		}
    		function filterByImt(gsim){
    			return $scope.inputSelection.matchesByImt(gsim, $scope.filterRegexp);
    		}
    		function filterByTrt(gsim){
    			return $scope.inputSelection.matchesByTrt(gsim, $scope.filterRegexp);
    		}
    		$scope.filterTypes = new Map([
    										[$scope.filterTypeName, filterByName],
    										['Intensity Measure Type', filterByImt],
    										['Tectonic Region Type', filterByTrt]
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

