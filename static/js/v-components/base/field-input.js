/* form input components (<input>, <select>) */

/*
Base input or select component (depending on props). Usage:
<base-input v-model=... :choices=... :error=... :disabled=... />
*/
EGSIM.component('base-input', {
    props: {
        value: {type: [String, Number, Array, Boolean]},
        error: {type: Boolean, default: false},
        choices: {type:Array, default: () => ([])},  // defaults to empty Array
        disabled: {type: Boolean, default: false},
    },
    data () {
        var val = Vue.toRaw(this.value);
        var isSelect = Vue.toRaw(this.choices || []).length > 0;
        var isBool = !isSelect && (typeof val === 'boolean');
        var isNum = !isSelect && (typeof val === 'number');
        return {
            isSelect: isSelect,
            isBool: isBool,
            isNum: isNum,
            val: val,  // this is the proxy to value
            options: [],  // will be set in watch.choices (because immediate=true),
        }
    },
    emits: ['value-changed'],
    watch: {
        val: function(newVal, oldVal){
            this.$emit('value-changed', newVal);  // val changed, emit a value-changed
        },
        // Whenever the choices change (including nested element), update options:
        choices: {
            deep: true,
            immediate: true,
            handler(newArray) {
                this.options = this.makeOptions(newArray);
                // if some element is disabled, scroll to top. Note that some
                // browsers (e.g. Firefox) seem to scroll to the first selected
                if (this.isSelect && this.$attrs.multiple && this.options.some(elm => elm.disabled)){
                    this.scrollSelectToTop();
                }
            }
        }
    },
    computed: {
        cssClass(){
            return this.isBool ? "" : (!!this.error ? "form-control border-danger" : "form-control");
        }
    },
    template: `<select v-if="isSelect" v-model="val" :disabled='disabled'
                       :class='cssClass' ref='selectComponent'>
            <option	v-for='opt in options' :value="opt.value" :disabled="opt.disabled"
                    :class="opt.class" :style="opt.style" v-html="opt.innerHTML">
            </option>
        </select>
        <input v-else :type="isBool ? 'checkbox' : (isNum ? 'number' : 'text')"
               v-model="val" :disabled='disabled' :class="cssClass" />`,
    methods: {
        makeOptions(choices) {
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
                setTimeout(() => {selComp.scrollTop = 0;}, 50);
            });
        }
    }
});

/** A <base-input> that accepts a single prop as Field (Object) */
EGSIM.component('field-input', {
    props: {
        field: {type: Object},
    },
    computed: {
        attrz(){  // merge passed non-reactive attrs ($attrs) with this Field attrs
            var attrs = Object.assign({}, this.$attrs);  // Object.assign(target, ...sources)
            var reactiveKeys = ['value', 'error',  'choices', 'disabled', 'help', 'label', 'type'];
            var field = this.field;
            Object.keys(field).map(key => {
                if (!reactiveKeys.includes(key)){
                    attrs[key] = field[key];
                }
            });
            return attrs;
        }
    },
    template: `<base-input :value="field.value"
                           @value-changed="(value) => {field.value = value;}"
                           :error="!!field.error"
                           :choices="field.choices" :disabled='field.disabled'
                           v-bind="attrz" />`
});

/** Field label */
EGSIM.component('field-label', {
    props: {
        field: {type: Object},
    },
    data() {
        return {
            showSelectedInfo: this.field.multiple && this.field.choices.length > 10
        }
    },
    computed: {
        infoMessageClass(){
            var cls = "small ms-2 text-nowrap ";
            return cls + (!!this.field.error ? 'text-danger' : ' text-muted');
        },
        selectedInfoMsg(){
            // for select[multiple], return the string with the number of selected items
            var count = this.field.choices.filter(e => !e.disabled).length; // FIXME choices!
            var sel = this.field.value.length || 0;
            return `${count} total, ${sel} selected`;
        }
    },
    template: `<div class="d-flex flex-row m-0 align-items-baseline">
            <label class='m-0 text-nowrap' :disabled='field.disabled' v-html="field.label" />
            <span :class="infoMessageClass" style="flex: 1 1 auto;">
                <template v-if="!!field.error">
                    <span v-html="field.error"/>
                </template>
                <template v-else>
                    <span v-if="field.help" v-html="field.help"></span>
                    <span v-if="field.help && showSelectedInfo"> | </span>
                    <span v-if="showSelectedInfo"
                          v-html="selectedInfoMsg"></span>
                    <i v-if="showSelectedInfo && field.value.length"
                       @click="field.value=[]" class="fa fa-times-circle"
                       style="cursor: pointer;" title="Clear selection"></i>
                </template>
            </span>
            <span class='text-primary small ms-3 text-right'>{{ field.name }}</span>
        </div>`
});