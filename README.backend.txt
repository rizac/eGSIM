Back-end TUTORIAL for DEVELOPERS:
==================================

The egsim backend is built with Django, a high-level Python Web framework.
Django is used as REST API, meaning that it implements all
url endpoints validating request inputs and calling the associated smtk
processing function and returning JSON formatted responses, and all
frontend implementation is delegated to the javascript library used (VueJS, see
README.frontend.txt). 
This means that some functionalities of Django are not used, and some
others needed to be adapted (e.g., Form methods passing <input> and <select>
attributes to VueJS, without creating an HTML page for that).


Some history about implementation choices
-----------------------------------------

Why not using django rest framework (DRF):
Answer: (TL/DR) not addressing any of our problem, relatively big overhead

djangorestframework is a toolkit for building Web APIs. Simply gp to their
home page and see  what are the reasons they claim we might want to use REST
framework: none of thenm is of interest (authentication, serialization, web
browable API). On the other hand, DRF implements several new concepts which
look like reinventing the wheel and their need should be clearly stated
(e.g. Validators vs Form validation)

Why not using Django + jQuery (standard old style approcah).

The community of web JavaScript frameworks is certainly
insane (see refs in README.frontend.txt), but it's 2019 and we wanted a simple
modern frameowrk which made our JavaScript code cleaner and easier to maintain
 
Why not using some other backend:

Of course, maybe simpler web frameworks (e.g. Flask) could have been also a
valid choice. Three reasons for using Django:
1 - It was already included in OpenQuake, a dependency library of eGSIM
2 - Django was a new web frameworks that we did not know yet and was worth a
    try
3 - The big Django community might have made easier finding tutorials and
    material on how to deploy the app on a dedicated server (and it did)


Implementing new services
-------------------------

To implement a new REST service, a new View class inerhting from EgsimQueryView
(views.py) has to be implemented. The view must have a Form and a url, and
override the `process` mathod.

Note: Most of the url endpoints are implemented in views.py via strings
(see global variables on top of the module). Then, urls.py uses these strings.
The advantage is then these url strings can be passed to the frontend and be
clled from therein.

Then, edit 'urls.py' and add the url(s) under `urlpatterns`, which should
be kept (for maintenance experience) as readable as possible: avoid e.g.,
using loops when populating `urlpatterns` or `urlpatterns.extend`, if possible.


IMPORTANT NOTE
--------------

After that, you need to implement the newly created form in forms.py and
optionally the Fields (have a look at fields.py). The form needs to
extend egsim.forms.BasForm or subclasses (see BaseForm methods for info).
If you need custom validation, overwrite the 'clean' method of the form.
If you need custom initialization, overwrite the 'init' method of the form.
If you need fields pre-processing the input, implement your own in fields.py.
Please refer to all already implemented Forms and Fields, as most likely
a similar routine case has already been implemented.
The form returns the dict of data "cleaned" (you do not need to care about
that).

The last step is to overwrite the view 'process' method which does the work of
returning a json serializable object (or a JsonResponse object). The method
usually takes the form output and calls some function (generally implemented
in smtk.py) to do the calculations. Remember that any exception raised after
the form validation and the json response return is up to you: in principle,
a 500 error is sent, so you have to catch your own exceptions and have a look
at middlewares.ExceptionHandlerMiddleware.jsonerr_response to generate a
google-API compliant json error response.
