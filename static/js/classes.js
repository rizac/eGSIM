/**
 * classes definitions (ES6 OOP)
 */
class SelArray extends Array {
    /**
     * JS Array subclass implementing a selected item (and selected index), assignable via
     * getter setter. This class is useful when implementing menus/lists in angularjs where we want to
     * store the 'active' or 'selected' item.
     * 
     * Examples:
     * 
     * var a = new SelArray(1,2,True,'4') // new SelArray() for empty Array
     * a.selIndex()  // -1 means: no selection
     * a.setSelIndex('4')
     * a.selIndex()  // returns 3
     * //usual operations on Arrays:
     * a.slice
     * ...
     */
    constructor(...args) { 
        super(...args);
        var _selIndex = -1;
        this.selection = function(index){
           /**
            * Root function to get/set selection. Compatible with angularjs ngmodel and getter/setter, e.g.:
            * <select ng-model="selarray.selection" ng-model-options="{ getterSetter: true }"
            *    ng-options="index as selarray[index] for index in selarray">
            * 
            * Without arguments, returns the currently selected index. With an argument (integer)
            * sets the selected index
            * For info see: https://docs.angularjs.org/api/ng/directive/ngModel
            */
           if (arguments.length){
               _selIndex = index;
               return this;
           }else{
               if (_selIndex < 0 || _selIndex >= this.length){
                   return -1;
               }
               return _selIndex;
           }
        }
        this.clearSelection();
    }
    clear(){ //overrides Array.clear. Calls super and clear selection
        super.clear();
        return this.clearSelection();
    }
    clearSelection(){ //clears selection (sets selected index = -1)
        return this.selection(-1);
    }
    select(index){ //aka selection(index), more explanatory than the latter
        return this.selection(index);
    }
    get selIndex() {  // getter for the selected index: var index = selArray.selIndex (-1 if no selection, or a value < this.length)
        return this.selection();
    }
    set selIndex(index) {  // setter for the selected index: selArray.selIndex = index. Same as this.select(index)
        this.selection(index);
    }
    get selHasNext(){
        var sindex = this.selIndex;
        return sindex >=0 && sindex < this.length -1;
    }
    get selHasPrev(){
        return this.selIndex > 0;
    }
    selNext(){
        if (this.selHasNext){
            this.selIndex += 1;
        } 
    }
    selPrev(){
        if (this.selHasPrev){
            this.selIndex -= 1; 
        }
    }
}


class SelSet extends Set {
    /**
     * JS Set subclass implementing a selectedItem (and selectedIndex).
     * Currently the selected index is not updating when the Array is modified,
     * the user has to care about that
     * 
     * Examples:
     * 
     * var a = new MultiselSet([1,2,True,'4'])  // empty: new MultiselSet()
     * a.selItems()  // -1 means: no selection
     * a.setSelItems('4')
     * a.selItems()  // returns [4]
     * //usual operations on Arrays:
     * a.values()
     * ...
     */
    constructor(...args) { 
        super(...args);
        var _selItem = undefined;
        this.selection = function(item){
           /**
            * Root function to get/set selection. Compatible with angularjs ngmodel and getter/setter, e.g.:
            * <select ng-model="selarray.selection" ng-model-options="{ getterSetter: true }"
            *    ng-options="value as selarray[index] for index in selarray">
            * 
            * Without arguments, returns the currently selected index. With an argument (integer)
            * sets the selected index
            * For info see: https://docs.angularjs.org/api/ng/directive/ngModel
            */
           if (arguments.length){
               _selItem = item;
               return this;
           }else{
               return this.has(_selItem) ? _selItem : undefined;
           }
        }
        this.clearSelection();
    }
    clear(){
        super.clear();
        this.clearSelection();
    }
    clearSelection(){
        this.selection(undefined);
    }
    select(item){
        return this.selection(item);
    }
    get selItem(){  // returns an Array instead of an iterator for angular compatibility
        return this.selection();
    }
    set selItem(item){
        this.selection(item);
    }
}


class SelMap extends Map {
    /**
     * JS (ES6) Map subclass implementing a selected key.
     * Currently the selected key is not updating when the Map is modified,
     * the user has to care about that
     * 
     * Examples:
     * 
     * var a = new SelMap([['key1', 5], ['key2', 'a'])  // SelMap() for empty Map
     * a.selKey()  // return undefined (no selection)
     * a.setSelKey('key1')
     * a.selKey() // returns 'key1'
     * // usual operations on map:
     * a.get('key1')
     * ...
     */
    constructor(...args) { 
        super(...args); 
        var _selKey = undefined;
        this.selection = function(key){
            /**
             * Root function to get/set selection. Compatible with angularjs ngmodel and getter/setter, e.g.:
             * <select ng-model="selarray.selection" ng-model-options="{ getterSetter: true }"
             *    ng-options="value as selarray[index] for index in selarray">
             * 
             * Without arguments, returns the currently selected index. With an argument (integer)
             * sets the selected index
             * For info see: https://docs.angularjs.org/api/ng/directive/ngModel
             */
            if (arguments.length){
                _selKey = key;
                return this;
            }else{
                return this.has(_selKey) ? _selKey : undefined;
            }
        }
        this.clearSelection();
    }
    clear(){
        super.clear();
        this.clearSelection();
    }
    clearSelection(){
        this.selection(undefined);
    }
    select(key){
        return this.selection(key);
    }
    get selKey(){ 
        return this.selection();
    }
    set selKey(key){
        this.selection(key);
    }
}

