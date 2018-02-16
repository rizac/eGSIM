/**
 * Implements the input selection to be shared across all controllers
 */

// difference between factory and .service: https://blog.thoughtram.io/angular/2015/07/07/service-vs-factory-once-and-for-all.html
ngApp.service('gsimsInput', function () {

    return {
        gsims: new MultiselMap(),
        imts: new MultiselSet(),
        init(avalGsims) {
            /**
             * Initializes a new InputSelection
             * 
             * :param avalGsims: an iterable (Array, Set,...) of objects. Each object is na Array
             *  is an Array of the form:
             * [
             *  gsimName (string),
             *  intensity measure types defined for the gsim (Array of String),
             *  tectonic region type defined for the gsim (String)
             *  ruptureParams (array of strings? FIXME: check)
             * ]
             */
            this.gsims.clear();
            this.imts.clear();
            for (let gsim of avalGsims) {
                var gsimName = gsim[0];
                var gImts = new Set(gsim[1]);
                for (let gImt of gImts){
                    this.imts.add(gImt);
                }
                var trt = gsim[2];
                var ruptureParams = gsim[3];
                this.gsims.set(gsimName, [gImts, trt, ruptureParams]);
            }
            return this;
        },
        get isValid(){
            var val = !!(this.gsims.selection.size && this.imts.selection.size);
            if (val){
                for (let imt of this.imts.selection){
                    if (!this.isImtSelectable(imt)){
                        return false;
                    }
                }
            }
            return val;
        },
        isImtSelectable(imt) {
            for (let gsim of this.gsims.selection){
                var selectableImts = this.gsims.get(gsim)[0];
                if (!selectableImts.has(imt)){
                    return false;
                }
            }
            return true;
        },
        matchesByName(gsimName, regexp){
            return gsimName.search(regexp) > -1;
        },
        matchesByImt(gsimName, regexp){
            var imts = this.gsims.get(gsimName)[0];
            for (let imt of imts){
                if (imt.search(regexp) > -1){
                    return true;
                }
            };
            return false;
        },
        matchesByTrt(gsimName, regexp){
            var trt = this.gsims.get(gsimName)[1];
            return trt.search(regexp) > -1;
        },
//        get ruptureParams(){
//            var _ruptureParams = new Set();
//            for (let gsimName of _gsims){
//                var rParams = this.gsims.get(gsimName)[2];
//                for (let rParam of rParams){
//                    _ruptureParams.add(rParam);  //PS: safe to delete within for of loop
//                }
//            }
//            return _ruptureParams;
//        }
    }
});