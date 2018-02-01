/**
 * 
 */

ngApp.controller("confRuptureController", ['$scope', 'inputSelection', '$http', function($scope, inputSelection, $http) {
		
	$scope.form = {};
	$scope.submitForm=function(form){
		data = {confRupture:$scope.form, gsimsInputSel: inputSelection.asObj};
		
		$scope.post("calculate_trellisp", data, {headers: {'Content-Type': 'application/json'}}).then(function(response) {
    			var g = 9;
    			// set loading flags to false
    	    });
		
		/*$http.post("calculate_trellisp", data, {headers: {'Content-Type': 'application/json'}}).then(function(response) {
    			var g = 9;
    			// set loading flags to false
    	    }, function(response) {  // error function, print message
    	    		$scope.handleError(response);
    	    });*/
			
			
			
			
        /* while compiling form , angular created this object*/
        //var data=$scope.fields;  
        /* post to server*/
        //$http.post(url, data);        
	}
}]);