/**
 * Registers globally a Vue component. The name of the component
 * (first argument of 'Vue.component' below must be equal to this file's name 
 * (without extension)
 */

_TEMPLATE_TRELLIS = `
<div class="flexible flex-direction-col" slot-scope="formscope">
    <div class="flexible flex-direction-row">
        <div class="flexible flex-direction-col">
            
            <gsimselect class="flexible p-1 mb-4" name="gsim" showfilter="" v-bind:errormsg="formscope.fielderrors['gsim']" v-bind:avalgsims="avalGsims" v-bind:selectedgsims.sync="selectedGsims">
                Ground Shaking Intensity Model(s)
            </gsimselect>
            
            <imtselect class="p-1" name="imt" v-bind:errormsg="formscope.fielderrors['imt']" v-bind:avalgsims="avalGsims" v-bind:selectedgsims="selectedGsims" v-bind:avalimts="avalImts" v-bind:selectedimts.sync="selectedImts">
                Intensity Measure Type(s)
            </imtselect>
        
        </div>
        
        <div class="flex-direction-col flexible ml-4">
            <h5>Scenario configuration</h5>
            <div class="flexible form-control" style="overflow:auto; background-color:transparent">
                <div class="flexible p-1 grid-2-columns grid-col-gap-2 grid-row-gap-0">
                
                <div>
                    <label for="id_magnitude">Magnitude(s)</label>
                    <errorspan :text="formscope.fielderrors['magnitude']"></errorspan>
                </div>
                <input type="text" name="magnitude" class="form-control" required="" id="id_magnitude">
                <div class="text-muted small text-nowrap mb-2 field-help grid-col-span"></div>
        
                <div>
                    <label for="id_distance">Distance(s)</label>
                    <errorspan :text="formscope.fielderrors['distance']"></errorspan>
                </div>
                <input type="text" name="distance" class="form-control" required="" id="id_distance"> 
                <div class="text-muted small text-nowrap mb-2 field-help grid-col-span"></div>
        
                <div>
                    <label for="id_dip">Dip</label>
                    <errorspan :text="formscope.fielderrors['dip']"></errorspan>
                </div>
                <input type="number" name="dip" min="0.0" max="90.0" step="any" class="form-control" required="" id="id_dip"> 
                <div class="text-muted small text-nowrap mb-2 field-help grid-col-span"></div>
                
                <div>
                    <label for="id_aspect">Rupture Length / Width</label>
                    <errorspan :text="formscope.fielderrors['aspect']"></errorspan>
                </div>
                <input type="number" name="aspect" min="0.0" step="any" class="form-control" required="" id="id_aspect"> 
                <div class="text-muted small text-nowrap mb-2 field-help grid-col-span"></div>
                
                <div>
                    <label for="id_rake">Rake</label>
                    <errorspan :text="formscope.fielderrors['rake']"></errorspan>
                </div>
                <input type="number" name="rake" value="0.0" min="-180.0" max="180.0" step="any" class="form-control" required="" id="id_rake"> 
                <div class="text-muted small text-nowrap mb-2 field-help grid-col-span"></div>
                
                <div>
                    <label for="id_ztor">Top of Rupture Depth (km)</label>
                    <errorspan :text="formscope.fielderrors['ztor']"></errorspan>
                </div>
                <input type="number" name="ztor" value="0.0" min="0.0" step="any" class="form-control" required="" id="id_ztor"> 
                <div class="text-muted small text-nowrap mb-2 field-help grid-col-span"></div>
                
                <div>
                    <label for="id_strike">Strike</label>
                    <errorspan :text="formscope.fielderrors['strike']"></errorspan>
                </div>
                <input type="number" name="strike" value="0.0" min="0.0" max="360.0" step="any" class="form-control" required="" id="id_strike"> 
                <div class="text-muted small text-nowrap mb-2 field-help grid-col-span"></div>
        
                <div>
                    <label for="id_magnitude_scalerel">Magnitude Scaling Relation</label>
                    <errorspan :text="formscope.fielderrors['magnitude_scalerel']"></errorspan>
                </div>
                <select name="magnitude_scalerel" class="form-control" id="id_magnitude_scalerel">
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
                    <errorspan :text="formscope.fielderrors['initial_point']"></errorspan>
                </div>
                <input type="text" name="initial_point" value="0 0" class="form-control" required="" id="id_initial_point"> 
                <div class="text-muted small text-nowrap mb-2 field-help grid-col-span">Longitude Latitude</div>
        
                <div>
                    <label for="id_hypocentre_location">Location of Hypocentre</label>
                    <errorspan :text="formscope.fielderrors['hypocentre_location']"></errorspan>
                </div>
                <input type="text" name="hypocentre_location" value="0.5 0.5" class="form-control" required="" id="id_hypocentre_location"> 
                <div class="text-muted small text-nowrap mb-2 field-help grid-col-span">Along-strike fraction, Down-dip fraction</div>
        
                <div>
                    <label for="id_vs30">V<sub>S30</sub> (m/s)</label>
                    <errorspan :text="formscope.fielderrors['vs30']"></errorspan>
                </div>
                <input type="text" name="vs30" value="760.0" class="form-control" required="" id="id_vs30"> 
                <div class="text-muted small text-nowrap mb-2 field-help grid-col-span"></div>
        
                <div>
                    <label for="id_vs30_measured">Is V<sub>S30</sub> measured?</label>
                    <errorspan :text="formscope.fielderrors['vs30_measured']"></errorspan>
                </div>
                <input type="checkbox" name="vs30_measured" id="id_vs30_measured" checked="">
                <div class="text-muted small text-nowrap mb-2 field-help grid-col-span">Otherwise is inferred</div>
        
                <div>
                    <label for="id_line_azimuth">Azimuth of Comparison Line</label>
                    <errorspan :text="formscope.fielderrors['line_azimuth']"></errorspan>
                </div>
                <input type="number" name="line_azimuth" value="0.0" min="0.0" max="360.0" step="any" class="form-control" required="" id="id_line_azimuth"> 
                <div class="text-muted small text-nowrap mb-2 field-help grid-col-span"></div>
        
                <div>
                    <label for="id_z1pt0">Depth to 1 km/s V<sub>S</sub> layer (m)</label>
                    <errorspan :text="formscope.fielderrors['z1pt0']"></errorspan>
                </div>
                <input type="text" name="z1pt0" class="form-control" id="id_z1pt0"> 
                <div class="text-muted small text-nowrap mb-2 field-help grid-col-span">
                    If not given, it will be calculated from the V<sub>S30</sub>
                </div>
        
                <div>
                    <label for="id_z2pt5">Depth to 2.5 km/s V<sub>S</sub> layer (km)</label>
                    <errorspan :text="formscope.fielderrors['z2pt5']"></errorspan>
                </div>
                <input type="text" name="z2pt5" class="form-control" id="id_z2pt5"> 
                <div class="text-muted small text-nowrap mb-2 field-help grid-col-span">
                    If not given, it will be calculated from the V<sub>S30</sub>
                </div>
        
                <div>
                    <label for="id_backarc">Backarc Path</label>
                    <errorspan :text="formscope.fielderrors['backarc']"></errorspan>
                </div> <input type="checkbox" name="backarc" id="id_backarc"> 
                <div class="text-muted small text-nowrap mb-2 field-help grid-col-span"></div>
            
                </div>
            </div>
        </div>
    </div>

    <div class="flex-direction-row mt-3">
        <!-- the submit button is the plot_type field. Render manually -->
        <label for="id_plot_type">Plot type</label>
        <select class="form-control flexible mr-3 ml-1" size="4" name="plot_type" id="id_plot_type">
            
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
      <div slot-scope='self'>
      {{ self.form }}
      </div>
  </egsimform>`
})

/**
* <div class='flexible flex-direction-col' slot-scope='parent'>
* 
*  </div>
*/