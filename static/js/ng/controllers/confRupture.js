/**
 * 
 */

ngApp.controller("confRuptureController", ['$scope', 'inputSelection', '$http',
	function($scope, inputSelection, $http) {
	
		// temp variables
	$scope.submitForm=function(form){
		/* we might setup the form fields via ng-model attached to every
		 * input in the form. However to achieve this we should customize django
		 * form field rendering, which is a great pain.
		 * To circumvent this, there's a library called django-widget-tweaks
		 * which allows us to insert custom attrs to each form field.
		 * But we should use ng-init for that, as ng-value does not set the value here
		 * in the scope (and moreover, ng-value does not work with <select> tags 
		 * as it does not recognizes the relative option, when the value is a string)
		 * So we ended up doing this, which might be bad (who knows) but works,
		 * let's manipulate the angular object:
		 */
		var values = {};
		var formHTMLElement = form.$$element[0];
		for(var i =0; i < formHTMLElement.length; i++){
			values[formHTMLElement[i].name] = formHTMLElement[i].value;
		} 
        /* while compiling form , angular created this object*/
        var data=$scope.fields;  
        /* post to server*/
        $http.post(url, data);        
    }
    		
    		
	}
]);