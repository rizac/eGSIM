This directory contains the Django custom commands of eGSIM (for info see
https://docs.djangoproject.com/en/2.2/howto/custom-management-commands/.
To see all Django commands type on the terminal `python manage.py --help`).

Custom commands are basically admin operation done once in a while when
(re)initializing the Django database with external data (e.g. OpenQuake
entities, Area source models and relative Gsim selection, Flatfiles)

Implementation details for new custom commands
==============================================

Create a new module in this directory (not starting with the underscore:
starting underscore tells Django "I am not a custom command").

Requirements:

1. The module name (without ".py" extension) must be the command name
   (i.e. the name you would type after `python manage.py`)

2. The module must implement a subclass of `_utils.EgsimBaseCommand`.
   `EgsimBaseCommand` is just a subclass of Django `BaseCommand` with some
   shorthand utilities (see implementation in `_utils.py` for details).
   For further details see here:
   https://docs.djangoproject.com/en/2.1/howto/custom-management-commands/

3. (optional) if the command requires external (and not huge) data, write a
   directory under '_data' with the same name as the command name. Put therein
   whatever you need (and organized as you want) for the functionality of
   your command. Pay attention to avoid committing large files

Final note: the parent directory "data" needs to start with an underscore to let
Django recognize it as non-command inside 'management/commands'
(https://docs.djangoproject.com/en/2.1/howto/custom-management-commands/)
