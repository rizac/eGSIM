<?php

/* DB access class: 
 * creates mysql DB connection
 * and provides DB query functions
 */

/* config file - not needed, we include it from the calling php script */

class Database {
    private $mysqli, $section, $last_result;

    /* ctor */
    function __construct($section/*, $sql*/)
    {
        $this->section = $section;
        //$this->sql = $sql;
        $this->mysqli = array();
        $this->last_result = "";

        if (!isset($this->mysqli[$this->section])) {
            $config = parse_ini_file(CONN_FILE_PATH, 1);
            // pass the db conn info in a section of the config file. 
            $this->mysqli[$this->section] = new mysqli($config[$this->section]['hostname'],
                                                       $config[$this->section]['username'],
                                                       $config[$this->section]['password'],
                                                       $config[$this->section]['database']);
        }
        if ($this->mysqli[$this->section]->connect_errno) {
            die( "Failed to connect to MySQL: (" . $this->mysqli[$this->section]->connect_errno . ") " . $this->mysqli[$this->section]->connect_error );
        } else {
            $this->mysqli[$this->section]->set_charset('utf8');
        }
    }
    
    /*
     * Utility function to automatically bind columns from selects in prepared statements to 
     * an array
     * see: https://gunjanpatidar.wordpress.com/2010/10/03/bind_result-to-array-with-mysqli-prepared-statements/
     */
    private function _bind_result_array($stmt)
    {
        $meta = $stmt->result_metadata();
        $result = array();
        while ($field = $meta->fetch_field()) {
            $result[$field->name] = NULL;
            $params[] = &$result[$field->name];
        }
        call_user_func_array(array($stmt, 'bind_result'), $params);
        return $result;
    }

    /**
     * Returns a copy of an array of references
     */
    private function _getCopy($row)
    {
        return array_map(create_function('$a', 'return $a;'), $row);
    }

    /** performs db query
     * @param $tables
     * @param $columns
     */
    function query_db($tables, $columns)
    {
        //clearstatcache(); // clear cached file_exists information
        $mysqli = $this->mysqli[$this->section];
        $result = '';
        /* remove leading and trailing ` characters from table names */
        $pattern = "/^`?(.+?)`?$/";
        /* construct select statement */
        $select = 'SELECT ' . $columns[0];
        unset($columns[0]);
        foreach($columns as $column) {
            $select .= ', ' . $column;
        }
        $select .= ' FROM ';
        
        foreach($tables as $table) {
            preg_match( $pattern, $table, $re );
            $sql = $select . $table; //." WHERE XY_ID=?";
            
            /* Prepare statement */
            if (!($stmt = $mysqli->prepare($sql))) {
                die( "Prepare failed: (" . $mysqli->errno . ") " . $mysqli->error );
            }

            //$stmt->bind_param( 'i', $id );
            $stmt->execute();
            //$stmt->store_result(); // need store_result here - see: http://stackoverflow.com/q/10335278
            
            $row = $this->_bind_result_array($stmt);
            if(!$stmt->error) {
                $i = 0;
                while ($stmt->fetch()) {
                    $result[$re[1]][$i] = $this->_getCopy($row);
                    ++$i;
                }
            }
            $stmt->free_result();
            $stmt->close();
        }
        $this->last_result = $result;
        return $result;
    }

    /* json encoded the last query result to a JS variable
     * @param $object_name the name of the JS variable to set the last result to
     */
    function to_js_object($object_name='dbresult')
    {
        //echo '<script>';
        return /*'var '.$object_name.'='.json_encode(*/$this->last_result/*).';'*/;
        //echo '</script>';
    }
    
}

?>