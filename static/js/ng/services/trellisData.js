/**
 * Implements the input selection to be shared across all controllers
 */

// difference between factory and .service: https://blog.thoughtram.io/angular/2015/07/07/service-vs-factory-once-and-for-all.html
ngApp.service('trellisData', function () {

    return {
        names: new SelSet(),
        types: new SelSet(),
        changed: false,
        // data = {'names': ['MagnitudeIMTs', 'DistanceIMTs', 'MagnitudeDistanceSpectra'],
        // 'data': {'sigma': 3*[{}], 'mean': 3*[{}]}}
        init(data) { // data needs to be a list of two-element arrays ['name', data], ['name', data]
            this._data = data.data;
            var selRemainder = this.types.selection;
            this.types = new SelSet(['mean', 'sigma'])
            this.types.selection = selRemainder !== undefined ? selRemainder : 'mean';
            selRemainder = this.names.selection;
            this.names = new SelSet(data.names);
            this.names.selection = selRemainder !== undefined ? selRemainder : this.names.asArray[0];
            this.changed=true;
        },
        selName: function(name){
            if (arguments.length){
                this.names.selection = name;
                this.changed=true;
            }else{
                return this.names.selection;
            }
        },
        selType: function(type){
            if (arguments.length){
                this.types.selection = type;
                this.changed=true;
            }else{
                return this.types.selection;
            }
        },
        get selPlotsRowsCols(){
            let rows = 0;
            let cols=0;
            if (this.selData && this.selData.figures){
                this.selData.figures.forEach(function(element){
                    if(element.row > rows){
                        rows = element.row;
                    }
                    if(element.column> cols){
                        cols = element.column;
                    }
                });
            }
            return [rows+1, cols+1];
        },
        get selData(){
            return this._data ? this._data[this.selType()][this.selName()] : undefined;
        },
        get selPlotsData() {
            var data = this.selData;
            if (!data){
                return [];
            }
            var xvalues = data['xvalues'];
            var xlabel = data['xlabel'];
            var layout = {};
            return data.figures.map(function(element, index){
                var traces = [];
                var names = Object.keys(element.yvalues);
                var traces = names.map(function(name){
                    return {
                        x: xvalues,
                        y: element.yvalues[name],
                        mode: 'lines',
                        name: name
                    }
                });
                layout = {
                        //title: 'Title of the Graph',
                        font: {
                            // family: 'Courier New, monospace',
                            size: 10
                            // color: '#7f7f7f'
                        },
                        margin: {
                            l: 70,  // default: 80
                            r: 25,  // default: 80
                            b: 70,  // default: 80 
                            t: 20,  // default: 100. If provising titles, increase...
                            pad: 1
                        },
                        hovermode: 'closest',  // defaults 'y' ?
                        showlegend: false,
                        xaxis: {
                            title: xlabel,
                        },
                        yaxis: {
                            title: element.ylabel,
                            type: 'log'
                        }
                };
                return [traces, layout];
            });
        }
    }
});