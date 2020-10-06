/**
 * Registers globally a Vue component. The name of the component
 * (first argument of 'Vue.component' below must be equal to this file's name 
 * (without extension)
 */
Vue.component('imprint', {
    props: {
    	src: {String, default: 'imprint.html'},
    	id: {String, default: '__imprint__iframe__'},
    	fragment: {String, default: ''}
    },
    template: `<iframe :id='id' class='flexible' :src='src + fragment'></iframe>`
})