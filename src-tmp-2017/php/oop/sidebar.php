<?php
/** GMPE-Service
 * sidebar class
 * sets up a whole leaflet based map and
 * provides functions to set up a sidebar for the leaflet map
 * *******************************************************
 * req: http://leafletjs.com/
 * req: http://getbootstrap.com/javascript/      
 * req: https://github.com/Turbo87/sidebar-v2
 * req: http://fontawesome.io/icons/
*/

/** base sidebar @class 
 * adds @class Sidebar_entry entries to either the top or the bottom of the sidebar
 */
abstract class Sidebar_base implements Executable {

    /** FUNCTIONS */

    /** registers an entry to the sidebar that develops from top to bottom */
    abstract function register_entry_top($id, $icon, $local_value);

    /** registers an entry to the sidebar that develops from bottom to top */
    abstract function register_entry_bottom($id, $icon, $local_value);

    /** @returns an @class Sidebar_entry by it's id 
     * @param $id the entry's html id
     */
    abstract function entry($id);
    
    /* uses @field id_prefix + @param id_postfix to create and return an html id 
     * thus the prefix can be variable
     * if prefix is empty it just returns the postfix
     */
    function create_id($id_prefix, $id_postfix)
    {
        return (strcmp($id_prefix, "") === 0)? $id_postfix : $id_prefix . '_' . $id_postfix;
    }
}

/**
 * @function register_entry_top(html id, fontawesome css class, localizable string)
 * @function register_entry_bottom(html id, fontawesome css class, localizable string)
 * @function entry(html id)
 * @function exec(leaflet map id)
 */
class Sidebar extends Sidebar_base {

    /* arrays of @class sidebar_entry */
    private $top_entries, $bottom_entries;
    private $id_prefix = "";
    /* html ids that need to be accessed by JS */
    private $ids4js = array();

    /* ctr */
    function __construct($id_prefix = "")
    {
        $this->top_entries = array();
        $this->bottom_entries = array();
        $this->id_prefix = $id_prefix;
        /* save the prefix for later use in JS */
        if (strlen($id_prefix) > 0) { $this->add_id4js('prefix', $id_prefix); }
    }

    /* adds a top @class sidebar_entry to the array 
     * @params see @class sidebar_entry
     * @return the added entry
     */
    function register_entry_top($id, $icon, $local_value)
    {
        $entry = new Sidebar_entry($this, $id, $icon, $local_value);
        array_push( $this->top_entries, $entry );
        return $entry;
    }

    /* adds a bottom @class sidebar_entry to the array 
     * @params see @class sidebar_entry
     * @return the added entry
     */
    function register_entry_bottom($id, $icon, $local_value)
    {
        $entry = new Sidebar_entry($this, $id, $icon, $local_value);
        array_push($this->bottom_entries, $entry);
        return $entry;
    }

    /** @interface 
     * php @function echo'es the sidebar to the website 
     * @param $sidebar_id the id of the sidebar
     * @param $map_id the html id of the map to draw the sidebar onto
     */
    function exec($sidebar_id = "sidebar", $map_id = "map")
    {
        //$this->echo_ids_ref_4js($sidebar_id, $map_id);
        //echo '<body> <!-- body -->';
        
        //echo '<div id="'. $this->prefix().'_site_wrapper" class="row">';
        
        //echo '<nav id="gfz_gmpe_scrollspy" class="navbar navbar-inverse navbar-fixed-top" >';
        //echo '<ul class="nav navbar-nav">';
        //echo '<li class="dropdown">
        //         <a class="dropdown-toggle" data-toggle="dropdown" href="#">Projects
        //            <span class="caret"></span></a>
        //               <ul class="dropdown-menu">
        //                   <li><a href="#">SHARE</a></li>
        //                   <li><a href="#">D-PSHA-2016</a></li>
        //                   <li><a href="#">SED-2016</a></li>
        //                   <li><a href="#">SERA</a></li>
        //               </ul>
        //     </li>';
        //echo '<li><a href="#map">Map</a></li>';
        //echo '<li><a href="#data">Data</a></li>';
        //echo '</nav>';
        

        //$this->echo_modal($map_id, $sidebar_id);
        //$this->echo_upper_wrapper();
        //$this->echo_map_wrapper();
        //$this->echo_sidebar_topdiv($sidebar_id);

        /* echo the registered sidebar tabs content */
        //echo '<div class="sidebar-content">';
        //$this->echo_all_entries($this->top_entries);
        //$this->echo_all_entries($this->bottom_entries);
        //$this->echo_closing_div('/.sidebar-content');
        //$this->echo_closing_div('/.sidebar /#sidebar');
        /* add the map */
        //$this->echo_map_div($map_id);
        //$this->echo_closing_div('/#'.$this->prefix().'_map_wrapper');
        //echo '</div>';
        
        // FIXME uncomment when working!!
        //$this->echo_closing_div('/#'.$this->prefix().'_site_wrapper');
        /* ./body */
        //echo '</body><!-- /body -->';
    }
    
    /** GETTER */
    /** returns a @class sidebar_entry by it's html id */
    function entry($id)
    {
        foreach($this->top_entries as $entry) {
            if ( strcmp( $entry->id()->get(), parent::create_id($this->id_prefix, $id) ) === 0 ) return $entry;
        }
        foreach($this->bottom_entries as $entry) {
            if ( strcmp( $entry->id()->get(), parent::create_id($this->id_prefix, $id) ) === 0 ) return $entry;
        }
    }
    function prefix()
    {
        return $this->id_prefix;
    }

    /** SETTER */
    function add_id4js($key, $value)
    {
        $this->ids4js[$key] = $value;
    }
    
    /** PRIVATE FUNCTIONS */
    private function echo_comment($comment = "")
    {
        echo '<!-- '.$comment.' -->';
    }
    private function echo_closing_div($comment = "")
    {
        echo '</div><!-- '.$comment.' -->';
    }

    private function echo_upper_wrapper()
    {
        echo '<div id="map" class="container-fluid">';
    }
    
    private function echo_modal($map_id, $sidebar_id)
    {
        /*echo /*'<div class="side-menu" id="sideMenu">
                  <menu>
                       <ul class="nav nav-tabs nav-stacked">
                       <li><a href="#myModal" "data-backdrop="static" data-toggle="modal">Map</a>
                       </li>
                       </ul>
                 </menu>
           </div>*/
        /*
           '<div id="myModal" class="modal" >
              <div id="myModal" class="modal-dialog" role="document">
                  <div class="modal-content">
                      <div class="modal-header modal-frame-element">
                          <button type="button" class="close" data-dismiss="modal" aria-hidden="true">&times;</button>
                          <h4 class="modal-title">Map</h4>
                      </div>
                      <div class="modal-body container-fluid">
                         <div id="'.$this->prefix().'_map_wrapper" class="map_wrapper col-xs-12 col-sm-12 col-md-12 col-lg-12">
                             <!-- here be the map  --><div id="'.$this->create_id($this->id_prefix, $map_id).'_modal" class="sidebar-map"></div>
                         </div>
                     </div>
                     <div class="modal-footer modal-frame-element">
                        <button type="button" class="btn btn-default" data-dismiss="modal">Close</button>
                        <button type="button" class="btn btn-primary">Save changes</button>
                     </div>
                 </div> <!-- /.modal-content -->
             </div> <!-- /.modal-dialog -->
        </div> <!-- /.modal -->';
        */
    }
    
    private function echo_map_wrapper()
    {
        echo '<div id="'.$this->prefix().'_map_wrapper" class="map_wrapper col-xs-12 col-sm-12 col-md-12 col-lg-12">';
    }

    /** echoes a JS fn obj to the site that can be fetched by JS from window.ids
     * window.ids = {map:mapidname, sidebar:sidebaridname}
     */
    private function echo_ids_ref_4js($sidebar_id, $map_id)
    {
        echo '<script>/* sidebar and map id object */';
        echo 'function Ids(s,m){this._i={map:m,sidebar:s};}';
        echo 'Ids.prototype.get=function(){return this._i;};';
        echo 'var ids = new Ids("'.$this->create_id($this->id_prefix, $sidebar_id).'", "'.$this->create_id($this->id_prefix, $map_id).'");';
        foreach ($this->ids4js as $key => $value) {
            echo 'console.log("adding '.$key. ' => ' .$value.' to window.ids");';
            echo 'ids.'.$key. '="' .$value .'";';
        }
        echo '</script>';
    }

    /** echoes the sidebar div to the site 
     * the passed in sidebar id is appended to the registered site prefix (if exists)
     * @param $sidebar_id the id of the leaflet map
     */
    function echo_sidebar_topdiv($sidebar_id)
    {
        echo '<div id="'.$this->create_id($this->id_prefix, $sidebar_id).'" class="sidebar collapsed">';
        /* echo the registered sidebar menu tabs */
        echo '<div class="sidebar-tabs"><ul role="tablist">';
        foreach($this->top_entries as $entry) {
            echo '<li><a href="#' . $entry->id()->get() . '" role="tab"><i class="' . $entry->icon() . '"></i></a></li>';
        }
        echo '</ul>';
        echo '<ul role="tablist">';
        foreach($this->bottom_entries as $entry) {
            echo '<li><a href="#' . $entry->id()->get() . '" role="tab"><i class="' . $entry->icon() . '"></i></a></li>';
        }
        echo '</ul>';
        echo '</div><!-- /.sidebar-tabs -->';

    }

    /** echoes the map div to the site 
     * the passed in map id is appended to the registered site prefix (if exists)
     * @param $map_id the id of the leaflet map
     */
    private function echo_map_div($map_id)
    {
        echo '<!-- here be the map  --><div id="'.$this->create_id($this->id_prefix, $map_id).'" class="sidebar-map"></div>';
    }
    
    /** echoes a sidebar's entry header 
     * @param $value_local a localization conform value
     */
    private function echo_sidebar_content_header($value_local = "")
    {
        echo '<h1 class="sidebar-header"><span class="'.$this->prefix().'_localisation" value-local="'.$value_local.'"></span>
              <span class="sidebar-close"><i class="fa fa-caret-left"></i></span>
          </h1>';
    }

    /** echoes all @class sidebar_entry from a data structure 
     * @param $entries an array of @class sidebar_entry
     */
    private function echo_all_entries(Array $entries)
    {
        foreach($entries as $entry) {
            echo '<div class="sidebar-pane" id="' . $entry->id()->get() . '">';
            $this->echo_sidebar_content_header($entry->local_value());
            echo '<div id="'.$entry->id()->get().'_content_wrapper" class="col-xs-12 col-sm-12 col-md-12 col-lg-12">';
            /* content */
            foreach($entry->features() as $feature) {
                $feature->printout();
            }
            /* closing divs */
            echo '</div><!-- /#'.$entry->id()->get().'_content_wrapper --></div><!-- ./#'.$entry->id()->get().' /.sidebar-pane -->';
        }
    }
}

/* base datatype for this project */
abstract class Datatype_base implements Storable {
    
    public function store($item) {}

    public function get() {}
}

/** a single sidebar entry that consists of a menu entry and a content page for feature items 
 * @field $id an html id value of @class Id for future referencing
 * @field $icon a font-awesome conform css based icon, see: http://fontawesome.io/icons/
 * @field $local_value the localizable name of this entry
 * *************************************************
 * @param $sidebar the sidebar object to which this entry is associated
 * @param $id_postfix the html element's id without the prefix
 * @params $icon, $local_value see @fields $icon, local_value
 */
class Sidebar_entry extends Datatype_base {
    private $sidebar, $id, $icon, $local_value;
    private $features;

    /* ctr */
    function __construct(Sidebar $sidebar, $id_postfix, $icon, $local_value)
    {
        $this->sidebar = $sidebar;
        $this->id = new Id($sidebar, $id_postfix);
        $this->icon = $icon;
        $this->local_value = $local_value;
        $this->features = array();
    }

    /** SETTER */
    /* adds a new derived object of abstract @class Feature_base to this entry
     * and stores it in an array
     * @param $feature an object of a class that extends @class Feature_base
     */
    public function store($feature)
    {
        array_push($this->features, $feature);
    }

    /** GETTER */
    /* returns this features array */
    public function get()
    {
        return $this->features;
    }
    
    function sidebar()
    {
        return $this->sidebar;
    }
    
    /* returns the @class Id that is associated with this entry */
    function id()
    {
        return $this->id;
    }
    function icon()
    {
        return $this->icon;
    }
    function local_value()
    {
        return $this->local_value;
    }

    function features()
    {
        return $this->features;
    }
}

/** class to store id_prefix, id_postfix and id = id_prefix_id_postfix */
class Id extends Datatype_base {
    private $sidebar, $id_prefix, $id_postfix, $id;

    /* ctr */
    function __construct(Sidebar $sidebar, $postfix)
    {
        $this->sidebar = $sidebar;
        $this->_postfix2ids($postfix);
    }

    /* SETTER */
    public function store($postfix)
    {
        $this->_postfix2ids($postfix);
    }

    /* GETTER */
    public function get()
    {
        return $this->id;
    }
    
    protected function prefix($prefix = null)
    {
        if($prefix === null) {
            return $this->id_prefix;
        } else {
            $this->id_prefix = $prefix;
        }
    }

    protected function postfix($postfix = null)
    {
        if($postfix === null) {
            return $this->id_postfix;
        } else {
            $this->id_postfix = $postfix;
        }
    }

    /* takes an @param $postfix and sets @params $id_prefix, $id_postfix, $id of the class */
    private function _postfix2ids($postfix)
    {
        $this->id_prefix = $this->sidebar->prefix();
        $this->id_postfix = $postfix;
        $this->id = $this->sidebar->create_id($this->id_prefix, $this->id_postfix );
    }
}

/** base class for sidebar content feature elements 
 * @param $sidebar the @class Sidebar object to which this feature is associated 
 * @param $sidebar_pane the concrete pane in @param $sidebar to which this feature is to be added
 * @param $id an html id value for future referencing
 * @param $desc_local the localizable name of this entry
 */
abstract class Feature_base extends Datatype_base implements Printable {
    protected $entry, $id, $desc_local;

    /* ctr */
    function __construct(Sidebar_entry $entry, $id_postfix = "", $desc_local = "")
    {
        $this->entry = $entry;
        $this->id = new Id($entry->sidebar(), $id_postfix);
        $this->desc_local = $desc_local;
        //$sidebar->entry($sidebar_pane)->add_feature($this);
        $this->entry->store($this);
    }

    /* SETTER */

    public function store($item)
    {
        
    }
    
    /* GETTER */
    function sidebar()
    {
        return $this->entry->sidebar();
    }
    function id()
    {
        return $this->id;
    }
    function desc_local()
    {
        return $this->desc_local;
    }
        
    /* OTHER FUNCTIONS */
    
    /* @interface
     * adds this feature to the site 
     * must be called by the @class Sidebar
     */
    public function printout(){}

    /* echoes this feature wrapped in proper html tags 
     * @param $html_content the inner html content to add to this feature
     * this has to be realized by classes inheriting this class
     */
    protected function wrap($html_content = "")
    {
        $this->echo_html_top($this->desc_local);
        echo $html_content;
        echo '</div><!-- /.col --></div><!-- /.row --></div><!-- /#'.$this->id->get().' /.'.$this->entry->sidebar()->prefix().'_lower_elements_wrapper -->';
    }
    
    private function echo_html_top($desc_local = "")
    {
        /* TODO - do we need an id for this wrapper. do not add this->id as it will break toggles */
        echo '<div id="'.$this->id->get().'_wrapper" class="container-fluid '.$this->entry->sidebar()->prefix().'_lower_elements_wrapper">
                   <div class="row">
                   <div id="" class="col-xs-6 col-sm-6 col-md-6 col-lg-6">
                   <span class="'.$this->entry->sidebar()->prefix().'_localisation" value-local="'.$desc_local.'" style="float:left">
                   </span></div><!-- /.col --><div id="" class="col-xs-6 col-sm-6 col-md-6 col-lg-6">';
    }
}

/** a horizontal seperator */
class Feature_seperator extends Feature_base {
    /* this one is fixed to match the respective seperator css rule */
    private $id_postfix = 'seperator';
                        
    /* overwrite ctr
     * @param $html the html text to display
     */
    function __construct(Sidebar_entry $entry)
    {
        parent::__construct($entry, $this->id_postfix);
    }
    public function printout()
    {
        echo '<div class="'.$this->id->get().'"></div>';
    }
}

class Feature_plainhtml extends Feature_base {
    private $html;

    /* overwrite ctr
     * @param $html the html text to display
     */
    function __construct(Sidebar_entry $entry, $id_postfix, $html)
    {
        parent::__construct($entry, $id_postfix);
        $this->html = $html;
    }
    public function printout()
    {
        echo  '<div id="'.$this->id->get().'" class="container-fluid '.$this->entry->sidebar()->prefix().'_lower_elements_wrapper"><div class="row">
                   <div id="" class="col-xs-12 col-sm-12 col-md-12 col-lg-12">' . $this->html . '</div>
<!-- /.col --></div><!-- /.row --></div><!-- /#'.$this->id->get().' /#'.$this->entry->sidebar()->prefix().'_lower_elements_wrapper -->';
    }
}

/** creates a bootstrap toggle 
 * see: http://www.bootstraptoggle.com
 */
class Feature_toggle extends Feature_base {

    public function printout()
    {
        /* a sidebar toggle */
        $toggle = '<!-- checkbox toggle --><input id="'. parent::id()->get() .'" checked type="checkbox">';
        parent::wrap($toggle);
    }
}

/** creates a button 
 */
class Feature_button extends Feature_base {
    private $text_local;
    
    /* overwrite ctr
     * @param $text_local the localizable text to appear for this element
     */
    function __construct(Sidebar_entry $entry, $id_postfix, $desc_local, $text_local = "")
    {
        parent::__construct($entry, $id_postfix, $desc_local);
        $this->text_local = $text_local;
    }

    
    public function printout()
    {
        /* a sidebar toggle */
        $button = '<input id="'. parent::id()->get() .'" class="gfz_gmpe_localisation" value-local="'. $this->text_local .'" type="submit" value=""></input>';
        parent::wrap($button);
    }
}


/** plain text  */
class Feature_text extends Feature_base {
    private $text_local;

    /* overwrite ctr
     * @param $text_local the localizable text to appear for this element
     */
    function __construct(Sidebar_entry $entry, $id_postfix, $desc_local, $text_local = "")
    {
        parent::__construct($entry, $id_postfix, $desc_local);
        $this->text_local = $text_local;
    }
    
    public function printout()
    {
        parent::wrap('<p><span class="'.$this->sidebar()->prefix().'_localisation" value-local="' . $this->text_local . '"></span></p>');
    }
}

/** a dropfield to allow users to add (vector data) files to the site */ 
class Feature_dropfield extends Feature_base {
    /* file, submit and warning field appendixe */
    private $_file = '_file', $_submit = '_submit', $_warning = '_warning';
    /* file, submit and warning field ids */
    private $file_id, $submit_id, $warning_id;
    
    /* overwrite ctr */
    function __construct(Sidebar_entry $entry, $id_postfix, $desc_local = "")
    {
        parent::__construct($entry, $id_postfix, $desc_local);
        /* the actual field ids as prefix_userchosenid_appendix */
        $this->file_id = $this->id()->get() . $this->_file;
        $this->submit_id = $this->id()->get() . $this->_submit;
        $this->warning_id = $this->id()->get() . $this->_warning;
        /**/
        $entry->sidebar()->add_id4js($id_postfix, $this->id()->get());
    }

    public function printout()
    {
        $input = '<label for="input">Select a zipped shapefile:</label> <input type="file" id="'.$this->file_id.'"> <br>'.
                  '<input type="submit" id="'.$this->submit_id.'"> <span id="'.$this->warning_id.'"></span>';
        parent::wrap($input);
    }
}

?>
