/**
 * Implements the input selection to be shared across all controllers
 */

// difference between factory and .service: https://blog.thoughtram.io/angular/2015/07/07/service-vs-factory-once-and-for-all.html
ngApp.service('inputSelection', function () {
	
	// sort of private variables:
	var _avalGsims = new Map();
	var _gsims = new Set();
	var _avalImts = new SelSet();  // will be used as single selection set
	var _selectableImts = new Set();

	return {

		init(avalGsims) {
			/**
			 * Initializes a new InputSelection
			 * 
			 * :param avalGsims: an iterable (Array, Set,...) of objects. Each object is na Array
			 * 	is of the form:
			 * 		[
			 * 			gsimName (string),
			 * 		 	intensity measure types defined for the gsim (Array of String),
			 * 		 	tectonic region type defined for the gsim (String)
			 * 		]
			 */
			_avalGsims.clear();
			_avalImts.clear();
			this.clearGsims();
			for (let gsim of avalGsims) {
				var gsimName = gsim[0];
				var imts = new Set(gsim[1]);
				imts.forEach(function(elm){_avalImts.add(elm);});
				var trt = gsim[2];
				_avalGsims.set(gsimName, [imts, trt]);
			}
			return this;
		},
		
		get isValid(){
			return this.gsimsCount > 0 && this.imt && this.isImtSelectable(this.imt); // ._selKey is a Set, its name overrides super-class (SelMap)
		},
		
		get gsims() {
		    return Array.from(_gsims);
		},
		
		clearGsims(){
			_gsims.clear();
			_selectableImts.clear();
		},
		
		deleteGsims(gsims){
			for (let gsim of gsims){
				_gsims.delete(gsim);  //safe to delete within for of loop
			}
			this.updateSelection();
		},
		
		addGsims(gsims) {
//		    if (typeof obj[Symbol.iterator] !== 'function'){
//		    		gsims = [gsims];
//		    }
		    // update selectableImts
		    for (let gsim of gsims){
				if (_avalGsims.has(gsim)){
					_gsims.add(gsim);
				}
			}
			this.updateSelection();
		},
		
		updateSelection(){
			_selectableImts.clear();
			for (let gsim of _gsims){
				var gsimSelectableImts = _avalGsims.get(gsim)[0];
				if (_selectableImts.size == 0){  // first item added
					for (let imt of gsimSelectableImts){
						_selectableImts.add(imt);
					}
					continue;
				}
				for (let imt of _selectableImts){
					if (!gsimSelectableImts.has(imt)){
						_selectableImts.delete(imt);  // safe to delete within let of loop
					}
				}
				if (_selectableImts.size == 0){
					break;
				}
			}
		},
		
		get gsimsCount() {
			return _gsims.size;
		},
		
		get imt() {
		    return _avalImts.selItem;
		},
		
		set imt(imt) {
			_avalImts.selItem = imt;
		},
		
		isImtSelectable(imt) {
			return _selectableImts.has(imt);
		},
		
		get avalGsims() {
		    return Array.from(_avalGsims.keys());
		},
		
		get avalGsimsCount(){
			return _avalGsims.size;
		},
		
		get avalImts() {
			return Array.from(_avalImts);
		},

		matchesByName(gsimName, regexp){
			return gsimName.search(regexp) > -1;
		},

		matchesByImt(gsimName, regexp){
			var imts = _avalGsims.get(gsimName)[0];
			for (let imt of imts){
				if (imt.search(regexp) > -1){
					return true;
				}
			};
			return false;
		},

		matchesByTrt(gsimName, regexp){
			var trt = _avalGsims.get(gsimName)[1];
			return trt.search(regexp) > -1;
		},
		
		get asObj(){
			return {gsims: this.gsims, imt: this.imt}
		}
	}
});