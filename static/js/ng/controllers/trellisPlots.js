/**
 * 
 */

ngApp.controller("trellisPlots", ['$scope', 'trellisData', '$http', '$timeout',function($scope, trellisData, $http, $timeout) {
	 $scope.trellisData = trellisData;
	 $scope.$watch('trellisData.changed', function(newValue, oldValue) {
        if ($scope.trellisData.changed) {
        		$scope._updateRowCol();
        		$scope.trellisData.changed = false;
        		// this is not maybe the best way, but we are in a hurry:
        		// check here: https://stackoverflow.com/questions/12304291/angularjs-how-to-run-additional-code-after-angularjs-has-rendered-a-template
        		$timeout($scope.displayPlots, 1000);
        }
     });
	 
	 $scope._rows=0;
	 $scope._cols = 0;
	 $scope.rowsArray = [];
	 $scope.colsArray = [];
	 
	 $scope._updateRowCol = function(){
		 if (trellisData.changed){
			 var rc = trellisData.selPlotsRowsCols;
			 $scope._rows = rc[0];
			 $scope._cols = rc[1];
			 $scope.rowsArray = $scope._arange($scope._rows);
			 $scope.colsArray = $scope._arange($scope._cols);
		 }
	 };
	 
	 $scope._arange = function(n){  // same as numpy arange: returns [0, 1, ... n-1]
		 // can u believe it? we didn't found a online function.So go for old school:
		 var a = [];
		 for (var i =0; i < n; i++){ a.push(i);}
		 return a;
	 };
	 
	 $scope.plotsH = function(){
		 return $scope._rows > 0 ? parseInt(100.0 / $scope._rows) : 0;
	 };
	 
	 $scope.plotsW = function(){
		 return $scope._cols > 0 ? parseInt(100.0 / $scope._cols) : 0;
	 };
	 
	 
	 $scope.displayPlots = function(){
		$scope._updateRowCol();
		var data = trellisData.selPlotsData; 
		var rows = $scope._rows;
		var cols = $scope._cols;
		// we might need to set the width / height here, very bad but there is no ng-style defined
		// for angular (FIXME: check)
		var r = 0;
		var c = 0;
		for (var i=0; i< data.length; i++){
			var id = 'trellisplot-' + r + "-" + c;
			var plotData = data[i][0];
			var plotLayout = data[i][1];
			Plotly.newPlot(id, plotData, plotLayout);
			c += 1;
			if (c==cols){
				c = 0;
				r += 1;
			}
		}
		// modifying the DOM here is not maybe the best, FIXME try to implement it in the view?
		//var parentDiv = angular.element( document.querySelector('#trellisContainer'));
		//parentDiv.empty();
	 };
}]);