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
        this.clearSelection();
    }
    clear(){
    		super.clear();
    		this.clearSelection();
    }
    clearSelection(){
		this._selIndex = -1;
    }
    select(item){
    		this.selItem = item;
    		return this;
    }
    get selIndex() {
    		return this._selIndex;
    }
    set selIndex(index) {
    		this._selIndex = index < 0 || index >= this.length ? -1 : 0;
    }
    get selItem() {
		return this[this._selIndex] || undefined;
    }
    set selItem(item) {
    		this.clearSelection();
    		var i =0;
    		for (let item_ of this) { // not efficient, but the only possible way ...
    			if (item_ === item){
    				this._selIndex = i;
    				break;
    			}
    			i += 1;
    		}
    }
    get selHasNext(){
    		return this._selIndex >=0 && this._selIndex < this.length -1;
    }
    get selHasPrev(){
		return this._selIndex > 0 && this._selIndex < this.length;
    }
    selNext(){
    		if (this.selHasNext){
    			this._selIndex += 1;
    		} 
    }
    selPrev(){
    		if (this.selHasPrev){
    			this._selIndex -= 1; 
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
        this.clearSelection();
	}
    clear(){
		super.clear();
		this.clearSelection();
	}
	clearSelection(){
		this._selection = undefined;
	}
    select(item){
		this.selItem = item;
		return this;
    }
    get selItem(){  // returns an Array instead of an iterator for angular compatibility
		return this._selection;
    }
    set selItem(item){
    		this._selection = this.has(item) ? item : undefined;
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
        this.clearSelection();
    }
    clear(){
    		super.clear();
    		this.clearSelection();
    }
    clearSelection(){
    		this._selection = undefined;
    }
    select(key){
		this.selKey = key;
		return this;
    }
    get selKey(){ 
		return this._selection;
	}
	set selKey(key){
		this._selection = this.has(key) ? key : undefined;
	}
}

