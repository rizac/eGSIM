/* form input components (<input>, <select>) */

/*
Base input or select component (depending on props). Usage:
<base-input v-model=... :choices=... :error=... :disabled=... />
*/
Vue.component('base-input', {
    props: {
        value: {type: [String, Number, Array, Boolean]},
        error: {type: Boolean, default: false},
        choices: {type:Array, default: () => ([])},  // defaults to empty Array
        disabled: {type: Boolean, default: false},
    },
    data: function () {
        return {
            errorColor: "#dc3545",
            options: [],  // will be set in watch.choices (because immediate=true)
        }
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
                if (this.isSelect && this.$attrs.multiple && this.options.some(elm => elm.disabled)){
                    this.scrollSelectToTop();
                }
            }
        }
    },
    emits: ['update:modelValue'],  // Vue3 necessary?
    computed: {
        val: {  // https://stackoverflow.com/questions/47311936/v-model-and-child-components
            get() {
                // this.modelValue === undefined -> Vue2, otherwise Vue3
                return this.modelValue === undefined ? this.value : this.modelValue;
            },
            set(value) {
                if (this.modelValue === undefined){  // Vue2
                    this.$emit('input', value);
                }else{  // Vue3
                    this.$emit('update:modelValue', value);
                }
            }
        },
        cssstyle(){
            var style = [];
            if (!!this.error){
                style.push(`border-color: ${this.errorColor} !important`);
            }
            return style.join(';');
        },
        isSelect(){
            return this.$attrs.type === 'select' ||  this.choices.length > 0;
        },
        isBool(){
            return this.$attrs.type == 'checkbox';
        }
    },
    template: `<input v-if="isBool" v-model="val" :disabled='disabled'>
        <select v-else-if="isSelect" v-model="val" :disabled='disabled' class='form-control'
               :style="cssstyle" ref='selectComponent'>
            <option	v-for='opt in options' :value="opt.value" :disabled="opt.disabled"
                    :class="opt.class" :style="opt.style" v-html="opt.innerHTML">
            </option>
        </select>
        <input v-else v-model="val" :disabled='disabled' class='form-control' :style="cssstyle">`,
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
                setTimeout(() => {selComp.scrollTop = 0;}, 50);
            });
        }
    }
});

/** A <base-input> that accepts a single prop as Field (Object) */
Vue.component('field-input', {
    props: {
        field: {type: Object},
    },
    computed: {
        attrz(){  // merge passed attrs ($attrs) with this Field attrs
            var attrs = Object.assign({}, this.$attrs);  // Object.assign(target, ...sources)
            var reactiveKeys = ['value', 'error',  'choices', 'disabled'];
            var field = this.field;
            Object.keys(field).map(key => {
                if (!reactiveKeys.includes(key)){
                    attrs[key] = field[key];
                }
            });
            return attrs;
        }
    },
    template: `<base-input v-model="field.value" :error="!!field.error"
                :choices="field.choices" :disabled='field.disabled'
                v-bind="attrz" />`
});

/** Field label */
Vue.component('field-label', {
    props: {
        field: {type: Object},
    },
    data: function () {
        return {
            errorColor: "#dc3545",
            showSelectedInfo: this.field.multiple && this.field.choices.length > 10
        }
    },
    computed: {
        infoMessageStyle(){
            var color = !!this.field.error ? `color: ${this.errorColor} !important` : "";
            return 'flex: 1 1 auto;' + color;
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
            <span class="small ml-2 text-muted text-nowrap" :style="infoMessageStyle">
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
            <span class='text-primary small ml-3 text-right'>{{ field.name }}</span>
        </div>`
});