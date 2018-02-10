/**
 * Implements the input selection to be shared across all controllers
 */

// difference between factory and .service: https://blog.thoughtram.io/angular/2015/07/07/service-vs-factory-once-and-for-all.html
ngApp.service('trellisData', function () {
	
	// sort of private variables:
	var _data = {};
	var _names = new SelSet();
	var _types = new SelSet(['mean', 'sigma']).select('mean')
	var _changed = false;
	
	return {
		// data = {'names': ['MagnitudeIMTs', 'DistanceIMTs', 'MagnitudeDistanceSpectra'],
        //		'data': {'sigma': 3*[{}], 'mean': 3*[{}]}}
		init(data) { // data needs to be a list of two-element arrays ['name', data], ['name', data]
			_data = data.data;
			var selName = _names.selItem;
			_names = new SelSet(data.names).select(selName);
			if(_names.selItem === undefined){
				_names.selItem = Array.from(data.names)[0];
			}
			this.changed=true;
		},
		get changed(){
			return _changed;
		},
		set changed(value){
			_changed = value;
		},
		selName: function(name){
			if (arguments.length){
				_names.selItem = name;
				this.changed=true;
			}else{
				return _names.selItem;
			}
		},
		
		selType: function(type){
			if (arguments.length){
				_types.selItem = type;
				this.changed=true;
			}else{
				return _types.selItem;
			}
		},
		
		get names(){
			return Array.from(_names);  // preverves ordering
		},
		
		get types(){
			return Array.from(_types);  // preverves ordering
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
			return _data[this.selType()][this.selName()];
		},
		
		get selPlotsData() {
		    var data = this.selData;
		    var xvalues = data['xvalues'];
		    var xlabel = data['xlabel'];
		    var layout={
		    		
		    };
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
		    		var layout = {
	//		    				  title: 'Title of the Graph',
		    			margin: {
		    				l: 70,  // default: 80
		    				r: 25,  // default: 80
		    				b: 50,  // default: 80 
		    				t: 20,  // default: 100. If provising titles, increase...
		    				pad: 1
		    			},
		    			showlegend: false,
					xaxis: {
					  title: xlabel
					},
					yaxis: {
					  title: element.ylabel
					}
		    		};
		    		return [traces, layout];
		    });
		}
	}
});