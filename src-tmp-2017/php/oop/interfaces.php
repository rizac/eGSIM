<?php
/** script to provide all interface definitions */

/** classes which implement this @interface can be executed from the frontend */
interface Executable
{
    public function exec();
}

/** classes which implement this @interface have content that is to be added to the page */
interface Printable
{
    /** echoes this @interface implementing @class 's content to the page */
    public function printout();
}

/** classes which implement this @interface store content for future use */
interface Storable
{
    /** stores @param $item */
    public function store($item);

    /** returns the stored $item */
    public function get();
}

?>
    