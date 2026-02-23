"""eGSIM management command to edit the DB"""

from datetime import datetime
from typing import Callable, Any
import shlex

from django.core.management import BaseCommand
from django.db import DatabaseError
from django.db.models import (QuerySet, Model,
                              Field, CharField, IntegerField, DateField, FloatField,
                              DateTimeField, TextField, BooleanField, SmallIntegerField,
                              PositiveIntegerField, ForeignKey)

from egsim.api import models


class Command(BaseCommand):
    help = """Interactive Django command to modify eGSIM table content. 
    Particularly useful to 
    quickly hide/show items in the web API
    """

    def handle(self, *args, **options):
        """Execute the command"""

        self.stdout.write(self.style.ERROR('Scanning Db tables...'))
        tables = {}
        for key in dir(models):
            try:
                cls = getattr(models, key)
                if (
                    models.__name__ == cls.__module__ and
                    issubclass(cls, models.EgsimDbModel) and
                    not cls._meta.abstract
                ):
                    tables[key.lower()] = cls
            except Exception:  # noqa
                pass
        db_model: Model | None = None
        queryset = None
        resp = None
        while resp != self.quit:
            if db_model is None:
                db_model, resp = self.select_db_model(tables)  # noqa
            elif queryset is None:
                queryset, resp = self.select_db_instances(db_model)
                if resp == self.back:
                    db_model = None
            else:
                resp = self.update_db_instance(queryset)
                if resp == self.back:
                    queryset = None
        self.stdout.write(self.style.ERROR('Command terminated'))

    quit = 'q'
    back = '<'
    help = '?'  # noqa
    suffix = {'h': f'{help}: help', 'q': f'{quit}: quit', 'b': f'{back}: go back'}

    def select_db_model(self, tables: dict[str, Model]) -> tuple[Model | None, str]:
        """Return (DbModel or None, aborted)"""

        self.stdout.write(f'{len(tables)} table(s): ' +
                          self.style.WARNING(" ".join(tables)))
        while True:
            msg = f'UPDATE [TABLE] ({self.suffix["q"]}): '
            res = input(msg)
            if res == self.quit:
                return None, res
            if res not in tables:
                self.stdout.write(self.style.ERROR('No matching table'))
            else:
                self.print_table(tables[res].objects)  # noqa
                return tables[res], res

    def parse_field_and_value(
        self,
        db_model: Model,
        input_result, *,
        allow_pkey=False,
        allow_editable=False,
        allow_fkey=False
    ) -> tuple[Field | None, Any | None, str]:
        """Return (Field, user_input)"""

        fields = {
            f.name: f for f in db_model._meta.get_fields()  # noqa
            if f.__class__ in self.f_types
        }
        resp = input_result.strip()
        if resp in {self.quit, self.back, self.help}:
            return None, None, resp
        try:
            resp = shlex.split(resp)
        except ValueError as sh_err:
            self.stdout.write(self.style.ERROR(str(sh_err)))
            return None, None, input_result

        if len(resp) != 2:
            self.stdout.write(self.style.ERROR(f'Type [column] [value] '
                                               f'(space-separated)'))
            return None, None, input_result

        res = resp[0]
        if res not in fields:
            self.stdout.write(self.style.ERROR(f'No matching column: "{res}"'))
        elif fields[res].primary_key and not allow_pkey:
            self.stdout.write(self.style.ERROR(f'"{res}" is a primary '
                                               f'key column'))
        elif not fields[res].editable and not allow_editable:
            self.stdout.write(self.style.ERROR(f'"{res}" is not editable'))
        elif isinstance(fields[res], ForeignKey) and not allow_fkey:
            self.stdout.write(self.style.ERROR(f'"{res}" is a foreign key column'))
        else:
            field = fields[res]
            f_type = self.f_types.get(field.__class__)
            if f_type is None:
                self.stdout.write(self.style.ERROR(f'Unsupported type for '
                                                   f'"{field.name}": '
                                                   f'{field.__class__.__name__}'))
            res = resp[1]
            try:
                val = self.f_types[field.__class__](res)
                return field, val, input_result
            except Exception as exc:  # noqa
                self.stdout.write(self.style.ERROR(f'Invalid value "{res}": {str(exc)}'))
                return None, None, input_result

        return None, None, input_result

    def select_db_instances(self, db_model: Model) -> tuple[QuerySet | None, str]:
        """Return (QuerySet, user_input)"""

        while True:
            msg = (
                f'WHERE [COLUMN] [VALUE] ' 
                f'({self.suffix["h"]}, {self.suffix["q"]}, {self.suffix["b"]}): '
            )
            field, val, resp = self.parse_field_and_value(db_model, input(msg))
            if resp == self.help:
                self.stdout.write('type a column and a value (space separated) '
                                  'that will be used to select matching rows. '
                                  'If the columns is a text type, '
                                  'value can be a regexp. Date-times must be typed '
                                  'ISO-formatted, boolean can be lower case or 0, 1. '
                                  'Examples: "hidden true", "hidden 0", "name ^ab.*"')
                continue
            elif resp in {self.quit, self.back}:
                return None, resp
            elif field is None or val is None:
                continue

            field_name = field.name
            if field.__class__ in {TextField, CharField}:
                field_name += '__iregex'  # use regexp (search, no match)
            queryset = db_model.objects.filter(**{field_name: val})  # noqa
            if queryset.count() == 0:
                self.stdout.write(self.style.ERROR('No matching row'))
            else:
                self.stdout.write('Matching table row(s): ')
                self.print_table(queryset, fields=['id', 'name', field.name])
                return queryset, resp

    def update_db_instance(self, queryset: QuerySet) -> str:
        """Return user_input"""

        while True:
            msg = (
                f'SET [COLUMN] [NEW VALUE] ' 
                f'({self.suffix["h"]}, {self.suffix["q"]}, {self.suffix["b"]}): '
            )
            field, val, resp = self.parse_field_and_value(queryset.model,
                                                          input(msg))
            if resp == self.help:
                self.stdout.write('type a column and a new value (space separated) '
                                  'to update the column value of all matching rows. '
                                  'If the columns is a boolean type, the new value '
                                  'can be "toggle" to switch old value, row-wise. '
                                  'Examples: "hidden toggle"')
                continue
            elif resp in {self.quit, self.back}:
                return resp
            elif field is None or val is None:
                continue

            try:
                count = queryset.count()
                if field.__class__ == BooleanField and val == 'toggle':
                    true_ids = [_.id for _ in queryset.filter(**{field.name: True})]
                    queryset.filter(id__in=true_ids).update(**{field.name: False})
                    queryset.exclude(id__in=true_ids).update(**{field.name: True})
                    # update res to display as message below:
                    val = 'true if the value was false, and false if it was true'
                else:
                    queryset.update(**{field.name: val})
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully updated "{field.name}" '
                        f'in {count} row(s) '
                        f'(new value: {str(val)})'
                    )
                )
                return input(f'What now? ({self.suffix["q"]}, {self.suffix["b"]}): ')
            except DatabaseError as db_err:
                self.stdout.write(self.style.ERROR(f'{str(db_err)}'))

    f_types: dict[type[Field], Callable] = {
        CharField: lambda v: str(v),
        TextField: lambda v: str(v),
        IntegerField: lambda v: int(v),
        PositiveIntegerField: lambda v: int(v),
        SmallIntegerField: lambda v: int(v),
        FloatField: lambda v: float(v),
        BooleanField: lambda v: {
            '0': False, 'false': False, 'toggle': 'toggle', '1': True, 'true': True
        }[str(v).lower()],
        DateField: lambda v: datetime.strptime(str(v), '%Y-%m-%d').date(),
        DateTimeField: lambda v: datetime.strptime(str(v), '%Y-%m-%d %H:%M:%S')
    }

    def print_table(
        self,
        queryset: QuerySet,
        fields: list[str] | None = None,
        order_by: tuple[str] | None = ('name',),
        max_width: int = 120,
        max_rows=5
    ):
        """
        Pretty print the given table rows.

        :param queryset: the QuerySet denoting a table rows collection,
            e.g. `db_model.objects.all()`
        :param fields: the column names to show. If None (the default), show all
            columns. The order dictates the priority of the columns when there is
            extra space available
        :param order_by: a list of field names whereby the rows will be sorted
            ascending. Default: ['name']
        :param max_width: the max table width, in characters
        :param max_rows: the maximum rows to show (default: 5)
        """
        total = queryset.count()  # noqa
        msg = f"{total:,} row{'' if total == 1 else 's'}"
        if total == 0:
            table = [msg]
        else:
            if total <= max_rows + 2:
                max_rows = total
            else:
                msg += f' ({total - max_rows} remaining rows not shown)'
            db_model = queryset.model
            db_model_fields = {f.name: f for f in db_model._meta.fields}
            if fields is None:
                fields = db_model_fields  # noqa
            else:
                fields = {n: db_model_fields[n] for n in fields}  # noqa
            objs = queryset.order_by(*order_by).all()[:max_rows]  # noqa
            field_lengths: dict[str, int] = {f: len(f) for f in fields}
            extra_space = max_width - sum(l+2 for l in field_lengths.values())
            for name, field in fields.items():
                if extra_space <= 0:
                    break
                val = str(getattr(objs[0], name))
                extra_col_space = min(extra_space, len(val) - field_lengths[name])
                if extra_col_space > 0:
                    field_lengths[name] += extra_col_space
                    extra_space -= extra_col_space

            def format(string:str, length:int):  # noqa
                if len(string) > length:
                    return string[:max(0, length - 1)] + '…'
                else:
                    return string.ljust(length)

            tbl_header = [format(n, l) for n, l in field_lengths.items()]
            tbl_body = [
                [format(str(getattr(obj, n)), l) for n, l in field_lengths.items()]
                for obj in objs
            ]

            table = (
                [" " + "  ".join(tbl_header)] +
                ["-" + "--".join(len(x) * "-" for x in tbl_header) + '-'] +
                [" " + "  ".join(x) for x in tbl_body] +
                [msg]
            )

        self.stdout.write(self.style.WARNING("\n".join(table)))
