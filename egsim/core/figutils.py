'''
Module converting plotly data to matplotlib figure

Created on 8 Aug 2019

@author: riccardo
'''
import os
import json
from io import BytesIO

import numpy as np
import matplotlib
# https://stackoverflow.com/questions/29620884/how-to-put-python-3-4-matplotlib-in-non-interactive-mode
matplotlib.use('Agg')  # @IgnorePep8
import matplotlib.pyplot as plt  # @IgnorePep8 pylint: disable=wrong-import-position

# global (READONLY) options:
DEFAULT_LINEWIDTH = 2
AXES_LINEWIDTH = 1
FIG_PADDING = 0.01  # in fig units (in [0.1])


def rgba2rgb(color, background=None):
    '''Converts the transparent color `color` into its opaque
    equivalent. That is, the returned color is what you see when `color`
    is rendered on the given `background`

    :param color: 4-elements list/tuple of numbers defining the transparent
        color in the usual rgba format with all numbers in [0 1] (matlab
        format). The first three numbers can also be in the [0 255] range
        (web format): whatever you provide, remember to be consistent
        with the `background` color, if the latter is provided

    :param background: 3-elements list/tuple of numbers defining the background
        color in the same format of `color` (either values in [0 1] or in
        [0 255])

    :return: a 3-element list with numeric elements ([0 1] or [0 255]
        depending on the input) defining the opaque color that results from
        `color` when rendered on `background`.
    '''
    # this function is modified from: https://stackoverflow.com/a/48359835
    alpha = color[3]
    color = color[:-1]
    # infer if we passed 0, 255 as color ranges by checking that all color
    # components are <=1: Note that these 7 notations:
    # [100] [010], [001] [110] [101] [011]
    # are ambiguous and will be interpreted to be in the [0 1] range, which
    # is far more likely in this context (note that "black" is not ambiguous)
    is01 = all(_ <= 1 for _ in color[:-1]) and \
        (background is None or all(_ <= 1 for _ in background))

    if background is None:  # defaults to white
        background = [1., 1., 1.] if is01 else [255., 255., 255.]

    ret = (1 - alpha) * np.asarray(background) + alpha * np.asarray(color)
    if not is01:
        ret = np.floor(ret + 0.5).astype(int)

    return ret.tolist()


class Converter:  # pylint: disable=invalid-name
    '''Class for functions converting plotly values to matplotlib values'''

    def __init__(self, opaque_colors=False):
        self.opaque_colors = opaque_colors

    def color(self, plotlycolor):
        '''
        converts plotly color to matplotlib color
        :param plotlycolor: is a string denoting a plotly color,
                e.g. rgba(...)
        '''
        clr = plotlycolor.lower()
        # convert strings 'rgb(...' or 'rgba(...' into tuples for matplotlib:
        colors = (clr[4:-1] if clr[:4] == 'rgb(' and clr[-1:] == ')' else
                  clr[5:-1] if clr[:5] == 'rgba(' and clr[-1:] == ')' else
                  '').split(',')
        if len(colors) not in (3, 4):  # no rgb or rgba string
            return plotlycolor
        # matplotlib wants all values in [0, 1], plotly has rgb in [0, 255]:
        ret = [float(_)/255.0 for _ in colors[:3]]
        if len(colors) == 4:
            ret.append(float(colors[-1]))
            if self.opaque_colors:
                ret = rgba2rgb(ret)
        return ret

    @staticmethod
    def angle(plotlyangle):
        '''converts plotly angle to matplotlib rotation'''
        angle = float(plotlyangle)
        if angle < 0:
            # plotly goes counter-clockwise, wird behaviour, so:
            angle = -angle
        return angle

    @staticmethod
    def alignment(plotlyalign):
        '''converts plotly alignment to matplotlib alignment'''
        return 'center' if plotlyalign == 'middle' else plotlyalign

    @staticmethod
    def fontprops(plotlyfontdict, dpi, prefix='font'):
        '''converts plotly font dict / object into a dict of matplotlib
        font arguments. Only 'fontfamily' and 'fontsize' are currently
        supported
        '''
        ret = {}
        # for default properties, see:
        # https://matplotlib.org/api/font_manager_api.html#matplotlib.font_manager.FontProperties
        # we use here the 'normal' keyword arguments, which seem to be the
        # attributes of the object above prepended with 'font':
        if 'family' in plotlyfontdict:
            ret['%sfamily' % prefix] = []
            for _ in plotlyfontdict['family'].split(','):
                if (_.startswith('\'') and _.endswith('\'')) or \
                        (_.startswith('"') and _.endswith('"')):
                    ret['%sfamily' % prefix].append(_[1:-1])
                else:
                    ret['%sfamily' % prefix].append(_)
        if 'size' in plotlyfontdict:
            ret['%ssize' % prefix] = \
                Converter.length(plotlyfontdict['size'], dpi)
        return ret

    @staticmethod
    def length(pixels, dpi):
        '''converts a length (in pixels) to the required matplotlib length
        according to the given dpi. This method should be used for all
        lengths, widths and font sizes given in plotly
        '''
        if isinstance(pixels, (int, float)):
            return pixels * 72 / dpi
        return pixels


def get_img(data, layout, width, height, format):  # @ReservedAssignment
    """
    Creates image from the given plotly data and layout in the specified format
    and returns the image as bytes string

    :param data: list of dicts in the same format as Plotly `data` argument
    :param data: dict in the same format as Plotly `layout` argument
    :param width: image width (int), in pixels
    :param height: image height (int), in pixels
    :param format: string, any matplotlib format defined for the current
        matplotlib backend (currently 'Agg'). Tested formats are:
        'pdf', 'eps', 'png', 'svg'

    :return: a bytes string representing the image
    """
    format = format.lower()  # @ReservedAssignment
    # assert format in ('pdf', 'eps', 'png', 'svg')
    converter = Converter(True) if format == 'eps' else None
    fig = get_fig(data, layout, width, height, converter)
    bio = BytesIO()
    fig.savefig(bio, transparent=True, dpi='figure', format=format)
    return bio.getvalue()


def get_fig(data, layout, width, height, converter=None):
    """
    Creates and returns the matplotlib figure from the given plotly data and
    layout

    :param data: list of dicts in the same format as Plotly `data` argument
    :param data: dict in the same format as Plotly `layout` argument
    :param width: figure width (int), in pixels
    :param height: figure height (int), in pixels
    """
    if converter is None:
        converter = Converter()

    # so, width and height are supposed to be in pixels.
    # points = pixels * 72 / dpi
    # inches = points / 72
    # inches = pixels / dpi
    dpi = 300  # dpi affects the font size and lines width/length! (see below)
    fig = plt.figure(figsize=(width/dpi, height/dpi), dpi=dpi)
    # get_dpi might be not the dpi set:
    # https://github.com/matplotlib/matplotlib/issues/11227
    # https://github.com/matplotlib/matplotlib/pull/11232
    dpi = fig.get_dpi()

    # set matplotlib global properties:
    # font:
    if 'font' in layout:
        matplotlib.rc('font',
                      **converter.fontprops(layout['font'], dpi, prefix=''))
    # set also the linewidth of the axes globally:
    matplotlib.rcParams['axes.linewidth'] = \
        converter.length(AXES_LINEWIDTH, dpi)

    axes = setup_axes(layout, fig, converter)

    # draw objects on the figure, anootations (texts, e.g. axis labels)
    # and legend:
    legend_objs = draw_plotly_data(data, axes, converter)
    annotations = draw_plotly_annotations(layout, fig, converter)

    # create legend:
    leg = None
    if legend_objs:
        leg = fig.legend(legend_objs.values(), legend_objs.keys(),
                         'upper right', frameon=False)

    figure_area = [FIG_PADDING, FIG_PADDING,
                   1 - 2 * FIG_PADDING, 1 - 2 * FIG_PADDING]  # x,y,w,h
    readjust_positions(axes, annotations, fig, figure_area, leg)

    return fig


def setup_axes(layout, fig, converter):
    '''
    Sets up the axes on the given figure according to the plotly layout
    and returns a dict of axes mapped to the key they are referred to in each
    plotly `data` item

    :param layout: the plotly layout (dict)
    :param fig: the matplotlib figure
    '''
    axesdict = {}
    for key, layout_x in layout.items():
        if key.startswith('xaxis'):
            key_x = key
            key_y = key.replace('xaxis', 'yaxis')
            layout_y = layout[key_y]

            domain_x = layout_x['domain']
            domain_y = layout_y['domain']

            axes = fig.add_axes([
                domain_x[0],  # x
                domain_y[0],  # y
                domain_x[1] - domain_x[0],  # width
                domain_y[1] - domain_y[0]   # height
            ])

            # set axes linewidth:
            axes.spines['top'].set_linewidth(
                converter.length(layout_x.get('linewidth',
                                              layout_y.get('linewidth',
                                                           AXES_LINEWIDTH)),
                                 fig.get_dpi()))
            axes.spines['bottom'].set_linewidth(
                converter.length(layout_x.get('linewidth',
                                              layout_y.get('linewidth',
                                                           AXES_LINEWIDTH)),
                                 fig.get_dpi()))
            axes.spines['left'].set_linewidth(
                converter.length(layout_y.get('linewidth',
                                              layout_x.get('linewidth',
                                                           AXES_LINEWIDTH)),
                                 fig.get_dpi()))
            axes.spines['right'].set_linewidth(
                converter.length(layout_y.get('linewidth',
                                              layout_x.get('linewidth',
                                                           AXES_LINEWIDTH)),
                                 fig.get_dpi()))

            # set ticks and padding, this has also to be set depending on
            # the dpi:
            # (https://stackoverflow.com/a/14450056):
            leng = matplotlib.rcParams['font.size'] / 4.0
            axes.tick_params('x', length=leng,
                             width=axes.spines['bottom'].get_linewidth(),
                             which='major', pad=leng)
            axes.tick_params('y', length=leng,
                             width=axes.spines['left'].get_linewidth(),
                             which='major', pad=leng)
            axes.tick_params('both', length=0, width=0, which='minor',
                             pad=leng)
            # TODO: plotly has grid on by default, here we avoid it for the
            # moment. In case, for info see:
            # https://matplotlib.org/3.1.1/api/_as_gen/matplotlib.axes.Axes.grid.html

            # set log scales:
            if layout_x.get('type', '') == 'log':
                axes.set_xscale('log')
            if layout_y.get('type', '') == 'log':
                axes.set_yscale('log')

            # set ranges if explicitly set:
            # Note that the range in plotly is log10(val) if type = log,
            # so we have to convert back with 10**val:
            if not layout_x.get('autorange', False) and 'range' in layout_x:
                values = layout_x['range']
                if layout_x.get('type', '') == 'log':
                    values = [10**values[0], 10**values[1]]
                axes.set_xlim(*values)
            if not layout_y.get('autorange', False) and 'range' in layout_y:
                values = layout_y['range']
                if layout_y.get('type', '') == 'log':
                    values = [10**values[0], 10**values[1]]
                axes.set_ylim(*values)

            # each line in data has the "xaxis" and "yaxis" mapped to "x1"
            # to mean "xaxis1", "x2" to mean "xaxis2", and so on, so to
            # retreive the axes map "x#", "y#" to this axes:
            axesdict[('x' + key_x[5:], 'y' + key_y[5:])] = axes

    return axesdict


def draw_plotly_data(data, axes, converter):
    '''
    Draws the plotly data on the given figure

    :param data: the plotly data (dict)
    :param layout the plotly layout (dict)
    :param axes: dict of strings mapped to an axes already added to the figure
        It is the returned value of `setup_axes`

    :return: the dict `legend_objects` of string (legend caption) mapped to the
        matplotlib object drawn (in case of multiple objects mapped to the
        same legend, the first object is set in this dict)
    '''
    legend_objs = {}
    for prev_datadict, datadict, next_datadict in zip([{}] + data[:-1],
                                                      data,
                                                      data[1:] + [{}]):
        if next_datadict.get('fill', ''):
            pass
        if datadict.get('fill', ''):
            if prev_datadict:
                datadict['_prev_x'] = prev_datadict['x']
                datadict['_prev_y'] = prev_datadict['y']
            if next_datadict:
                datadict['_next_x'] = next_datadict['x']
                datadict['_next_y'] = next_datadict['y']

        axs = axes[(datadict['xaxis'], datadict['yaxis'])]
        drawn_obj = draw_data(datadict, axs, converter)
        if drawn_obj is None:
            continue
        if 'legendgroup' in datadict and datadict.get('showlegend', False):
            legendgroup = datadict['legendgroup']
            if legendgroup not in legend_objs:
                legend_objs[legendgroup] = drawn_obj

    return legend_objs


def draw_plotly_annotations(layout, fig, converter):
    '''
    Draws the plotly annotations on the given figure as matplotlib
        Text elements

    :param layout the plotly layout (dict)
    :param fig: the matplotlig figure

    :return: the list of matplotlib text Objects drawn. This usually includes
        also the axis labels
    '''
    dpi = fig.get_dpi()
    # write annotations (note that this includes xlabels and ylabels)
    annotations = []
    for annot in layout['annotations']:
        textangle = annot.get('textangle', '')
        textangle = converter.angle(textangle) if textangle else 0
        halign = converter.alignment(annot.get('xanchor', 'center'))
        valign = converter.alignment(annot.get('yanchor', 'center'))
        ann = plt.figtext(annot['x'], annot['y'], annot['text'], figure=fig,
                          rotation=textangle, ha=halign, va=valign,
                          **converter.fontprops(annot.get('font', {}), dpi))
        annotations.append(ann)

    return annotations


def readjust_positions(axes, annotations, fig, figure_area=None,
                       legend=None):
    '''
    Readjusts the position of axes and texts (annotations) according to
    figure_area and legend

    :param axes: a list og matplotlib Axes added to the figure
    :param annotations: a list of matplotlib Text objects added to the figure
    :param fig: the figure
    :param figure_area: a 4 element list denoting the [x, y, width, height]
        of the figure, all values must be in [0, 1] i.e. figure coordinates.
        Note that width=1 will be the width of the figure minus the width
        of the legend (if the latter is not None). The legend is assumed to
        have been added in the 'upper right' position of the figure
    :param legend: None or the legend added to the figure. It must be added
        in the 'upper right' position of the figure
    '''
    if figure_area is None:
        figure_area = [0, 0, 1, 1]

    if legend is not None:
        bbx = dimensions(legend, fig)
        bbx_width = bbx.width
        # get figure size (https://stackoverflow.com/a/29702596)
        size = fig.get_size_inches() * fig.get_dpi()  # size in pixels
        new_width = (size[0] - bbx_width) / size[0]
        figure_area[2] = new_width - ((1-figure_area[2]) + figure_area[0])

    # now re-adjust all axes positions, assuming legend is upper right:
    figure_area_width = figure_area[2] - figure_area[0]
    figure_area_height = figure_area[3] - figure_area[1]
    for axs in axes.values():
        ax_pos = axs.get_position()
        position = [ax_pos.x0, ax_pos.y0, ax_pos.x0 + ax_pos.width,
                    ax_pos.y0+ax_pos.height]  # x0, y0, x1, y1
        # position is expressed in the old figure_area coordinates,
        # i.e. [0 0 1 1]. Convert to the new figure_area. with the classical
        # formula (example with position[0]):
        # pos = figure_area[0] + figure_area_width * (position[0] - 0) / (1- 0)

        # set x's:
        position[0] = figure_area[0] + position[0] * figure_area_width
        position[2] = figure_area[0] + position[2] * figure_area_width
        # set y's:
        position[1] = figure_area[1] + position[1] * figure_area_height
        position[3] = figure_area[1] + position[3] * figure_area_height

        # set new positions:
        axs.set_position([position[0], position[1], position[2]-position[0],
                         position[3] - position[1]])
    # same for annotations:
    for annot in annotations:
        xxx, yyy = annot.get_position()
        xxx = figure_area[0] + xxx * figure_area_width
        yyy = figure_area[1] + yyy * figure_area_height
        annot.set_position([xxx, yyy])

    return fig


def dimensions(obj, fig):
    '''
    Gets the size of an 'em' in display units and returns it

    :param obj: any matplotlib object, e.g. plt.text(0.5, 0.5, 'text')

    :return: a BBox object with the object window coordinates
    '''
    # we need to draw the canvas to make the obj.get_window_extent() work
    # This work only in non interactive backends
    # (for info, see https://matplotlib.org/3.1.1/tutorials/introductory/usage.html#backends)
    # There are several functions to be called according to the internet
    # (e.g., https://stackoverflow.com/a/36959454
    #  https://matplotlib.org/3.1.1/api/_as_gen/matplotlib.pyplot.draw.html)
    # but these two seem to work:
    fig.canvas.draw()
    fig.canvas.flush_events()
    rdr = fig.canvas.get_renderer()
    bbx = obj.get_window_extent(renderer=rdr)
    # print(str(bbx))  # in order to check that's not ([0, 0, 1, 1])
    return bbx


def draw_data(datadict, axes, converter):
    '''
    Draws plotly data (`datadict`) on the given matplotlib axes.
    Supports bar, filled areas, lines and scatter points (or both)

    :return: the drawn object, or None
    '''
    dpi = axes.get_figure().get_dpi()

    # set recognized options. These are dicts reflecting plotly Objects BUT
    # with the matplotlib value mapped to them. Later we will assign these
    # values to the matplotlib function arguments, renaming them if necessary:
    options = get_draw_options(datadict, converter, dpi)

    # now draw:
    if datadict['type'] == 'bar':
        return draw_bar(datadict, axes, options)

    if datadict['type'] == 'scatter':
        if '_prev_x' in datadict and '_prev_y' in datadict and \
                datadict.get('fill', '') == 'tonexty':
            return draw_filled_area(datadict, axes, options)

        return draw_line(datadict, axes, options)

    return None


def get_draw_options(datadict, converter, dpi):
    '''
    Returns a dict representing the plotly options for the objects to be
    drawn. Each key represents a plotly property, but its mapped to the
    matplotlib equivalent, or None to mean: no value set.
    Function using these options might need to rename some keys according to
    matplotlib functions arguments
    '''
    # we might use defaultdicts(lambda: None), but we prefer to write them
    # as dicts so that it is clear which arguments are expected to be supported
    # Also, we want to raise if we access some key not defined here for easy
    # debugging:
    marker = {
        'color': None,
        'size': None,
        'line': {
            'color': None,
            'width': None
        }
    }
    line = {
        'color': None,
        'width': None,
        'dash': None  # supports plotly 'dash' and 'dot' (defaults to 'solid')
    }
    # and put there the matplotlib values:
    if 'marker' in datadict:
        _marker = datadict['marker']
        if 'color' in _marker:
            marker['color'] = converter.color(_marker['color'])
        if 'size' in _marker:
            marker['size'] = converter.length(_marker['size'], dpi)
        if 'line' in _marker:
            _line = _marker['line']
            if 'color' in line:
                marker['line']['color'] = converter.color(_line['color'])
            marker['line']['width'] = \
                converter.length(_line.get('width', DEFAULT_LINEWIDTH), dpi)

    if 'line' in datadict:
        _line = datadict['line']
        if 'color' in _line:
            line['color'] = converter.color(_line['color'])
        if 'dash' in _line:
            if _line['dash'] == 'dash':
                line['dash'] = '--'
            elif _line['dash'] == 'dot':
                line['dash'] = ':'
        line['width'] = \
            converter.length(_line.get('width', DEFAULT_LINEWIDTH), dpi)

    return {
        'line': line,
        'marker': marker,
        'fillcolor': converter.color(datadict['fillcolor'])
        if 'fillcolor' in datadict else None
    }


def draw_bar(datadict, axes, options):
    '''
    Draws plotly data (`datadict`) as bars on the given matplotlib axes

    :param datadict: plotly data dict representing the data to be drawn
    :param axes: matplotlib axes object
    :param options: dict representing the plotly options retrieved from
        `datadict` and with values converted to matplotlib valid values.
        See :func:`get_draw_options`

    :return: the drawn object
    '''
    zipx = zip(datadict['x'][:-1], datadict['x'][1:])
    binw = np.min(np.abs([(first-second)
                          for first, second in zipx]))
    # setup matplotlib kwargs:
    marker = options['marker']
    kwargs = {}
    if marker['color'] is not None:
        kwargs['color'] = marker['color']
    if marker['line']['color'] is not None:
        kwargs['edgecolor'] = marker['line']['color']
    if marker['line']['width'] is not None:
        kwargs['linewidth'] = marker['line']['width']

    return axes.bar(datadict['x'], datadict['y'], width=binw, **kwargs)


def draw_filled_area(datadict, axes, options):
    '''
    Draws plotly data (`datadict`) as filled area on the given matplotlib axes

    :param datadict: plotly data dict representing the data to be drawn
    :param axes: matplotlib axes object
    :param options: dict representing the plotly options retrieved from
        `datadict` and with values converted to matplotlib valid values.
        See :func:`get_draw_options`

    :return: the drawn object
    '''
    # setup matplotlib kwargs:
    line = options['line']
    kwargs = {}
    if line['width'] is not None:
        kwargs['linewidth'] = line['width']
    # fill_between uses different param values, change them:
    if line['color'] is not None:
        kwargs['edgecolor'] = line['color']
    if options['fillcolor'] is not None:
        kwargs['color'] = options['fillcolor']

    # First three arguments are: x, y1, y2:
    # convert to numpy so that we have nans instead of none
    # (ax.fill_between complains otherwise:
    return axes.fill_between(np.array(datadict['x'], dtype=float),
                             np.array(datadict['_prev_y'], dtype=float),
                             np.array(datadict['y'], dtype=float),
                             **kwargs)


def draw_line(datadict, axes, options):
    '''
    Draws plotly data (`datadict`) as line or scatter points (or both)
    on the given matplotlib axes

    :param datadict: plotly data dict representing the data to be drawn
    :param axes: matplotlib axes object
    :param options: dict representing the plotly options retrieved from
        `datadict` and with values converted to matplotlib valid values.
        See :func:`get_draw_options`

    :return: the drawn object
    '''
    # setup matplotlib kwargs:
    line, marker = options['line'], options['marker']
    kwargs = {}
    if line['width'] is not None:
        kwargs['linewidth'] = line['width']
    if datadict['mode'] == 'markers':
        kwargs['linewidth'] = 0  # hide the line
        if marker['color'] is not None:
            kwargs['color'] = marker['color']
        # NOTE: there is a markerfacecolor in the doc but it does not work!
    elif datadict['mode'] == 'lines':
        kwargs['markersize'] = 0  # hide the markers
        if line['color'] is not None:
            kwargs['color'] = line['color']
    elif datadict['mode'] in ('lines+markers', 'markers+lines'):
        # which color to use? marker.color or line.color? use the first
        # given (not None), priority to line.color if both are given:
        linecolor, markercolor = \
            line.get('color', None), marker.get('color', None)
        if linecolor is not None:
            kwargs['color'] = linecolor
        elif markercolor is not None:
            kwargs['color'] = markercolor

    if datadict['mode'] in ('lines+markers', 'markers+lines', 'markers'):
        if marker['size'] is not None:
            kwargs['markersize'] = marker['size']
        # TODO: support for marker line, width and color. For the moment we
        # just support the marker bg color, and kwargs['color'] works for that.
        # But if we support marker line options we should see what to set as
        # marker bg color: I would say matplotlib's 'markerfacecolor' but it
        # does not work, maybe because we should set 'o' as marker
        # (see next line of code). Note also that the transparent bg color
        # for markers needs to be set to 'None' (string) in matplotlib (check)

        # defaults marker is None (hidden) in matplotlib, set it as the
        # circle (no other marker shape implemented yet):
        kwargs['marker'] = '.'
    elif datadict['mode'] in ('lines+markers', 'markers+lines', 'lines'):
        if line['dash'] is not None:
            kwargs['linestyle'] = line['dash']

    return axes.plot(datadict['x'], datadict['y'], **kwargs)[0]


if __name__ == '__main__':
    path = os.path.join(os.path.dirname(__file__), 'plottest')
    jsonfiles = [os.path.join(path, _) for _ in os.listdir(path)
                 if os.path.isfile(os.path.join(path, _))]
    outpath = os.path.join(path, 'results')
    for jsonf in jsonfiles:
        with open(jsonf, encoding='utf-8') as fp:
            jsondata = json.load(fp)
            for frmt in ['png', 'svg', 'eps', 'pdf']:
                val = get_img_buf(jsondata['data'], jsondata['layout'], 1295, 820,
                                  frmt)
                with open(os.path.join(outpath,
                                       os.path.basename(jsonf) + '.' + frmt),
                          'bw') as of:
                    of.write(val.getvalue())
    print('done')
    # plt.show()  # pylint: disable=missing-final-newline
