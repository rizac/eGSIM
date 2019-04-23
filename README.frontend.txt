Front-end TUTORIAL for DEVELOPERS:
==================================

Our frontend (client-side application) uses Vuejs. The reason is that as of
2018 it is the best framework giving model-view bindings and other facilities
*without* forcing us to over eingeneering our app
(Want a hint about web develompment histeria?
https://www.planningforaliens.com/blog/2016/04/11/why-js-development-is-crazy/).

Vue defines "instances" and "components". Technically, they are both JsavaScript
Objects. However, an instance is the "root" Object, whereas Components are a way
of defining custom HTML components and are sort of "children" of the instance.

So, in the practice: egsim.html is the root page of our program (single
page application). Therein:

<div ... id='egsim-vue'>

is the HTML "root" component associated with our Vue instance. The Vue instance
is declared at the end of the page:

var EGSIM = new Vue({
	    el: '#egsim-vue',
	    mixins: [EGSIM_BASE],  /* defined in script above */
	    data: ...

Note the properties:

el: '#egsim-vue'

maps the instance to the given <div>.

data: ...

initializes the Vue instance with data injected in the 
HTML from the server via Django templating system. Our Vue instance is
nothing more than an Object initialized. Where are the "core" method of the
instance? It turns out that the Vue instance "inherits" from an Object
called EGSIM_BASE:

mixins: [EGSIM_BASE]

defined in

egsim_base.js

EGSIM_BASE defines not only the initialization functions for our Vue instance
(function 'created' in egsim_base.js) but also several common procedures which
can be called by the Vue components later: for instance it implements a "post"
function which issues a POST request, takes care of showing a waitbar and sets
up the error code, or returns the data.


TABS MENUS in egsim.html
------------------------

In egsim.html, inside <div ... id='egsim-vue'> we first create the navigation
bar. Each tab is created with a for-loop from the server via Django.
The most important point is the event associated when a tab is clicked:

@click="setComponent('{{ component.0 }}')"

{{ component.0 }} is the first item of a list passed by Django, where each tab
is associated to a list of three elements: [key, label, icon].
"setComponent" is thus called with the value of the key (the function
is defined in egsim_base.js and does nothing more than assigning the Vue
selected component, and optionally changes the URL).

Now, IMPORTANT: the key described above is FUNDAMENTAL to recognize what
component to be set as active. Therefore, it should be consistently the same on
the server side and in the Vue component creation, WHICH MUST BE DEFINED IN A
JavaScript file with the name [key].js.

Example, the trellis plots. The menu is injected in the page from Django as
['trellis', 'Trellis plots', whatever_icon]

The key is thus 'trellis'. This means there must be a javascript file called

trellis.js

in the "components" (or "comps") subdirectory of Js files, where we create a
VueJs component called 'trellis':

Vue.component('trellis', { ... })

The lines of code importing trellis.js are defined near the end of
egsim.html:

{% for component in components %}
	<script type='text/javascript' src = "{% static 'js/comps/' %}{{ component.0 }}.js"></script>
{% endfor %}

(in our basic project made of classical javascript imports via <script> tag,
remember to import FIRST the components js files and as last the instance js file)


Components
----------

The tabs above set the selected component into the Vue instance. The Vue instance
variable change accordingly, but where is the binding which forces updates in the HTML?
At the end of egsim.html where we define our "keep alive" <component>:

<keep-alive>
	<component v-bind:is="selComponent"
		v-bind="selComponentProps" v-bind:post='post'
		@gsim-selected='selectGsims'
		@movetoapidoc='moveToApidoc'>
	</component>
</keep-alive>

The <component> tag is a way to say: here
there is a component which is 'selComponent', and everytime we change the latter
change also the component here, and viceversa. The keep-alive is just a wrapper
Vue uses in order to say that when deactivated, the component data must still
be alive. The binding component key <-> Vue component is done via the attribute:

v-bind:is="selComponent"

The <component> has also two data bindings i.e. data that is passed from the Vue
instance into the Vue component:

v-bind="selComponentProps" v-bind:post='post'

and two event listeners:

@gsim-selected='selectGsims' @movetoapidoc='moveToApidoc'

Let's see these in details:


Binding component properties
++++++++++++++++++++++++++++

v-bind="selComponentProps"

the selComponentProps is a computed property defined in egsim_base.js: It is
basically a dict of keys mapped to some component values, and are passed from
the server. Look at egsim.html
where we initialize the Vue instance, and its property 'data' (this was obtained
by inspecting the source in a browser):

data: function(){
	return {selComponent: "home",
		errormsg: "",
		initdata: {"component_props": {"home": {"src": "pages/home"},
									   "gsims": {"tr_models_url": "data/tr_models",
									   			 "url": "query/gsims",
									   			 "form": {"gsim": {"help": "",
									   			                   "label": "Ground Shaking Intensity Model(s)",
									   			                   "attrs": {"multiple": "multiple",
									   			                             "required": false,
									   			                             "id": "id_gsim",
									   			                             "name": "gsim"},
									   			                   "err": "",
									   			                   "is_hidden": false,
									   			                   "val": null,
									   			                   "choices": []
									   			                   },
									   			          }
									   			} ... ]]}
	};
}

It is that `initdata.component_props` that holds all the data injected from the
server into Vuejs components. The main Vue instance converts each key into the component
'componentProps' and then, when a user clicks on a tab, the 'componentProps'
updates automatically (by definition of a Vuejs computed property) and the
properties are passed to the given component.

With that in mind, any component in "components" should then define a 'props'
attribute consistent with its component_props implemented server-side.
For instance, look at how we define home.js:

Vue.component('home', {
    props: {src: String},
    template: `<iframe class='flexible' :src='src'></iframe>`
})


(confront props.src and "home": {"src": "pages/home"} above).


Binding component post function
+++++++++++++++++++++++++++++++

Also, the 'post' function defined in the main Vue instance is passed to any
child component so that a post can be issued from anywhere and has the same
behaviour: freeze buttons, show waitbar etceters. The result of the POST can
be then attached and processed from within each sub-coimponent with normal axios
(and ES6) Promises ('.then(handle your code here)')

This allows, for components defining the proeprty 'post' (i.e., binding
that 'post' passed from the Vue instance into a component property), to
write something like:

this.post(this.url, formObject).then(response => {
      if (response && response.data){
      	...do whatever you want here
      } 
}).catch(... if you want to catch errors ...);
  
and the Vue instance takes care of issuing the POST request, making the waitbar
visible, displaying the error in case of error, and then providing custom
component code via 'then' and 'catch' callbacks.


Listening for events
++++++++++++++++++++

The <component> has also two (for the moment) attributes starting with '@' (or 'v-on:') they are
event listeners. The syntax is:

@event_name="function_to_be_called"

The function to be called is implemented in egsim_base.js, whereas the event 
can be fired within each component with he syntax $emit('event_name', arguments), where
arguments are any (optional) argument that have to be implemented in the attached function
of egsim_base.js.

The events fired are currently two: the selection of gsims from the gsims.js component:
@gsim-selected='selectGsims'

And the link to the selection expression help from within each component implementing
a gmdb (Ground Motion batabase) selection expression (e.g., residuals.js):
@movetoapidoc='moveToApidoc'



-------------------------------------------------------------------------------
FIXME TODO: describe component pros: url, form, request, post to help the user
understanding also each component


IMPLEMENTING A NEW COMPONENT:

- add script tag in egsim.html
- copy one of the existing components in a new JS file
