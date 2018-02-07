/**
 * 
 */

ngApp.controller("confRuptureController", ['$scope', 'inputSelection', '$http', function($scope, inputSelection, $http) {
		
	$scope.isValid = function(){
//		Forms have the following states:
//		$pristine  No fields have been modified yet
//		$dirty     One or more have been modified
//		$invalid   The form content is not valid
//		$valid     The form content is valid
//		$submitted The form is submitted
		return $scope.inputSelection.isValid && $scope.c_r_form.$valid;
	};

	$scope.submitForm=function(){
		data = {confRupture:$scope.form, gsimsInputSel: inputSelection.asObj};
		
		$scope.post("validate_trellis_input", data, {headers: {'Content-Type': 'application/json'}}).then(function(response) {
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