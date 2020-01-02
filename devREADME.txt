Developer Guide

Backend Frontend communication
==============================

We use Django as backend framework, because - for some unknown reason - it's already integrated with OpenQuake.
Django is primarily used for multi-page browser applications, i.e. where most of the client (browser) requests are returned from
the server in form of HTML pages to be displayed in the client browser.

There are two limitations to this:
1. EGSIM is a Web API, thus the client browser should be on top of the API, not the application itself.
	Most of Django stuff should be therefore redundant or not "ad hoc". It turns out, that using Django as Rest framework
	is possible and way easier than most of addons libraries (e.g., django rest framework) which
	simply add complexity to the package and nothing more that cannot be already achieved by sending JSOn responses from
	within Django, after validating the POST/GET data via Form validations

2. EGSIM uses a single page application as browser portal. We chose VueJS to experiment a bit and because it seems
   to be the only JS frameworks with model-view controllers adapted for complex **and simple projects**
   (Building a simple page with Angular or React is as easy and straighforward as getting a master in engenerring in order
   to build a doghouse).
   This means that we cannot use many of Django features, e.g. page templates and form re-rendering.
   We therefore exploit the we API to send/receive JSOn data from within the browser, as if it was a "normal" client.
   To exploit Django Form rendering, i.e. delegate Django for the <input> and <select> tags rendering, we built a custom
   method 'to_rendered_dict' in 'forms.BaseForm' which converts a form to a dict which, after json serialization,
   can be injected in the (only) HTML page via {{ dict|safe }}. After that, the dict.attrs can be bound to any HTML element
   via v-bind:data['name'].attrs  <- FIXME: more doc here
   
3. 