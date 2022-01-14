/**
 * Implementation of from input components <base-input> and <field-input>
 * Requires Bootstrap CSS 5
 */

// Mixin used by <base-input> and <field-input> (see below)
const baseComponentMixin = {
    data: function(){
        return {
            errorColor: "#dc3545"
        }
    },
    methods: {
        createData(attrs, choices, value){
            // Complete the Object of HTML attributes `attrs` with missing values
            // inferred from `choices` (Array) and value (String, Boolean, Number)

            // copy attrs Object:
            var attrs = Object.assign({}, attrs);

            // Detect if the input is a <select> and add the `multiple` attr if needed:
            var isSelect = (attrs.type === 'select') || (Array.isArray(choices) && !!choices.length);
            var isSelectMultiple = false;
            if (isSelect && Array.isArray(value)){
                attrs.multiple = true;
                isSelectMultiple = true;
            }

            // infer attributes `type` and `step` if needed:
            if (!attrs.type && !isSelect){
                if  (typeof value === 'boolean'){
                    attrs.type = 'checkbox';
                }else if (typeof value === 'number'){
                    attrs.type = 'number';
                    attrs.step || (attrs.step = 'any');
                }else{
                    attrs.type = 'text';
                }
            }else if (isSelect){
                delete attrs.type;
            }

            // create an auto id if needed:
            if (!attrs.id){
                var rnd = Date.now() + Math.random()*1e12;
                attrs.id = `${isSelect ? 'select' : attrs.type}_${rnd}`;
            }
            var isBool = ['radio', 'checkbox'].includes((attrs.type || "").toLowerCase());
            return {
                mainComponentClasses: isBool ? '' : 'form-control',
                isSelect: isSelect,
                isSelectMultiple: isSelectMultiple,
                isBool:  isBool,
                attrs: attrs
            }
        }
    }
};

/**
* Base IO HTML component, wraps a <select> or <input> based on the properties passed,
* optionally placing a <label> before it
*
* Example
* -------
*
* <base-input v-model=... :choices=... :error=... :disabled=... ...attrs...>label</base-input>
*
* Notes
* -----
*
* `attrs` collects any non-prop attribute (NPA), i.e. normal HTML attribute such as
* "placeholder", "min", "max" , "size". NPA are not reactive: the HTML component
* will not react to changes of the bound variable. NPA will affect the inner <select>
* or <input> component, not the root element (a wrapping <div>). A special NPA is `type`
* because it dictates the type of component: if 'text', 'number', 'checkbox' it creates
* an <input> of the given type, if 'select', it will create a <select> element. If
* `type` is missing the component is inferred from the data passed to `:choices` and
* `v-model`. The label is optional: leave the inner HTML empty for "no label"
*
* Parameters
* ----------
*
* choices: Array of <option>s for a <select> component (default: []). If given, and no
*   `type` attribute is specified, a <select> is used. Each option can be  1) JS object
*   with a mandatory key 'value' and the optional keys 'innerHtml' (default:
*   `value.toString()`), 'disabled' (default: false), 'style' (default: ""), 'class'
*   (default: ""), 2) the Array [value, innerHTML, disabled, class, style], or
*   3) a string denoting both the option value and innerHTML
* v-model: sets the two way binding from the <input> or <select> value. It is basically
*   a shorthand for :value and @input combined:
*   value: The <input> or <select> value (one-way binding)
*   @input: listens for changes in the <input> or <select> value. It is a function of
*     one argument (the new value). The argument can be accessed inline with the Vue
*     variable $event or the JS variable `arguments[0]`, e.g.: @input="my_value=$event"
* error: boolean telling if the component should be rendered in error mode. By default,
*   this sets a red border on the inner <input> or <select>
* disabled: boolean telling if the component is disabled
*/
Vue.component('base-input', {
    inheritAttrs: false,  // https://vuejs.org/v2/guide/components-props.html#Disabling-Attribute-Inheritance
    mixins: [baseComponentMixin],
    props: {
        value: {type: [String, Number, Array, Boolean]},
        error: {type: Boolean, default: false},
        choices: {type:Array, default: () => ([])},  // defaults to empty Array
        disabled: {type: Boolean, default: false},
        // custom <input>/<select> component css style. In Vue3, 'style' would be enough:
        cstyle: {type: String, default: ""}
    },
    data: function () {
        // Complete the HTML attributes of this component with values that can
        // be inferred if missing:
        const data = this.createData(this.$attrs, this.choices, this.value);

        // setup the style classes:
        var cls = {
            label: 'text-nowrap me-1',
            rootDiv: 'd-flex flex-row align-items-baseline'
        };
        hasLabel = !!this.$slots.default || !!this.$scopedSlots.default;
        // change some classes according to current configuration:
        if (!hasLabel){
            cls.rootDiv = '';
        }else if(data.isSelectMultiple ||
                 (data.isSelect && parseInt(data.attrs.size || 1) > 1)){
            // two rows layout (label above component):
            cls.rootDiv = 'text-nowrap';
            cls.label = 'text-nowrap mb-1';
        }else if (data.isBool){
            cls.rootDiv = 'text-nowrap';
            cls.label = 'text-nowrap';
        }

        return Object.assign({
            hasLabel: hasLabel,
            cls: cls,
            options: [],  // will be set in watch.choices (because immediate=true)
        }, data);
    },
    watch: {
        // Whenever the choices change (including nested element), update options:
        choices: {
            deep: true,
            immediate: true,
            handler(newArray) {
                this.options = this.makeOptions(newArray);
                // if some element is disabled, scroll to top. Note that some
                // browsers (e.g. Firefox) seem to scroll to the first selected
                if (this.isSelect && this.attrs.multiple && this.options.some(elm => elm.disabled)){
                    this.scrollSelectToTop();
                }
            }
        }
    },
    computed: {
        mainComponentStyle: function(){
            var style = this.cstyle;
            if (!!this.error){
                var errc = `border-color: ${this.errorColor} !important`;
                style += `${style.trim().slice(-1) != ';' ? ';' : ''}${errc};`
            }
            return style;
        },
        val: {  // https://stackoverflow.com/questions/47311936/v-model-and-child-components
            get() {
                return this.value;
            },
            set(value) {
                this.$emit('input', value);
            }
        }
    },
    template: `<div :class="cls.rootDiv">
        <input v-if="isBool" v-model="val" v-bind="attrs" :disabled='disabled'
               :class="mainComponentClasses" :style="mainComponentStyle">
        <label v-if="hasLabel" :for="attrs.id" :disabled='disabled' :class="cls.label">
            <slot></slot>
        </label>
        <select v-if="isSelect" v-model="val" v-bind="attrs" :disabled='disabled'
                :class="mainComponentClasses" :style="mainComponentStyle" ref='selectComponent'>
	        <option	v-for='opt in options' :value="opt.value" :disabled="opt.disabled"
	                :class="opt.class" :style="opt.style" v-html="opt.innerHTML">
	        </option>
	    </select>
	    <input v-else-if="!isBool"  v-model="val" v-bind="attrs" :disabled='disabled'
	           :class="mainComponentClasses" :style="mainComponentStyle">
        </div>`,
    methods: {
        makeOptions: function(choices) {
            // convert the `choices` prop to an Array of options (JS Objects):
            return choices.map(elm => {
                var [cls, style, disabled] = ["", "", false];
                if (!Array.isArray(elm)){
                    if ((typeof elm === "object") && ('value' in elm)){
                        elm.innerHTML || (elm.innerHTML = elm.value.toString());
                        elm.class || (elm.class = cls);
                        elm.style || (elm.style = style);
                        elm.disabled || (elm.disabled = disabled);
                        return elm;
                    }
                    return {
                        value: elm,
                        innerHTML: elm.toString(),
                        class: cls,
                        style: style,
                        disabled: disabled
                    };
                }
                return {
                    value: elm[0],
                    innerHTML: elm[1] || elm[0].toString(),
                    disabled: elm[2] || disabled,
                    class: elm[3] || cls,
                    style: elm[4] || style
                }
            });
        },
        scrollSelectToTop(){
            var selComp = this.$refs.selectComponent;
            this.$nextTick(() => {
                selComp.scrollTop = 0;
            });
        }
    }
});

/**
* <base-input> representing a Django Form Field, i.e.. a JavaScript Object where
* keys denote the HTML attribute of the internal component Cmp (<input> or
* <select>), with the
* exception of these reactive or special keys:
* value: the field <-> Cmp value
* error: field validation error message (from server)
* help: the help text
* choices: the options Array, if Cmp should be represented by a <select>
* disabled: the state (enabled/disabled) of Cmp
* label: the text of the label before Cmp
*/
Vue.component('field-input', {
    inheritAttrs: false,  // https://vuejs.org/v2/guide/components-props.html#Disabling-Attribute-Inheritance
    mixins: [baseComponentMixin],
    //https://vuejs.org/v2/guide/components-props.html#Prop-Types:
    props: {
        field: {type: Object},
    },
    data: function () {
        var field = this.field;
        // copy all non-props attributes (non reactive) from field to attrs:
        var attrs = {};
        var reactiveKeys = ['help', 'choices', 'error', 'value', 'disabled', 'label',
                            'cstyle'];
        Object.keys(field).map(key => {
            if (!reactiveKeys.includes(key)){
                attrs[key] = field[key];
            }
        });
        // Complete attrs with non-prop attributes passed directly on the component
        // ($attrs) from the parent, and other attrs that can be inferred if missing:
        attrs = Object.assign(attrs, this.$attrs);
        // return the `data` Object
        data = this.createData(attrs, field.choices, field.value);
        data.showSelectedInfo = data.isSelectMultiple && field.choices.length > 10;
        return data;
    },
    computed: {
        infoMessageStyle(){
            var color = !!this.field.error ? `color: ${this.errorColor} !important` : "";
            return 'flex: 1 1 auto;' + color;
        },
    },
    template: `<div>
        <div class="d-flex flex-row mb-0 align-items-baseline">
            <base-input v-if="isBool" v-model="field.value" :error="!!field.error"
                        v-bind="attrs" :choices="field.choices" :cstyle="field.cstyle"
                        :disabled='field.disabled' class='me-1'>
                <span v-html="field.label"></span>
            </base-input>
            <label v-else :for="attrs.id" class='mb-1 text-nowrap'
                          :disabled='field.disabled' v-html="field.label">
            </label>
            <span class="small ms-2 text-muted text-nowrap" :style="infoMessageStyle">
                <template v-if="!!field.error">
                    <span v-html="field.error"></span>
                </template>
                <template v-else>
                    <span v-if="field.help" v-html="field.help"></span>
                    <span v-if="field.help && showSelectedInfo"> | </span>
                    <span v-if="showSelectedInfo"
                          v-html="selectedInfoMsg()"></span>
                    <i v-if="showSelectedInfo && field.value.length"
                       @click="field.value=[]" class="fa fa-times-circle"
                       style="cursor: pointer;" title="Clear selection"></i>
                </template>
            </span>
            <span class='text-primary small ms-3 text-right'>{{ attrs.name }}</span>
        </div>
        <base-input v-if="!isBool" v-model="field.value" :error="!!field.error"
                v-bind="attrs" :choices="field.choices" :cstyle="field.cstyle"
                :disabled='field.disabled' style='flex: 1 1 auto'>
        </base-input>
    </div>`,
    methods: {
        selectedInfoMsg(){
            // for select[multiple], return the string with the number of selected items
            var field = this.field;
            var count = field.choices.filter(e => !e.disabled).length;
            var sel = field.value.length || 0;
            return `${count} total, ${sel} selected`;
        },
    }
});