"""Container for some utilities used in this package"""
import re


def vectorize(value):
    """Return `value` if it is already an iterable, otherwise `[value]`.
    Note that :class:`str` and :class:`bytes` are considered scalars:
    ```
        vectorize(3) = vectorize([3]) = [3]
        vectorize('a') = vectorize(['a']) = ['a']
    ```
    """
    return [value] if isscalar(value) else value


def isscalar(value):
    """Return True if `value` is a scalar object, i.e. a :class:`str`, a
    :class:`bytes` or without the attribute '__iter__'. Example:
    ```
        isscalar(1) == isscalar('a') == True
        isscalar([1]) == isscalar(['a']) == False
    ```
    """
    return not hasattr(value, '__iter__') or isinstance(value, (str, bytes))


def relabel_sa(string):
    """Simplifies SA string representation removing redundant trailing zeros,
    if present. Examples:
    'SA(1)' -> 'SA(1)' (unchanged)
    'SA(1.0)' -> 'SA(1.0)' (unchanged)
    'ASA(1.0)' -> 'ASA(1.0)' (unchanged)
    'SA(1.00)' -> 'SA(1.0)'
    'SA(1.000)' -> 'SA(1.0)'
    'SA(.000)' -> 'SA(.0)'
    """
    return re.sub(r'((?:^|\s|\()SA\(\d*\.\d\d*?)0+(\))(?=($|\s|\)))', r"\1\2",
                  string)