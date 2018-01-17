<?php

/** GMPE-Service
 * Header class
 * echoes the header to the page
 */

class Header implements Executable {
    private $tags, $prefix, $value_local;
    
    function __construct($prefix, $value_local) {
        $this->prefix = $prefix;
        $this->value_local = $value_local;
        $this->tags = array();
    }

    /* adds a new @class Link to the header */
    public function add_link($url, $comment="")
    {
        array_push($this->tags, new Link($url, $comment));
    }

    /* adds a new @class Script to the header */
    public function add_script($url, $comment="")
    {
        $script = new Script($url, $comment);
        array_push($this->tags, $script);
        return $script;
    }

    /* adds a new @class Comment to the header */
    public function add_comment($comment)
    {
        array_push($this->tags, new Comment($comment));
    }
    
    /* @interface
     * echoes the header */
    public function exec()
    {
        echo '<head>';
        echo '<meta charset="utf-8">';
        echo '<meta http-equiv="X-UA-Compatible" content="IE=edge">';
        echo '<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />';
        echo '<title class="'.$this->prefix.'_localisation" value-local="'.$this->value_local.'"></title>';

        foreach($this->tags as $tag) {
            $tag->printout();
        }
        echo '</head>';
    }
}

class Header_element {
    private $target, $comment;

    function __construct($target, $comment = "")
    {
        $this->target = $target;
        $this->comment = $comment;
    }

    /* SETTER & GETTER */
    public function target($target=null)
    {
        if ($target === null) {
            return $this->target;
        } else {
            $this->target = $target;
        }
    }
    public function comment($comment=null)
    {
        if ($comment === null) {
            return '<!-- '.$this->comment.' -->';
        } else {
            $this->comment = $comment;
        }
        
    }
}

abstract class Tag implements Storable, Printable {
    protected $element;

    function __construct($target, $comment)
    {
        $this->element = new Header_element($target, $comment);
    }

    /** @interface */
    public function store($element)
    {
        $this->element = $element;
    }
    
    /** @interface 
     * needs to be implemented by the child class
     */
    public function printout()
    {
        echo $this->element->comment();
    }

    /** @interface */
    public function get()
    {
        return $this->element;
    }
}

class Link extends Tag {

    public function printout()
    {
        parent::printout();
        echo '<link rel="stylesheet" type="text/css" href="' .$this->get()->target(). '"></link>';
    }
    
}

class Script extends Tag {

    public function printout()
    {
        parent::printout();
        echo '<script type="text/javascript" src="' .$this->get()->target(). '"></script>';
    }

}

class Comment extends Tag {

    function __construct($target)
    {
        $this->element = new Header_element($target, "");
    }
    
    public function printout()
    {
        echo '<!-- ' .$this->get()->target(). ' -->';
    }
}

?>