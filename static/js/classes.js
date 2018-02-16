/**
 * classes definitions (ES6 OOP) mapping view iterables (Array, Set, Map) with a selection attribute
 */

class ArraySet extends Set{
    /** Set subclass implementing the asArray and toggle methods **/
    get asArray(){ /* convert me as array */
        return Array.from(this);
    }
    toggle(item){ /* add item if not in this Set, remove it otherwise */
        if (this.has(item)){
            return this.delete(item);
        }
        return this.add(item);
    }
}


class SelArray extends Array {
    /**
     * JS Array with an optional selected index  accessible/settable via `this.selection`.
     * `this.selection` is an integer lower than this Array length which, when -1 (the default) indicates no index selected
     * This Array is intended to be immutable: adding removing elements
     * to this object does not update the selected index. Such  a functionality is not needed by the program
     * and there would be too many methods to override in any case.
     */
    constructor(...args) { 
        super(...args);
        this.selection = this.defaultSelection;
    }
    clear(){ //overrides Array.clear. Calls super and clear selection
        super.clear();
        this.selection = this.defaultSelection;
    }
    get defaultSelection(){
        return -1;
    }
}


class SelSet extends ArraySet {
    /**
     * JS Set with an optional selected element accessible/settable via `this.selection`.
     * `this.selection` is an element of this set which, when undefined (the default) indicates no element selected.
     * For applications requiring arrays (e.g. angular 1x) use `this.asArray`
     */
    constructor(...args) { 
        super(...args);
        this.selection = this.defaultSelection;
    }
    clear(){
        super.clear();
        this.selection = this.defaultSelection;
    }
    delete(item){
        var ret = super.delete(item);
        if(ret && (item === this.selection)){
            this.selection = this.defaultSelection;
        }
        return ret;
    }
    get defaultSelection(){
        return undefined;
    }
}

class MultiselSet extends SelSet {
    /**
     * JS Set with optional selected elements accessible/settable via `this.selection`.
     * `this.selection` is a Set which, when empty (the default) indicates no element selected.
     * For applications requiring arrays (e.g. angular 1x) use `this.asArray` or `this.selection.asArray`
     */
    delete(item){
        var ret = super.delete(item);
        if (ret && this.selection.has(item)){
            this.selection.delete(item);
        }
        return ret;
    }
    get defaultSelection(){
        return new ArraySet();
    }
}


class SelMap extends Map {
    /**
     * JS Map with an optional selected key accessible/settable via `this.selection`.
     * `this.selection` is an key of this map which, when undefined (the default) indicates no key selected.
     * For applications requiring arrays (e.g. angular 1x) use `this.asArray` which returns this.keys() converted to Array.
     */
    constructor(...args) { 
        super(...args); 
        this.selection = this.defaultSelection;
    }
    clear(){
        super.clear();
        this.selection = this.defaultSelection;
    }
    delete(key){
        var ret = super.delete(key);
        if(ret && (key === this.selection)){
            this.selection = this.defaultSelection;
        }
        return ret;
    }
    get asArray(){
        return Array.from(this.keys());
    }
    get defaultSelection(){
        return undefined;
    }
}

class MultiselMap extends SelMap {
    /**
     * JS Map with optional selected keys accessible/settable via `this.selection`.
     * `this.selection` is a Set which, when empty (the default) indicates no key selected.
     * For applications requiring arrays (e.g. angular 1x) use `this.asArray` which returns this.keys() converted to Array,
     * or `this.selection.asArray`
     */
    delete(key){
        var ret = super.delete(key);
        if (ret && this.selection.has(key)){
            this.selection.delete(key);
        }
        return ret;
    }
    get defaultSelection(){
        return new ArraySet();
    }
}