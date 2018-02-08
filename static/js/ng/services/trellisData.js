/**
 * Implements the input selection to be shared across all controllers
 */

// difference between factory and .service: https://blog.thoughtram.io/angular/2015/07/07/service-vs-factory-once-and-for-all.html
ngApp.service('trellisData', function () {
	
	// sort of private variables:
	var _files = new SelMap();
	var _changed = false;

	return {

		init(data) {
			_files.clear();
			var keys = Object.keys(data);
			keys.forEach(function(name){
				_files.set(name, data[name]);
			});
			if (keys.length){
				_files.selKey = keys[0];
			}
			_changed=true;
		},
		
		get fileNames(){
			return Array.from(_files.keys());
		},
		
		get selFileName(){
			return _files.selKey; // ._selKey is a Set, its name overrides super-class (SelMap)
		},
		
		get selData() {
		    return _files.get(this.selFileName);
		}
	}
});