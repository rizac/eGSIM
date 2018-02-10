'''
Created on 9 Feb 2018

@author: riccardo
'''
import json
import os
import math

if __name__ == '__main__':
    dir_ = os.path.dirname(__file__)
    for f in os.listdir(dir_):
        path = os.path.join(dir_, f)
        if os.path.isfile(path) and os.path.splitext(f)[1] == '.json':
            with open(path) as fp:
                jsondict = json.load(fp)
                ylabel = jsondict.pop('ylabel', None)
                figures = jsondict['figures']
                num = int(math.ceil(math.sqrt(len(figures))))
                row, col = 0, 0
                newfigures = []
                if ylabel is None:
                    for name in list(figures.keys()):
                        r, c = 0, 0
                        if name != 'PGA':
                            col += 1
                            if col >= num:
                                col = 0
                                row += 1
                            r, c = row, col
                        figure_obj = figures.pop(name)
                        # fix bug with magnitude:
                        if ('yvalues' not in figure_obj):
                            figure_obj['yvalues'] = {}
                            for key in list(figure_obj.keys()):
                                if key not in ('ylabel', 'row', 'column', 'yvalues'):
                                    figure_obj['yvalues'][key] = figure_obj.pop(key)
                        
                        figure_obj['row'] = r
                        figure_obj['column'] = c
                        newfigures.append(figure_obj)
                    
                else:
                    newfigures = []
                    for name in list(figures.keys()):
                        figure_obj = figures.pop(name)
                        figure_obj['ylabel'] = ylabel
                        newfigures.append(figure_obj)
                jsondict['figures'] = newfigures
                h = 9
                with open(os.path.join(os.path.dirname(dir_), f), 'w') as fp2:
                    json.dump(jsondict, fp2)