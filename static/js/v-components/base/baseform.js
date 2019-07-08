/**
 * Represents a base form used in trellis, residuals, testing
 */
var _BASE_FORM = Vue.component('baseform', {
    props: {
        form: Object,
        url: String,
        post: Function,
        // urls properties are passed to the downloadselect for downloading the request:
        urls: {type: Object, default: () => {return {}}}
    },
    data: function () {
    	return {
        	responseDataEmpty: true,
            responseData: {},
            mounted: false,
        }
    },
    methods: {
        request: function(){
            var form = this.form;
            this.post(this.url, form).then(response => {
                if (response && response.data){
                    this.responseData = response.data;
                } 
            });
        },
        resetDefaults: function(){
        	for (var key of Object.keys(this.form)){
        		if (this.form[key].initial !== undefined){
    				this.form[key].val = this.form[key].initial;
    			}
    		}
        }
    },
    mounted: function () {
    	// set the mounted variable in order to activate the transition after the
    	// whole component has been mounted
    	// the transition is used just to show up / hide the form
    	if (this.mounted){
    		return;
    	}
  		this.$nextTick(function () {
    		// Code that will run only after the
    		// entire view has been rendered
    		this.mounted = true;
  		})
	},
    watch: {
        responseData: {
            immediate: true, // https://forum.vuejs.org/t/watchers-not-triggered-on-initialization/12475
            handler: function(newVal, oldVal){
                this.responseDataEmpty = Vue.isEmpty(newVal); // defined in vueutil.js
                if (!this.responseDataEmpty){
                	this.$emit('responsereceived', newVal);
                }
            }
        }
    },
    computed: {
    	formObject: function(){
    		// returns a javascript object with keys mapped to each form element value
    		var data = {};
    		for (var key of Object.keys(this.form)){
    			data[key] = this.form[key].val;
    		}
    		return data;
    	}	
    },
    template: `
	<transition :name="mounted ? 'egsimform' : ''">
    <form novalidate v-on:submit.prevent="request"
        :class="[responseDataEmpty ? '' : ['shadow', 'border', 'bg-light']]"
        class='d-flex flex-column flexible position-relative mb-3 align-self-center' style='z-index:10'
    >    
        <div class="d-flex flex-column flexible" :class="[responseDataEmpty ? '' : ['mx-4', 'mt-4', 'mb-3']]">
            <div class="d-flex flexible flex-row mb-3">
                <div class="d-flex flexible flex-column">
                    <gsimselect :form="form" showfilter class="flexible" />
                </div>
                <slot/> <!-- << HERE CUSTOM FORM ELEMENTS IN CHILD COMPONENTS -->
            </div>
        
			<div class='d-flex flex-row justify-content-center border-top pt-3'>
				<downloadselect
					:urls="urls.downloadRequest"
					:post="post"
					:data="formObject"
				/>
	            <button type="submit" class="btn btn-primary ml-2">
	                <i class="fa fa-play"></i> Display plots
	            </button>
	            <button type="button"
	            	@click='resetDefaults'
	            	class="btn btn-outline-secondary ml-2"
	            >
	                <i class="fa fa-fast-backward"></i> Reset defaults
	            </button>
	            <button type="button"
	            	v-show='!responseDataEmpty'
	            	@click='$emit("closebuttonclicked")'
	            	class="btn btn-outline-secondary ml-2"
	            >
	                <i class="fa fa-times"></i> Close
	            </button>
            </div>
        </div>
    </form>
	</transition>`
})