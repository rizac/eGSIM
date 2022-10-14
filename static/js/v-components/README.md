# Developers README

## Table of Contents

- [FORM FIELD INPUTS in egsm-form.js](#FORM-FIELD-INPUTS)
- [FormDataHTTPClient in egsm-form.js](#FormDataHTTPClient)
- [PlotsDiv in plot-div.js](#PlotsDiv)
- [FLATFILE_SELECT_COMPONENT](#FLATFILE-SELECT)

## Overview

eGSIM handles the communication between Django (backend Python library) 
and Vue (frontend JavaScript library) via
JSON serializable Python dicts, or JavaScript Objects.

The main Object which represents both a Django and an HTML `Form` 
for sending data is a so-called `Form Object`:
```
form_obj = {
    "parameter1": {
        "value": [1, 2],
        "choices": [0, 1,2,3,4,5,6,7,8,9],
        "error": "",
        "disabled": "false
    },
    "parameter2": { ... }
    ...
}
```

Above, each 'parameterN' is mapped to a so-called `Field` Object
(the term is Django legacy) that represents a Form parameter.


## FORM FIELD INPUTS
(`v-components/base/field-form.js`)

A Field is represented via a `field-input` which automatically
created the associated [input] component from he Field data (e.g. select,
input[type=checkbox], and so on)

```
<field-input :field="form_obj['parameter1']" />
```


A Field input can also be called for more control with each parameter 
separately using a `base-component`, a base class for any HTML input 
or select component:

```
<base-input v-model="field.value" :disabled="field.disabled"
    :choices="field.choices" :error="field.error" />
```

('error' is a string usually returned from the server. When error
is given, it outlines the component in red, if present)

## FormDataHTTPClient
(`v-components/base/egsim-form.js`)

`FormDataHTTPClient` is the Mixin base class for all Form related components.
This snippet shortly describes how to use FormDataHTTPClient in subclasses. 
Given, e.g. a subclass `my-form`:

```
<my-form :form=form :url=url @submitted='my_callback' />
```

where:
 - `form` is a Form object (see above)
 - `url` is the URL to which a request will be sent with the Form data
 - `@submitted` is the Vue event fired when the server successfully
   sent a response after submission. `my_callback` is a function 
   taking the axios response Object as argument and has to be 
   implemented somewhere to process the response. For instance 
   throughout the code (e.g., `trellis.js`, `residuals.js`) you will 
   see a wrapper component implementing
   a `FormDataHTTPClient` component, and a `PlotsDiv` component receiving the form 
   submitted data in order to update its plots 
   (For `PlotsDiv` see details below):
   ```
   Vue component('wrapper',{
        data() {
            return {
                resData: {}
            }
        },
        template: `
            <my-form @submitted='resData=arguments[0].data' ... />
            <my-plot-div :data="resData" ... >
        `
   });
   ``` 
  listening
   the successful submit and takes as first argument the `axios` 
   `response` object (see snippet below)
   
To let the code above work, the implementation of `my-form` in 
Vue might look at least like this:

```
EGSIM.component('my-form', {
   mixins: [FormDataHTTPClient],
   props: {
   }
   template: `<form novalidate @submit.prevent="mySubmitFunc">
       <button type='submit'>Ok</button>
   </form>`
   methods: {
       mySubmitFunc(){
           this.submit().then(response => {
               this.$emit('submitted', response);
           }
       }
   }
});
```

Notes:

 1. `props` here you implement additional `props`, 
    remembering that you have the props `this.url` and `this.form`
    (defined in `FormDataHTTPClient`) by default
    
 2. `template` in the template you implement your components
    usually bound to elements of `this.form`. As such, the snippet above
    must be filled with something meaningful

 3. `mySubmitFunc` this is your submit function. You can call here 
    `this.submit()` (implemented in `FormDataHTTPClient`) that does all the 
    work of creating a FormData, send it to `this.url`
    with correct headers and displaying errors in case. 
    `this.submit` is a `Promise` that you can chain as in the snippet
    above, where we notify the listeners emitting a `submitted`
    event


## PlotsDiv
(`v-components/base/plot-div.js`)

`PlotsDiv` is the Mixin base class for all Grids of plots
This snippet shortly describes how to use FormDataHTTPClient in subclasses. 
Given, e.g. a subclass `my-plot-div`:

```
<my-plot-div :data="responseData" 
             :download-url="urls.downloadResponse">
```

where:

- `responseData` is the `response.data` Object received from the server
  after e.g. form submission (e.g., there must be a `FormDataHTTPClient` implementing
  something like `@submitted="responseData=arguments[0].data`)

- `download-url` is  a string of the URL to call for downloading plots

To let the code above work, the implementation of `my-plot-div` in 
Vue might look at least like this:

```
EGSIM.component('my-plot-div', {
    mixins: [PlotsDiv],
    methods: {
        getData(responseObject){},
        displayGridLabels(axis, paramName, paramValues){}
        configureLayout(layout){}
    }
});

```
Among the three methods above one is mandatory (`getData`) and 
two optional. These methods dictate how to display 
plots and the controls of the plot grid.

### `getData(responseObject)`

(mandatory) return from the given response object an Array of Objects.
Each Object represents a sub-plot to be visualized, in the form:

```javascript
{
    traces: Array, 
    params: Object, 
    xaxis: Object, 
    yaxis: Object
}
```

#### Function arguments:
 
 - `traces` Array of Trace Objects (lines, points, bars) e.g.:
    ```
    {
        x: Array, 
        y: Array, 
        name: string
    }
    ```
    - A list of keys of each Object is available at 
      https://plot.ly/javascript/reference/. Consider that some layout-related 
      keys will be set automatically and overwritten if present: `xaxis` (string), 
      `yaxis` (string), `showlegend` (boolean).
 
    - Providing a `name` key to a Trace Object makes the name showing
      when hovering over the trace with the mouse.
   
    - To add the Trace to the legend, set its `legendgroup` attribute. All traces with 
      the same legend group are treated the same way during click/double-click 
      interactions.
      Usually, you need to get a starting color for a `legendgroup` in order to style
      all legend traces the same way. You can do this by using 
      `this.colors.get(legendgroup)` which returns
      a color from a cyclic palette assuring that the same `legendgroup` is mapped to
      the same color. Example:
 
      ```
      trace.legendgroup = trace.name;
      var color = this.colors.get(trace.legendgroup);
      trace.line = { color: this.colors.rgba(color, 0.5) }
      ```
      
      If no item is in the legend, the right panel is not shown. The right panel
      includes several controls such as log axis, download actions and so on (this
      behaviour could anyway change in the future, and the right panel shown anyway)
   
 - `params` Object defining the plot properties (String -> Any scalar), e.g. 
    ```
    {magnitude: 5, xlabel: 'PGA', 'PGV': 0.01}
    ```
    The property names ('magnitude', 'xlabel' and 'PGV' in the example above) 
    will be collected and made selectable on the GUI, 
    so that users can choose two of them on the X and Y axis in order 
    display plot in grids, where each plot is
    placed on the grid according to its parameters values.
    
    Consequently, all traces must return the same `params`, i.e,. Objects
    with the same keys. If `params` is always composed of the same single 
    key and the same value, then in this
    case it's used to display the main plot title as `${key}: ${value}`.

  - `xaxis` Object of x axis properties, e.g.:  
    ```
    {title: 'A title', type: 'log'}
    ```
    The final Axis properties will be built by merging `this.defaultxaxis`
    and the values provided here. For a list of possible keys, see: 
    https://plot.ly/javascript/reference/#layout-xaxis, but consider that
    some layout-related keys will be set automatically and overwritten if
    present: `domain` and `anchor`.

 - `yaxis` 
   A `dict` of y axis properties. See `xaxis` above for details.
          

### `displayGridLabels(axis, paramName, paramValues)`

(optional) return true / false to specify if the given parameter should be displayed
as grid parameter along the specified axis. In the default implementation
of `plot-div.js`, return `true` if `paramValues.length > 1`.

#### Function arguments:

 - `axis` String, either 'x' or 'y'
 - `paramName` The string denoting the parameter name along the given axis
 - `paramValues` Array of the values of the parameter keyed by 'paramName'


### `configureLayout(layout)`

(optional configure the `layout` Object to be passed to plotly (for details, see
https://plotly.com/javascript/reference/layout/). 
Note that the `layout` keys `font.family` and `font.size` will be 
overwritten if present as they need to be equal to the HTML page in order 
to reliably calculate spaces and sizes.

#### Function argument:

 - `layout` Object copied from `this.defaultlayout` which can be modified
   here. Note that this function does not need to return any value
   

## FLATFILE SELECT
(`v-components/flatfiles.js`)

This [select] component associated to the flatfile Field of, e.g.,
residuals and testing forms, behaves differently than the other components
associated to Form Fields because:

- when a flatfile is selected, the Field `value` type must change 
  dynamically: a String for predefined flatfiles, or a File object 
  (the DOM object returned from uploaded files)
  
- we want to upload user-defined flatfiles. But in doing so, we need to:
  - know if the same flatfile has already been uploaded (change 
  the [option] component label) or is new (add a new [option] component) 
  - never replace a predefined flatfile in the [option]s list
  
- make any change in the available flatfiles immediately
  available also in all other similar [select] components on the page
  
As such, in a [flatfile-select] we watch immediately for any change 
(deep) in the global `$flatfiles` variable (Array of flatfiles). 
The watcher updates the Field `choices` with the flatfile index and label.
The [select] component `model` is not bound to the Field value,
but to a Component variable called `selectedFlatfileIndex` (int).

When a flatfile is selected, `selectedFlatfileIndex` changes, and
because it is watched, it updates the Field `value` accordingly (File
or String). 

When a flatfile is uploaded, we check whether it is a new [option] or
has to override an existing one *by index* (so that we avoid overwriting
predefined flatfiles), and then we update the global
`$flatfiles` variable: this makes the flatfile available to all
[select] and also triggers the update of the [options] in the
current [select] component.