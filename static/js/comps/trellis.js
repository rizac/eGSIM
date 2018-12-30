/**
 * Registers globally a Vue component. The name of the component
 * (first argument of 'Vue.component' below must be equal to this file's name 
 * (without extension)
 */

// template for the trellis form
// Note the slot-scope 'self' which refers to the egsimform component
// (see related .js file for info)
_TEMPLATE_TRELLIS = `
<div class="flexible flex-direction-col" slot-scope="self">
    <div class="flexible flex-direction-row">
        <div class="flexible flex-direction-col">
            
            <!--<gsimselect class="flexible p-1 mb-4" name="gsim" showfilter="" v-bind:errormsg="formscope.fielderrors['gsim']" v-bind:avalgsims="avalGsims" v-bind:selectedgsims.sync="selectedGsims">
                Ground Shaking Intensity Model(s)
            </gsimselect>
            
            <imtselect class="p-1" name="imt" v-bind:errormsg="formscope.fielderrors['imt']" v-bind:avalgsims="avalGsims" v-bind:selectedgsims="selectedGsims" v-bind:avalimts="avalImts" v-bind:selectedimts.sync="selectedImts">
                Intensity Measure Type(s)
            </imtselect>-->
        
        </div>
        
        <div class="flex-direction-col flexible ml-4">
            <h5>Scenario configuration</h5>
            <div class="flexible form-control" style="overflow:auto; background-color:transparent">
                <div class="flexible p-1 grid-2-columns grid-col-gap-2 grid-row-gap-0">
                
                <!--<div v-for="(value, key) in self.form" v-if="!['gsim', 'imt', 'plot_type'].includes(key)">
                    {{ key }}: {{ value }}
                    <label for="'id_' + key">{{ key }}</label>
                    <span class="text-danger small text-nowrap">{{ value.err }}</span>
                    <input type="text" :name="key" v-model="value.val" class="form-control" required="" :id="'id_' + key">
                    <div class="text-muted small text-nowrap mb-2 field-help grid-col-span">{{ value.help }}</div>
                </div>-->
                
                
                <div>
                    <label for="id_magnitude">Magnitude(s)</label>
                    <span class="text-danger small text-nowrap">{{ self.form.magnitude.err }}</span>
                </div>
                <input type="text" name="magnitude" v-model="self.form.magnitude.val" class="form-control" required="" id="id_magnitude">
                <div class="text-muted small text-nowrap mb-2 field-help grid-col-span"></div>
        
                <div>
                    <label for="id_distance">Distance(s)</label>
                    <span class="text-danger small text-nowrap">{{ self.form.distance.err }}</span>
                </div>
                <input type="text" name="distance" v-model="self.form.distance.val" class="form-control" required="" id="id_distance"> 
                <div class="text-muted small text-nowrap mb-2 field-help grid-col-span"></div>
        
                <div>
                    <label for="id_dip">Dip</label>
                    <span class="text-danger small text-nowrap">{{ self.form.dip.err }}</span>
                </div>
                <input type="number" name="dip" v-model="self.form.dip.val" min="0.0" max="90.0" step="any" class="form-control" required="" id="id_dip"> 
                <div class="text-muted small text-nowrap mb-2 field-help grid-col-span"></div>
                
                <div>
                    <label for="id_aspect">Rupture Length / Width</label>
                    <span class="text-danger small text-nowrap">{{ self.form.aspect.err }}</span>
                </div>
                <input type="number" name="aspect" v-model="self.form.aspect.val" min="0.0" step="any" class="form-control" required="" id="id_aspect"> 
                <div class="text-muted small text-nowrap mb-2 field-help grid-col-span"></div>
                
                <div>
                    <label for="id_rake">Rake</label>
                    <span class="text-danger small text-nowrap">{{ self.form.rake.err }}</span>
                </div>
                <input type="number" name="rake" v-model="self.form.rake.val"  min="-180.0" max="180.0" step="any" class="form-control" required="" id="id_rake"> 
                <div class="text-muted small text-nowrap mb-2 field-help grid-col-span"></div>
                
                <div>
                    <label for="id_ztor">Top of Rupture Depth (km)</label>
                    <span class="text-danger small text-nowrap">{{ self.form.ztor.err }}</span>
                </div>
                <input type="number" name="ztor" v-model="self.form.rake.val"  min="0.0" step="any" class="form-control" required="" id="id_ztor"> 
                <div class="text-muted small text-nowrap mb-2 field-help grid-col-span"></div>
                
                <div>
                    <label for="id_strike">Strike</label>
                    <span class="text-danger small text-nowrap">{{ self.form.strike.err }}</span>
                </div>
                <input type="number" name="strike" v-model="self.form.strike.val"  min="0.0" max="360.0" step="any" class="form-control" required="" id="id_strike"> 
                <div class="text-muted small text-nowrap mb-2 field-help grid-col-span"></div>
        
                <div>
                    <label for="id_magnitude_scalerel">Magnitude Scaling Relation</label>
                    <span class="text-danger small text-nowrap">{{ self.form.magnitude_scalerel.err }}</span>
                </div>
                <select name="magnitude_scalerel" v-model="self.form.magnitude_scalerel.val" class="form-control" id="id_magnitude_scalerel">
                    <option value="CEUS2011">CEUS2011</option>
                    <option value="GSCCascadia">GSCCascadia</option>
                    <option value="GSCEISB">GSCEISB</option>
                    <option value="GSCEISI">GSCEISI</option>
                    <option value="GSCEISO">GSCEISO</option>
                    <option value="GSCOffshoreThrustsHGT">GSCOffshoreThrustsHGT</option>
                    <option value="GSCOffshoreThrustsWIN">GSCOffshoreThrustsWIN</option>
                    <option value="Leonard2014_Interplate">Leonard2014_Interplate</option>
                    <option value="Leonard2014_SCR">Leonard2014_SCR</option>
                    <option value="PeerMSR">PeerMSR</option>
                    <option value="PointMSR">PointMSR</option>
                    <option value="StrasserInterface">StrasserInterface</option>
                    <option value="StrasserIntraslab">StrasserIntraslab</option>
                    <option value="ThingbaijamInterface">ThingbaijamInterface</option>
                    <option value="WC1994" selected="">WC1994</option>
                    <option value="WC1994_QCSS">WC1994_QCSS</option>
                </select> 
                <div class="text-muted small text-nowrap mb-2 field-help grid-col-span"></div>
        
                <div>
                    <label for="id_initial_point">Location on Earth</label>
                    <span class="text-danger small text-nowrap">{{ self.form.initial_point.err }}</span>
                </div>
                <input type="text" name="initial_point" v-model="self.form.initial_point.val"  class="form-control" required="" id="id_initial_point"> 
                <div class="text-muted small text-nowrap mb-2 field-help grid-col-span">Longitude Latitude</div>
        
                <div>
                    <label for="id_hypocentre_location">Location of Hypocentre</label>
                    <span class="text-danger small text-nowrap">{{ self.form.hypocentre_location.err }}</span>
                </div>
                <input type="text" name="hypocentre_location" v-model="self.form.hypocentre_location.val" class="form-control" required="" id="id_hypocentre_location"> 
                <div class="text-muted small text-nowrap mb-2 field-help grid-col-span">Along-strike fraction, Down-dip fraction</div>
        
                <div>
                    <label for="id_vs30">V<sub>S30</sub> (m/s)</label>
                    <span class="text-danger small text-nowrap">{{ self.form.vs30.err }}</span>
                </div>
                <input type="text" name="vs30" v-model="self.form.vs30.val" class="form-control" required="" id="id_vs30"> 
                <div class="text-muted small text-nowrap mb-2 field-help grid-col-span"></div>
        
                <div>
                    <label for="id_vs30_measured">Is V<sub>S30</sub> measured?</label>
                    <span class="text-danger small text-nowrap">{{ self.form.vs30_measured.err }}</span>
                </div>
                <input type="checkbox" name="vs30_measured" v-model="self.form.vs30_measured.val" id="id_vs30_measured" checked="">
                <div class="text-muted small text-nowrap mb-2 field-help grid-col-span">Otherwise is inferred</div>
        
                <div>
                    <label for="id_line_azimuth">Azimuth of Comparison Line</label>
                    <span class="text-danger small text-nowrap">{{ self.form.line_azimuth.err }}</span>
                </div>
                <input type="number" name="line_azimuth" v-model="self.form.line_azimuth.val" min="0.0" max="360.0" step="any" class="form-control" required="" id="id_line_azimuth"> 
                <div class="text-muted small text-nowrap mb-2 field-help grid-col-span"></div>
        
                <div>
                    <label for="id_z1pt0">Depth to 1 km/s V<sub>S</sub> layer (m)</label>
                    <span class="text-danger small text-nowrap">{{ self.form.z1pt0.err }}</span>
                </div>
                <input type="text" name="z1pt0" v-model="self.form.z1pt0.val" class="form-control" id="id_z1pt0"> 
                <div class="text-muted small text-nowrap mb-2 field-help grid-col-span">
                    If not given, it will be calculated from the V<sub>S30</sub>
                </div>
        
                <div>
                    <label for="id_z2pt5">Depth to 2.5 km/s V<sub>S</sub> layer (km)</label>
                    <span class="text-danger small text-nowrap">{{ self.form.z2pt5.err }}</span>
                </div>
                <input type="text" name="z2pt5" v-model="self.form.z2pt5.val" class="form-control" id="id_z2pt5"> 
                <div class="text-muted small text-nowrap mb-2 field-help grid-col-span">
                    If not given, it will be calculated from the V<sub>S30</sub>
                </div>
        
                <div>
                    <label for="id_backarc">Backarc Path</label>
                    <span class="text-danger small text-nowrap">{{ self.form.backarc.err }}</span>
                </div> <input type="checkbox" v-model="self.form.backarc.val" name="backarc" id="id_backarc"> 
                <div class="text-muted small text-nowrap mb-2 field-help grid-col-span"></div>
            
                </div>
            </div>
        </div>
    </div>

    <div class="flex-direction-row mt-3">
        <label for="id_plot_type">Plot type</label>
        <select v-model="self.form.plot_type.val" class="form-control flexible mr-3 ml-1" size="4" name="plot_type" id="id_plot_type">
            <option value="d">IMT vs. Distance</option>
            <option value="m">IMT vs. Magnitude</option>
            <option value="s">Magnitude-Distance Spectra</option>
            <option value="ds">IMT vs. Distance (st.dev)</option>
            <option value="ms">IMT vs. Magnitude  (st.dev)</option>
            <option value="ss">Magnitude-Distance Spectra  (st.dev)</option>
        </select>
        <button type="submit" class="btn btn-outline-primary">
            Display plots
        </button>
    </div>

</div>
`

Vue.component('trellis', {
  //https://vuejs.org/v2/guide/components-props.html#Prop-Types:
  props: {
      form: Object,
      url: String
  },
  data: function () {
      return {
      }
  },
  template: `<egsimform class='flex-direction-col' :form='form' :url='url'>
      ${_TEMPLATE_TRELLIS}
  </egsimform>`
})