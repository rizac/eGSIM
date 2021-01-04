"""
Flush the "egsim" database tables, i.e. empty all tables removing all rows.
Any other database structure is not affected.

Modified from the `flush` command in order to:
1. Empty only the Tables of the "egsim" app (i.e., those used by the API.
   See INSTALLED_APPS in the provided settings file)
2. Empty tables found on the database and not necessarily backed by a model.
   This should allow to successfully empty a database also in circumstances
   where `flush` would fail, i.e. after the models have been modified and
   before creating the relative migration file. Consider e.g. this case:
   Modify the models, adding a new non-nullable column C with no default. When
   creating the migration file (`manage.py makemigrations`), Django will asks
   how to fill C. No big deal, but why filling something that we are up to delete?
   (we will need to run `manage.py egsim_init` anyway after any migration)
   A better solution might be to run `egsim_flush` before making the migration

Usage:
```
export DJANGO_SETTINGS_MODULE="..."; python manage.py egsim_flush
```
"""
import re
from importlib import import_module
from itertools import chain
from typing import List, Sequence, Pattern

from django.apps import apps
from django.core.management.base import CommandError
from django.core.management.color import no_style
from django.core.management.sql import emit_post_migrate_signal
from django.db import DEFAULT_DB_ALIAS, connections, DatabaseError

# from django.db.backends.base.operations import BaseDatabaseOperations
# from django.db.backends.base.introspection import BaseDatabaseIntrospection
# from django.db.backends.sqlite3.introspection import BaseDatabaseIntrospection
from egsim.management.commands._utils import EgsimBaseCommand


class Command(EgsimBaseCommand):
    """Class implementing the command functionality"""

    # As help, use the module docstring (until the first empty line):
    help = globals()['__doc__'].split("\n\n")[0]

    # Command-specific options not defined by the argument parser:
    stealth_options = ('reset_sequences', 'allow_cascade', 'inhibit_post_migrate')
    # this is our stealth option 'appname' (maybe publicly settable in the future):
    appname_optname = 'appname'

    def add_arguments(self, parser):
        parser.add_argument(
            '--noinput', '--no-input', action='store_false', dest='interactive',
            help='Tells Django to NOT prompt the user for input of any kind.',
        )
        parser.add_argument(
            '--database', default=DEFAULT_DB_ALIAS,
            help='Nominates a database to flush. Defaults to the "default" database.',
        )
        parser.add_argument(
            '--tables', default='',
            help='Tables to flush (regular expression). Default "" (empty all tables)',
        )

    def handle(self, *args, **options):
        """Executes the command

        :param args: positional arguments (?). Unclear what should be given
            here. Django doc and Google did not provide much help, source code
            inspection suggests it is here for legacy code (OptParse)
        :param options: any argument (optional or positional), accessible
            as options[<paramname>]. For info see:
            https://docs.djangoproject.com/en/2.2/howto/custom-management-commands/
        """
        database = options['database']
        connection = connections[database]
        tables_re = options['tables']
        verbosity = options['verbosity']
        interactive = options['interactive']
        # The following are stealth options used by Django's internals.
        reset_sequences = options.get('reset_sequences', True)
        allow_cascade = options.get('allow_cascade', False)
        inhibit_post_migrate = options.get('inhibit_post_migrate', False)

        self.style = no_style()

        # this is our "stealth" option:
        appname = options.get(self.appname_optname, 'egsim')

        # Import the 'management' module within each installed app, to register
        # dispatcher events (legacy code from the 'flush' command)
        for app_config in apps.get_app_configs():
            if app_config.name != appname:  # ignore other apps:
                continue
            try:
                import_module('.management', app_config.name)
            except ImportError:
                pass
            break
        else:  # appname not found:
            raise CommandError(("\"%s\" is not a registered app, check "
                                "settings file") % appname)

        tnames = table_names(connection, only_django=False, app_names=[appname],
                             tbl_names=re.compile(tables_re) if tables_re else None)

        if not tnames:
            raise CommandError(('No table(s) found for app(s) %s. '
                                'Check the `tables` argument (if provided) and '
                                'that you created the database with '
                                'migration file(s)?') % str(appname))

        # Return a list of the SQL statements used to flush the database. Note:
        # If `only_django` is True, only include the table names that have
        # associated Django models and are in INSTALLED_APPS (we do NOT want
        # this:inspect the db - i.e. what is there - not the models)
        sql_list = sql_flush(self.style, connection, tnames,
                             reset_sequences=reset_sequences,
                             allow_cascade=allow_cascade)

        msg = "\n".join([
            "",
            "The following table(s) found in the database",
            "%r" % connection.settings_dict['NAME'],
            "will be IRREVERSIBLY returned to an empty state (all rows removed):",
            ""
        ])
        t_info = self.tables_info(connection, tnames)
        mxl = max(len(_) for _ in t_info)
        for tbl, row_count in t_info.items():
            msg += " %s (%s)\n" % (tbl.ljust(mxl), str(row_count))
        self.printsoftwarn(msg)

        # from here on, the code is almost equal to Django 'flush' command:

        if interactive:
            confirm = input("Are you sure you want to do this?" +
                            "\nType 'yes' to continue, or 'no' to cancel: ")
        else:
            confirm = 'yes'

        self.printinfo("")

        if confirm == 'yes':

            try:
                connection.ops.execute_sql_flush(database, sql_list)
            except Exception as exc:
                errtype, errmsg = str(exc.__class__.__name__), str(exc)
                if not errmsg:
                    errmsg = "no detail provided"
                raise CommandError(
                    "%s (%s).\n"
                    "Possible reasons:\n"
                    "  * The database isn't running or isn't configured correctly.\n"
                    "  * At least one of the expected database tables doesn't exist.\n"
                    "  * The following SQL was invalid: %s\n" %
                    (errtype, errmsg, " ".join(sql_list))
                ) from exc

            # Empty sql_list may signify an empty database and post_migrate
            # would then crash
            if sql_list and not inhibit_post_migrate:
                # Emit the post migrate signal. This allows individual applications to
                # respond as if the database had been migrated from scratch.
                emit_post_migrate_signal(verbosity, interactive, database)

            # print summary:
            self.printsuccess('Truncated tables:')
            for tbl, row_count in self.tables_info(connection, tnames).items():
                self.printsuccess(' %s (%s)' % (tbl, str(row_count)))

        else:
            self.stdout.write("Command cancelled.\n")


def table_names(connection, only_django=False,
                app_names: Sequence[str] = None,
                tbl_names: Pattern = None) -> List[str]:
    """Returns a list of table names

    :param connection: a database connection. E.g.
        ```
        from django.db import DEFAULT_DB_ALIAS, connections
        connection = connections[DEFAULT_DB_ALIAS]
        ```
    :param only_django: if True, only include the table names that have
        associated Django models
    :param app_names: list of strings of the apps (see INSTALLED_APPS)
        to search. None means: no filter (search all apps)
    :param tbl_names: regular expression to filter: matchin table names (using
        re.search) will be returned. None means no filter (all tables)
    """
    if only_django:
        tables = connection.introspection.django_table_names(only_existing=True,
                                                             include_views=False)
    else:
        tables = connection.introspection.table_names(include_views=False)

    if app_names is not None:
        tables = [t for t in tables if any(t.startswith(n+'_') for n in app_names)]

    if tbl_names is not None:
        tables = [t for t in tables if tbl_names.search(t)]

    return tables


# copied and modified from django.core.management.sql.sql_flush, with an optional
# app_names list of strings to filter tables from specific apps (Django names
# the tables as "<appname>_<modelname>")
def sql_flush(style, connection, tables: Sequence[str], reset_sequences=True,
              allow_cascade=False) -> List[str]:
    """Return a list of the SQL statements used to flush the database"""

    db_op = connection.ops  # db_op is a :class:`BaseDatabaseOperations`
    # (e.g. `django.db.backends.sqlite.operations.BaseDatabaseOperations`)

    db_op = get_db_operation(connection)  # see comment below
    # =========================================================================
    # TL/DR: REMOVE THE LINE ABOVE AND THIS COMMENT BLOCK IN DJANGO>=3
    # ------------------
    # Detailed explanation: In Django (2.2) `flush` command would now call:
    # ```
    # seqs = connection.introspection.sequence_list() if reset_sequences else ()
    # statements = connection.ops.sql_flush(style, tables, seqs, allow_cascade)
    # return statements
    # ```
    # where `connection.ops.sql_flush` does not actually use the `seqs` argument
    # for sqlite, so sequences reset is not supported for our current backend.
    # The solution for the moment is to copy/modify Django3 code (see
    # :func:`get_db_operation` for details. Upgrading Django would be easier but
    # we are bound to OpenQuake requirements) and call `db_op.sql_flush` instead
    # of `connection.ops.sql_flush`. Note that due to the new signature of
    # `sql_flush` (see below), we do not need anymore the `seqs` variable.
    # =========================================================================
    statements = db_op.sql_flush(style, tables,
                                 reset_sequences=reset_sequences,
                                 allow_cascade=allow_cascade)
    return statements


def tables_info(connection, tables):
    ret = {}
    with connection.cursor() as cursor:
        for tbl in tables:
            try:
                cursor.execute("SELECT COUNT(*) FROM " + str(tbl))
                row_count = str(cursor.fetchone()[0]) + " rows"
            except DatabaseError as _:
                row_count = 'unknown number of rows'
            ret[str(tbl)] = row_count
    return ret


# ===============================================================================
# Custom BaseDatabaseOperations (remove if using Django>=3)
# ================================================================================


def get_db_operation(connection) -> "BaseDatabaseOperations":
    """Return a :class:`django.db.backends.base.operations.DatabaseOperations`
    as implemented in Django3+, because this is required by our command.
    The function is used also to import "on demand", i.e. avoid useless imports
    for unused backend databases.
    (in principle, from Django3 onwards we can remove this function)
    """
    db_operations_class = None

    # connection.ops is a subclass of
    # django.db.backends.base.operations.BaseDatabaseOperations
    # we need to further subclass it, but first we need to know which subclass
    # is, importing only necessary modules. Hence let's use the module name:
    modname = connection.ops.__module__

    if '.postgresql.' in modname:

        from django.db.backends.postgresql import operations as postgres_op

        class _PostgresOperations(postgres_op.DatabaseOperations):
            """Subclasses Django Postgres DatabaseOperations Django3 compliant"""

            # https://github.com/django/django/blob/master/django/db/backends/postgresql/operations.py
            def sql_flush(self, style, tables, *, reset_sequences=False,
                          allow_cascade=False):
                if not tables:
                    return []

                # Perform a single SQL 'TRUNCATE x, y, z...;' statement. It allows us
                # to truncate tables referenced by a foreign key in any other table.
                sql_parts = [
                    style.SQL_KEYWORD('TRUNCATE'),
                    ', '.join(style.SQL_FIELD(self.quote_name(table)) for table in tables),
                ]
                if reset_sequences:
                    sql_parts.append(style.SQL_KEYWORD('RESTART IDENTITY'))
                if allow_cascade:
                    sql_parts.append(style.SQL_KEYWORD('CASCADE'))
                return ['%s;' % ' '.join(sql_parts)]

            # =============================================================#
            # The class methods used above are supposed to be the Django3  #
            # implementations, thus for safety copy them here:             #
            # =============================================================#

            def quote_name(self, name):
                if name.startswith('"') and name.endswith('"'):
                    return name  # Quoting once is enough.
                return '"%s"' % name

        db_operations_class = _PostgresOperations

    elif '.sqlite3.' in modname:

        from django.db.backends.sqlite3 import operations as sqlite_op
        from functools import lru_cache
        from django.utils.functional import cached_property

        class _SqliteOperations(sqlite_op.DatabaseOperations):
            """Subclasses Django Postgres DatabaseOperations Django3 compliant"""

            # https://github.com/django/django/blob/master/django/db/backends/sqlite/operations.py
            def sql_flush(self, style, tables, *, reset_sequences=False,
                          allow_cascade=False):
                if tables and allow_cascade:
                    # Simulate TRUNCATE CASCADE by recursively collecting the tables
                    # referencing the tables to be flushed.
                    tables = set(chain.from_iterable(
                        self._references_graph(table) for table in tables))
                sql = ['%s %s %s;' % (
                    style.SQL_KEYWORD('DELETE'),
                    style.SQL_KEYWORD('FROM'),
                    style.SQL_FIELD(self.quote_name(table))
                ) for table in tables]
                if reset_sequences:
                    sequences = [{'table': table} for table in tables]
                    sql.extend(self.sequence_reset_by_name_sql(style, sequences))
                return sql

            # =============================================================#
            # The class methods used above are supposed to be the Django3  #
            # implementations, thus for safety copy them here:             #
            # =============================================================#

            @cached_property
            def _references_graph(self):
                # 512 is large enough to fit the ~330 tables (as of this writing) in
                # Django's test suite.
                return lru_cache(maxsize=512)(self.__references_graph)

            def __references_graph(self, table_name):
                query = """
                WITH tables AS (
                    SELECT %s name
                    UNION
                    SELECT sqlite_master.name
                    FROM sqlite_master
                    JOIN tables ON (sql REGEXP %s || tables.name || %s)
                ) SELECT name FROM tables;
                """
                params = (
                    table_name,
                    r'(?i)\s+references\s+("|\')?',
                    r'("|\')?\s*\(',
                )
                with self.connection.cursor() as cursor:
                    results = cursor.execute(query, params)
                    return [row[0] for row in results.fetchall()]

            def quote_name(self, name):
                if name.startswith('"') and name.endswith('"'):
                    return name  # Quoting once is enough.
                return '"%s"' % name

            def sequence_reset_by_name_sql(self, style, sequences):
                if not sequences:
                    return []
                return [
                    '%s %s %s %s = 0 %s %s %s (%s);' % (
                        style.SQL_KEYWORD('UPDATE'),
                        style.SQL_TABLE(self.quote_name('sqlite_sequence')),
                        style.SQL_KEYWORD('SET'),
                        style.SQL_FIELD(self.quote_name('seq')),
                        style.SQL_KEYWORD('WHERE'),
                        style.SQL_FIELD(self.quote_name('name')),
                        style.SQL_KEYWORD('IN'),
                        ', '.join([
                            "'%s'" % sequence_info['table'] for sequence_info in sequences
                        ]),
                    ),
                ]

        db_operations_class = _SqliteOperations

    elif '.mysql.' in modname:

        from django.db.backends.mysql import operations as mysql_op

        class _MysqlOperations(mysql_op.DatabaseOperations):
            """Subclasses Django MySQL DatabaseOperations Django3 compliant"""

            # https://github.com/django/django/blob/master/django/db/backends/mysql/operations.py
            def sql_flush(self, style, tables, *, reset_sequences=False,
                          allow_cascade=False):
                if not tables:
                    return []

                sql = ['SET FOREIGN_KEY_CHECKS = 0;']
                if reset_sequences:
                    # It's faster to TRUNCATE tables that require a sequence reset
                    # since ALTER TABLE AUTO_INCREMENT is slower than TRUNCATE.
                    sql.extend(
                        '%s %s;' % (
                            style.SQL_KEYWORD('TRUNCATE'),
                            style.SQL_FIELD(self.quote_name(table_name)),
                        ) for table_name in tables
                    )
                else:
                    # Otherwise issue a simple DELETE since it's faster than TRUNCATE
                    # and preserves sequences.
                    sql.extend(
                        '%s %s %s;' % (
                            style.SQL_KEYWORD('DELETE'),
                            style.SQL_KEYWORD('FROM'),
                            style.SQL_FIELD(self.quote_name(table_name)),
                        ) for table_name in tables
                    )
                sql.append('SET FOREIGN_KEY_CHECKS = 1;')
                return sql

            # =============================================================#
            # The class methods used above are supposed to be the Django3  #
            # implementations, thus for safety copy them here:             #
            # =============================================================#

            def quote_name(self, name):
                if name.startswith("`") and name.endswith("`"):
                    return name  # Quoting once is enough.
                return "`%s`" % name

        db_operations_class = _MysqlOperations

    elif '.oracle.' in modname:

        from django.db.backends.oracle import operations as oracle_op
        from functools import lru_cache
        from django.utils.functional import cached_property
        from django.db.backends.utils import strip_quotes, truncate_name

        class _OracleOperations(oracle_op.DatabaseOperations):
            """Subclasses Django Oracle DatabaseOperations Django3 compliant"""

            # https://github.com/django/django/blob/master/django/db/backends/oracle/operations.py
            def sql_flush(self, style, tables, *, reset_sequences=False,
                          allow_cascade=False):
                if not tables:
                    return []

                truncated_tables = {table.upper() for table in tables}
                constraints = set()
                # Oracle's TRUNCATE CASCADE only works with ON DELETE CASCADE foreign
                # keys which Django doesn't define. Emulate the PostgreSQL behavior
                # which truncates all dependent tables by manually retrieving all
                # foreign key constraints and resolving dependencies.
                for table in tables:
                    for foreign_table, constraint in \
                            self._foreign_key_constraints(table,
                                                          recursive=allow_cascade):
                        if allow_cascade:
                            truncated_tables.add(foreign_table)
                        constraints.add((foreign_table, constraint))
                sql = [
                          '%s %s %s %s %s %s %s %s;' % (
                              style.SQL_KEYWORD('ALTER'),
                              style.SQL_KEYWORD('TABLE'),
                              style.SQL_FIELD(self.quote_name(table)),
                              style.SQL_KEYWORD('DISABLE'),
                              style.SQL_KEYWORD('CONSTRAINT'),
                              style.SQL_FIELD(self.quote_name(constraint)),
                              style.SQL_KEYWORD('KEEP'),
                              style.SQL_KEYWORD('INDEX'),
                          ) for table, constraint in constraints
                      ] + [
                          '%s %s %s;' % (
                              style.SQL_KEYWORD('TRUNCATE'),
                              style.SQL_KEYWORD('TABLE'),
                              style.SQL_FIELD(self.quote_name(table)),
                          ) for table in truncated_tables
                      ] + [
                          '%s %s %s %s %s %s;' % (
                              style.SQL_KEYWORD('ALTER'),
                              style.SQL_KEYWORD('TABLE'),
                              style.SQL_FIELD(self.quote_name(table)),
                              style.SQL_KEYWORD('ENABLE'),
                              style.SQL_KEYWORD('CONSTRAINT'),
                              style.SQL_FIELD(self.quote_name(constraint)),
                          ) for table, constraint in constraints
                      ]
                if reset_sequences:
                    sequences = [
                        sequence
                        for sequence in self.connection.introspection.sequence_list()
                        if sequence['table'].upper() in truncated_tables
                    ]
                    # Since we've just deleted all the rows, running our sequence ALTER
                    # code will reset the sequence to 0.
                    sql.extend(self.sequence_reset_by_name_sql(style, sequences))
                return sql

            # =============================================================#
            # The class methods used above are supposed to be the Django3  #
            # implementations, thus for safety copy them here:             #
            # =============================================================#

            @cached_property
            def _foreign_key_constraints(self):
                # 512 is large enough to fit the ~330 tables (as of this writing) in
                # Django's test suite.
                return lru_cache(maxsize=512)(self.__foreign_key_constraints)

            def __foreign_key_constraints(self, table_name, recursive):
                with self.connection.cursor() as cursor:
                    if recursive:
                        cursor.execute("""
                            SELECT
                                user_tables.table_name, rcons.constraint_name
                            FROM
                                user_tables
                            JOIN
                                user_constraints cons
                                ON (user_tables.table_name = cons.table_name AND cons.constraint_type = ANY('P', 'U'))
                            LEFT JOIN
                                user_constraints rcons
                                ON (user_tables.table_name = rcons.table_name AND rcons.constraint_type = 'R')
                            START WITH user_tables.table_name = UPPER(%s)
                            CONNECT BY NOCYCLE PRIOR cons.constraint_name = rcons.r_constraint_name
                            GROUP BY
                                user_tables.table_name, rcons.constraint_name
                            HAVING user_tables.table_name != UPPER(%s)
                            ORDER BY MAX(level) DESC
                        """, (table_name, table_name))
                    else:
                        cursor.execute("""
                            SELECT
                                cons.table_name, cons.constraint_name
                            FROM
                                user_constraints cons
                            WHERE
                                cons.constraint_type = 'R'
                                AND cons.table_name = UPPER(%s)
                        """, (table_name,))
                    return cursor.fetchall()

            def quote_name(self, name):
                # SQL92 requires delimited (quoted) names to be case-sensitive.  When
                # not quoted, Oracle has case-insensitive behavior for identifiers, but
                # always defaults to uppercase.
                # We simplify things by making Oracle identifiers always uppercase.
                if not name.startswith('"') and not name.endswith('"'):
                    name = '"%s"' % truncate_name(name.upper(), self.max_name_length())
                # Oracle puts the query text into a (query % args) construct, so % signs
                # in names need to be escaped. The '%%' will be collapsed back to '%' at
                # that stage so we aren't really making the name longer here.
                name = name.replace('%', '%%')
                return name.upper()

            def sequence_reset_by_name_sql(self, style, sequences):
                sql = []
                for sequence_info in sequences:
                    no_autofield_sequence_name = self._get_no_autofield_sequence_name(
                        sequence_info['table'])
                    table = self.quote_name(sequence_info['table'])
                    column = self.quote_name(sequence_info['column'] or 'id')
                    query = self._sequence_reset_sql % {
                        'no_autofield_sequence_name': no_autofield_sequence_name,
                        'table': table,
                        'column': column,
                        'table_name': strip_quotes(table),
                        'column_name': strip_quotes(column),
                    }
                    sql.append(query)
                return sql

        db_operations_class = _OracleOperations

    if db_operations_class is None:
        raise CommandError('Db system "%s" unknown (supported are: '
                           'sqlite3, postgresql, mysql, oracle).' %
                           str(connection.ops.__class__))

    return db_operations_class(connection)
