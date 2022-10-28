# Developers README

This Django App (standalone Python package that can
be plugged to a Django project) implements the basic eGSIM API.

As in any Django app, everything starts in `urls.js`. As you can 
see, urls strings are actually implemented in `views.py`. the reason
is that we can then pass the strings to both `urls.py` and the
frontend (see `app` package) more easily.

In `urls` we use a `RESTAPIView` class instead of the classical
Django view function. For info in class-based views, see [here](
https://docs.djangoproject.com/en/stable/topics/class-based-views/).

A `views.RESTAPIView` must implement two attributes, a `formclass` and
a list of `urls`. Urls have been described above, whereas the 
form class is the API form that will provide the service:
```python
# in egsim.api.views:

class RESTAPIView(View):
    
    # The APIForm of this view. You can set 
    # it at a class level in subclasses, or
    # pass at instance level via: 
    # `__init__(formclass=...)`
    formclass: Type[APIForm] = None
    
    # the URL(s) endpoints of the API (no 
    # paths, no slashes, just the name)
    urls: list[str] = []
```

An APIForm is where the core routine is implemented. An `APIForm` is a Django
Form that implements a property `response_data` that will be used in `views.py` 
to get the response data. `response_data` calls **two methods** (depending on 
the `format` requested by the user) **that must be implemented in subclasses**
(any exception raised below will be caught as a `500 server error` in 
`views.py`):

```python
# in egsim.api.forms.__init__:

class APIForm(MediaTypeForm):
    
    @classmethod
    def process_data(cls, cleaned_data: dict) -> dict:
        """
        Process the input data `cleaned_data` 
        returning the response data of this 
        form upon user request. This method is 
        called by `self.response_data` only 
        if the form is valid.

        :param cleaned_data: the result of 
            `self.cleaned_data`
        """
        raise NotImplementedError(":meth:%s.process_data" % cls.__name__)

    @classmethod
    def csv_rows(cls, processed_data) -> Iterable[Iterable[Any]]:
        """
        Yield CSV rows, where each row is an 
        iterables of Python objects representing 
        a cell value. Each row doesn't need to 
        contain the same number of elements, 
        the caller function `self.to_csv_buffer` 
        will pad columns with Nones, in case 
        (note that None is rendered as "", any other
        value using its string representation).

        :param processed_data: dict resulting 
            from `self.process_data`
        """
        raise NotImplementedError(":meth:%s.csv_rows" % cls.__name__)
```

Basic hierarchy of eGSIM Forms (see `api.forms.__init__.py`):

```
[EgsimBaseForm] a Django Form that exposing the Form field attribute 
│              names to one or more public parameter names, and formatting 
│              errors into a dict with keys following the Google API spec
│
└── [SHSRForm] an EgsimBaseForm retrieving a list of models from a given geo
│    │         location. After validation , the list of models will be put in 
│    │         SHSRForm.cleaned_data and can be used in subclasses
│    │   
│    └── [GsimImtForm] a SHSRForm that accepts also models as list of names,
│                      and intensity measures. Performs some checks during 
│                      validation
│    
└── [APIForm] an abstract EgsimBaseForm that processes the request and returns
              the response in different media types (or mime types) such as 
              JSON, CSV via the main property:
              APIForm.response_data: Union[dict, StringIO, None]
              The method response_data calls in turn two asbtract methods to be
              implemented in subclasses (see above) 
```

Many Forms used in eGSIM are subclasses of both 
`GsimImtForm` and `APIForm`
