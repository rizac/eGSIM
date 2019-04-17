Back-end TUTORIAL for DEVELOPERS:
==================================

Our backend is built with Django. Although Django is commonly used for validating
input, generating forms and html strings to be injected into the HTML, due to
the fact that we use a single page application with VueJS (see frontend README),
only the validation part is used throughout the Form classes.
Django might be thus an overhead, and solutions like djanog RESt framework might
be more appropriate, but they reinvent too much the wheel in my opinion, and
there is nothing we can achieve with those libraries that we can not already
achieve with Django (which, we remember, is shipped with openquake)

To implement a new REST service, a new View class inerhting from EgsimQueryView
(views.py) has to be implemented. The view must have a Form and a url, and
override the `process` mathod.

Then, fo to urls.py and add the url under:
```
# REST APIS:
urlpatterns.extend([
...
```

After that, you need to implement the newly created form in forms.py and
optionally the Fields (have a look at fields.py).
If you need custom validation, overwrite the 'clean' method of the form.
If you need customk initialization, overwrite the 'init' method of the form.
If you need fields pre-processing the input, implement your own in fields.py.
Please refer to all already implemented Forms and Fields, as most likely
a similar routine case has already been implemented.

FIXME: write what forms.BaseForm does

The form returns the dict of data "cleaned" (you do not need to care about that).
The last step is to overwrite the view 'process' method whichdoes the work of returning
a json serializable object (or a JsonResponse object). The method usually takes
the form output and calls some function (generally implemented in semtk.py)
to do the calculations. Remember that any exception raised after the form validation
and the json response return is up to you: in principle, a 500 error is sent, so
you have to catch your own exceptions and have a look at
middlewares.ExceptionHandlerMiddleware.jsonerr_response
to generate a google-API compliant json error response