# JS Developers Cheatsheet

## plot-div
(base/plot-div.js)

This abstract class (or better Vue mixin) is the main 
container for displaying grids of plots. 
In "subclasses" (see trellis.js, testing.js, residuals.js 
and flatfile.js) one mandatory and two optional
methods must be implemented in order to dictate how to display 
these plots and the
<[select]> that will allow switching among them, if needed.

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
      `yaxis` (string), `showlegend` (boolean) and `legendgroup` (see `addLegend`
      below).
 
    - Providing a `name` key to a Trace Object makes the name showing
      when hovering over the trace with the mouse.
   
    - To add the Trace to the legend, where a checkboxes allow to toggle the 
      Traces visibility, call `addLegend`:
 
      ```
      var color = this.addLegend(trace, trace.name)
      trace.line = {color: color}
      ```
 
      `trace.name` in the example above sets the `key` argument of `addLegend`. `key` 
      is both the checkbox label shown on the GUI, and an unique identifier: 
      calling `addLegend` with the same key for several traces will toggle all 
      traces visibility at once. 
 
      If no item is in the legend, the right panel is not shown. The right panel
      includes several controls such as log axis, download actions and so on (this
      behavious could anyway change in the future and the right panel shown anyway)
 
      To specify an explicit color for non yet mapped key, call:
      `addLegend(trace, key, color)` where color is a string in the HEX-form
      '#XXXXXX' that can be created via a `colorMap` for details.
   
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
