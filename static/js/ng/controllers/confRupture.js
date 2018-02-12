/**
 * 
 */

ngApp.controller("confRuptureController", ['$scope', 'gsimsInput', 'trellisData', '$http', function($scope, gsimsInput, trellisData, $http) {

    $scope.isValid = function(){
        // Forms have the following states:
        // $pristine  No fields have been modified yet
        // $dirty     One or more have been modified
        // $invalid   The form content is not valid
        // $valid     The form content is valid
        // $submitted The form is submitted
        return $scope.gsimsInput.isValid && $scope.c_r_form.$valid;
    };

    $scope.trellisData = trellisData;

    $scope.submitForm=function(){
        data = {confRupture:$scope.form, gsimsInputSel: gsimsInput.asObj};

        $scope.post("validate_trellis_input", data, {headers: {'Content-Type': 'application/json'}}).then(function(response) {
            $scope.post("get_trellis_plots", response.data, {headers: {'Content-Type': 'application/json'}}).then(function(response) {
                $scope.trellisData.init(response.data);
                $scope.service.moveNext();
            });
        });
    }

}]);