def validate(formclass):
    '''creates a validator for a function processing a dict resulting e,g, from a web request
    The validator must be a django form that will be called with the dict. The validated
    dict will then be passed to the decorated function. The dict must be the function's first
    argumeent

    Example:

    @validate(MyForm)
    def process_params(params, *args, **kwargs):
        # here params is assured to be validated with 'MyForm' and can be safely processed
    '''
    def real_decorator(function):
        def wrapper(params, *args, **kwargs):
            validated_params = formclass(params).clean()
            return function(validated_params, *args, **kwargs)
        return wrapper
    return real_decorator
