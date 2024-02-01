# Developers README

## Table of Contents

- [FORM FIELD INPUTS in egsm-form.js](#FORM-FIELD-INPUTS)
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

## PlotsDiv
(`v-components/base/plot-div.js`)

`PlotsDiv` is the Mixin base class for all Grids of plots
This snippet shortly describes how to use it in subclasses. 
Given, e.g. a subclass `my-plot-div`:

```
<my-plot-div :data="responseData" 
             :download-url="urls.downloadResponse">
```

where:

- `responseData` is the `response.data` Object received from the server
  after e.g. form submission

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

### Plotting details (for developers needing to modify plot-div source code)

In `plot-div`s, the plot is performed in two steps: the first is by calling 
`Plotly.newPlot`, then by calling `Plotly.relayout` which re-positions the plots 
and labels. In between, we compute the space taken by all elements to correctly 
compute reserved space: plots margin (tick labels space) and paper padding (the 
plots grid layout space, if present). Plotly supports several parameters to 
control the plots layout, but we were not satisfied by the results. Hence, the 
two-steps workaround just described.

`NewPlot` is implemented along the line of https://plotly.com/javascript/subplots/#multiple-custom-sized-subplots:

```javascript

// plot data:
var data = [
  {
    // 1st trace. Setup trace data and then assign its plot:
    xaxis: 'x1',  // trace plot x axis (see Layout.xaxis below)
    yaxis: 'y1'   // trace plot y axis (see Layout.yaxis below)
  },
  {
    // 2nd trace. Setup trace data and then assign its plot:
    xaxis: 'x2',  // trace plot x axis (see Layout.xaxis2 below)
    yaxis: 'y2'  // trace plot y axis (see Layout.yaxis2 below)
  }
];

// Note: It turns out (although not documented in plotly) that "xaxis" and "yaxis"
// keys above can be omitted and they will default to 'x1' and 'y1'. In the
// code, we prefer to be explicit and provide the keys anyway

// plot layout (plot axes positions and size):
var layout = {
  xaxis1: {  // for xaxis1, "1" is actually optional
    domain: [0, 0.45],  // axis left and right, in paper coordinates (in [0, 1])
    anchor: 'y1'  // opposite axis
  },
  yaxis1: {  // for yaxis1, "1" is actually optional
    domain: [0.5, 1],  // axis bottom and top, in paper coordinates (in [0, 1])
    anchor: 'x1'
  },
  xaxis2: {
    domain: [0.55, 1],
    anchor: 'y2'
  },
  yaxis2: {
    domain: [0.8, 1],
    anchor: 'x2'
  }
};

// Note: It turns out (although not documented in plotly) that in "layout.xaxis1" 
// and "layout.yaxis1" the "1" is optional. In the code, we prefer to be explicit 
// and provide "xaxis1" and "yaxis1" anyway

// Then plot with plotly:
Plotly.newPlot(<root_div>, data, layout);
```

`relayout` is then called after setting the new computed axis domains.
Note that it supports overwriting nested properties via the
dot. Example:

```javascript
// plot layout (plot axes positions and size):
var layout = {
  'xaxis1.domain': [0, 0.55]  // overwrite 'domain' property of 'xaxis1' only
  'yaxis1.domain' ...
  'annotations': [],  // list of grid labels and tick labels, if any 
  'shapes': []  // list of the horizontal and vertical grid lines, if needed
};

// Then plot with plotly:
Plotly.relayout(layout);
```


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