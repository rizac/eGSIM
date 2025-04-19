from datetime import datetime
from typing import Optional, Callable, Any

from django.core.management import BaseCommand
from django.db import DatabaseError
from django.db.models import (QuerySet, Field, CharField, IntegerField, DateField,
                              FloatField, Model,
                              DateTimeField, TextField, BooleanField, SmallIntegerField,
                              PositiveIntegerField, ForeignKey)

from egsim.api import models


class Command(BaseCommand):
    help = """Interactive Django command to modify eGSIM table content. 
    Particularly useful to 
    quickly hide/show items in the API form testing purposes or fixing bugs
    """

    def handle(self, *args, **options):
        """Execute the command"""
        self.stdout.write(self.style.ERROR('Scanning Db tables...'))
        tables = {}
        for key in dir(models):
            try:
                cls = getattr(models, key)
                if models.__name__ == cls.__module__ and \
                        issubclass(cls, models.EgsimDbModel) and \
                        not cls._meta.abstract:
                    tables[key.lower()] = cls
            except Exception:  # noqa
                pass
        db_model: Optional[Model] = None
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
        if resp == self.quit:
            self.stdout.write(self.style.ERROR('Aborted by user'))

    quit = 'q'
    back = '<'
    help = '?'  # noqa
    suffix = {'h': f'{help}: help', 'q': f'{quit}: quit', 'b': f'{back}: go back'}

    def select_db_model(self, tables: dict[str, Model]) -> tuple[Optional[Model], str]:
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

    def parse_field_and_value(self, db_model: Model, input_result, *,
                              allow_pkey=False, allow_editable=False,
                              allow_fkey=False) -> \
            tuple[Optional[Field], Optional[Any], str]:
        """Return (Field, user_input)"""
        fields = {
            f.name: f for f in db_model._meta.get_fields()  # noqa
            if f.__class__ in self.f_types
        }
        resp = input_result.strip()
        if resp in {self.quit, self.back, self.help}:
            return None, None, resp
        resp = resp.split(" ")
        if len(resp) != 2:
            self.stdout.write(self.style.ERROR(f'Type [column] [value] '
                                               f'(space-separated)'))
        res = resp[0]
        if res not in fields:
            self.stdout.write(self.style.ERROR(f'"{res}" is not a column'))
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

    def select_db_instances(self, db_model: Model) -> tuple[Optional[QuerySet], str]:
        """Return (QuerySet, user_input)"""
        while True:
            msg = f'WHERE [COLUMN] [VALUE] ' \
                  f'({self.suffix["h"]}, {self.suffix["q"]}, {self.suffix["b"]}): '
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

            field_name = field.name
            if field.__class__ in {TextField, CharField}:
                field_name += '__iregex'  # use regexp (search, no match)
            queryset = db_model.objects.filter(**{field_name: val})  # noqa
            if queryset.count() == 0:
                self.stdout.write(self.style.ERROR('No matching row'))
            else:
                self.stdout.write('Matching table row(s): ')
                self.print_table(queryset,
                                 fields={'id', 'name', field.name},
                                 main_fields=['name', field.name])  # noqa
                return queryset, resp

    def update_db_instance(self, queryset: QuerySet) -> str:
        """Return user_input"""
        while True:
            msg = f'SET [COLUMN] [NEW VALUE] ' \
                  f'({self.suffix["h"]}, {self.suffix["q"]}, {self.suffix["b"]}): '
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

            try:
                count = queryset.count()
                if field.__class__ == BooleanField and val == 'toggle':
                    true_ids = [_.id for _ in queryset.filter(**{field.name: True})]
                    queryset.filter(id__in=true_ids).update(**{field.name: False})
                    queryset.exclude(id__in=true_ids).update(**{field.name: True})
                    # update res to display as message below:
                    val = 'true if the value was false, and false ' \
                          'if it was true'
                else:
                    queryset.update(**{field.name: val})
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully updated "{field.name}" '
                        f'in {count} row(s) '
                        f'(new value: {str(val)})'
                    )
                )
                return input(f'What now ({self.suffix["q"]}, {self.suffix["b"]})? ')
            except DatabaseError as db_err:
                self.stdout.write(self.style.ERROR(f'{str(db_err)}'))

    f_types: dict[type[Field], Callable] = {
        CharField: lambda v: str(v),
        TextField: lambda v: str(v),
        IntegerField: lambda v: int(v),
        PositiveIntegerField: lambda v: int(v),
        SmallIntegerField: lambda v: int(v),
        FloatField: lambda v: float(v),
        BooleanField: lambda v: {'0': False, 'false': False, 'toggle': 'toggle',
                                 '1': True, 'true': True}[str(v).lower()],  # noqa
        DateField: lambda v: datetime.strptime(str(v), '%Y-%m-%d').date(),
        DateTimeField: lambda v: datetime.strptime(str(v), '%Y-%m-%d %H:%M:%S')
    }

    def print_table(self, queryset: QuerySet,
                    fields: Optional[set[str]] = None,
                    main_fields: list[str] = ('name',),
                    max_rows=5):
        """Pretty print the given table rows

        :param queryset: the QuerySet denoting a table rows collection,
            e.g. `db_model.objects.all()`
        :param fields: the column names to show. If None (the default), show all columns
        :param main_fields: list/tuple of the name of the columns where at least
            th 1st row value should be visible, if longer than the column name length
            (default: ["name"])
        :param max_rows: the maximum rows to show (default: 5)
        """
        total = queryset.count()  # noqa
        tbl_header = []
        tbl_body = []
        tbl_footer = f"{total:,} rows"
        if total <= max_rows + 2:
            max_rows = total
        else:
            tbl_footer += f' ({total - max_rows} remaining rows not shown)'

        objs = queryset.order_by(*main_fields).all()[:max_rows]  # noqa
        fields_include = fields
        fields: dict[str, int] = {}
        for field in objs[0]._meta.fields:  # noqa
            if fields_include is not None and field.name not in fields_include:
                continue
            name = field.name
            val = str(getattr(objs[0], name))
            if name in main_fields and len(val) > len(name):
                lng = len(val)
            else:
                lng = len(name)
            fields[name] = lng
            tbl_header.append(name[:max(0, lng - 1)] + '…'
                              if len(name) > lng else name.ljust(lng))
        for obj in objs:
            tbl_line = []
            tbl_body.append(tbl_line)
            for name, lng in fields.items():  # noqa
                val = str(getattr(obj, name))
                val = val[:max(0, lng - 1)] + '…' if len(val) > lng else val.ljust(lng)
                tbl_line.append(val)

        table = [" " + " | ".join(tbl_header)] + \
                ["-" + "-|-".join(len(x) * "-" for x in tbl_header) + '-'] + \
                [" " + " | ".join(x) for x in tbl_body] + \
                [tbl_footer]

        self.stdout.write(self.style.WARNING("\n".join(table)))
