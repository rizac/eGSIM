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
created the associated [input] component from the Field data (e.g. select,
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

`FormDataHTTPClient` is the Mixin base class for all Form related components
and is intended to perform HTTP requests with the form data as request data.
It is subclassed by the component `egsim-form`, which is in turn used
in `trellis.js`, `residuals.js` and `testing.js`.

`egsim-form` handles also the fact that the <div> disappears and becomes a 
dialog window after the first submission. To implement a more general form
component from `FormDataHTTPClient`, e.g. a `my-form` Component from 
a given Form Object and a URL where to send POST request with the form data:

```
<my-form :form=form :url=url />
```

then, along the lines of `egsim-form` one could write:

```
EGSIM.component('my-form', {
    mixins: [FormDataHTTPClient],
    emits: ['submitted'],  // needed only if we want to emit, see below
    template: `<form novalidate @submit.prevent="submit">
        <!-- you form component here, associated to this.form -->
       <button type='submit'>Ok</button>
    </form>`
    methods: {
        submit(){
            // call FormDataHTTPClient.postFormData. You can also
            // chain the promise for performing custom operation upon 
            // submission, e.g. let's emit the event 'submitted
            this.postFormData().then(response => {
                this.$emit('submitted', response);
            });
        },
    }
});
```


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
        getPlots(responseObject){}
    }
});

```
Where the only required method to "subclass" is:

### `getPlots(responseObject){}`

Return an Array of plots (aka "figure" in plotly, see
https://plotly.com/javascript/reference/index/) from the given response.
Each plot has in EGSIM an additional `params` key, so a plot is an Object of the type:

```javascript
{
    data: Array, 
    layout: Object,
    params: Object
}
```

#### Plotly data arguments:
 
 - `data` is the plot data, an Array of Trace Objects (lines, points, bars) e.g.:
    ```
    {
        x: Array, 
        y: Array, 
        name: string
    }
    ```
    For details, see https://plotly.com/javascript/reference/.
    Consider that some layout-related keys will be set automatically and 
    overwritten if present: `xaxis` (string), `yaxis` (string), `showlegend` 
    (boolean).
   
    **Notes:** 
   
    - Providing a `name` key to a Trace Object makes the name showing
      when hovering over the trace with the mouse.
   
    - To add the Trace to the legend, set its `legendgroup` attribute. All 
      traces with the same legend group are treated the same way during 
      click/double-click interactions.
      Usually, you need to get a starting color for a `legendgroup` in order 
      to style all legend traces the same way. You can do this by using 
      `this.colors.get(legendgroup)` which returns a color from a cyclic 
      palette assuring that the same `legendgroup` is mapped to the same color. 
      Example:
 
      ```javascript
      trace.legendgroup = trace.name;
      var color = this.colors.get(trace.legendgroup);
      trace.line = { color: this.colors.rgba(color, 0.5) }
      ```
   
 - `params` eGSIM specific property (ignored by Plotly), 
    define the plot parameters (String -> Any scalar), e.g. 
    ```
    {magnitude: 5, xlabel: 'PGA', 'PGV': 0.01}
    ```
    Params dictate how plots should be selected (e.g., show only plots of 
    magnitude 5) and arranged in grid layouts (e.g. show plot on a grid where x:
    magnitude values and y: PGA values).
    
    All traces must return the same `params`, i.e,. Objects
    with the same keys. `params` that are mapped to the same value for all plots
    will be discarded.
     
 - `layout` is the Plot layout, e.g.:
   
    ```
    { 
        xaxis: {
            title: 'A title', 
            type: 'log'
        }, 
        yaxis: { 
            ... 
        }
    }
    ```
    For details, see https://plotly.com/javascript/reference/layout.
    Note that some layout-related keys will be set automatically and overwritten if
    present: `[xy]axis.domain` and `[xy]axis.anchor`.

### Plot details

The plot is performed in two step: the first is by calling `plot.newPlot`, then
by calling `Plotly.relayout` which re-positions the plots and labels. In 
between, we compute the space taken by all elements to correctly compute 
reserved space: plots margin (tick labels space) and paper padding (the plots 
grid layout space, if present)

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