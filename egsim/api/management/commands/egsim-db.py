from datetime import datetime
from typing import Optional, Callable

from django.core.management import BaseCommand
from django.db import DatabaseError
from django.db.models import (QuerySet, Field, CharField, IntegerField, DateField,
                              FloatField, Model,
                              DateTimeField, TextField, BooleanField, SmallIntegerField,
                              PositiveIntegerField)

from egsim.api import models


class Command(BaseCommand):
    help = """Interactive Django command to modify eGSIM table content. 
    Particularly useful to 
    quickly hide/show items in the API form testing purposes or fixing bugs
    """

    def handle(self, *args, **options):
        """Execute the command"""
        self.stdout.write(self.style.ERROR('Scanning editable db tables...'))
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
        field: Optional[Field] = None
        queryset = None
        aborted = None
        while not aborted:
            if db_model is None:
                db_model, aborted = self.select_db_model(tables)  # noqa
            elif field is None:
                field, aborted, back = self.select_field(db_model)
                if back:
                    db_model = None
            elif queryset is None:
                queryset, aborted, back = self.select_db_instances(db_model, field)
                if back:
                    field = None
            else:
                aborted, action = self.update_db_instance(queryset, field)
                if action not in ('r', 'c', 't', self.back):
                    break
                # move back 1 step (r, self.back) or to (c):
                queryset = None
                if action in ('c', 't'):
                    field = None
                if action == 't':
                    db_model = None
        if aborted:
            self.stdout.write(self.style.ERROR('Aborted by user'))

    quit = 'q!'
    back = '<!'
    suffix = [f'{quit}: quit', f'{back}: go back']

    def select_db_model(self, tables: dict[str, Model]) -> tuple[Optional[Model], bool]:
        """Return (DbModel or None, aborted)"""
        self.stdout.write(f'{len(tables)} table(s): ' +
                          self.style.WARNING(" ".join(tables)))
        while True:
            msg = f'Select a table ({self.suffix[0]}): '
            res = input(msg)
            if res == self.quit:
                return None, True
            if res not in tables:
                self.stdout.write(self.style.ERROR('No matching table'))
            else:
                self.print_table(tables[res].objects)  # noqa
                return tables[res], False

    def select_field(self, db_model: Model) -> tuple[Optional[Field], bool, bool]:
        """Return (Field or None, aborted, go_back)"""
        fields = {
            f.name: f for f in db_model._meta.get_fields() if f.__class__ in self.f_types  # noqa
        }
        while True:
            msg = f'Column name to update ' \
                  f'(Enter/Return = "hidden" column, {", ".join(self.suffix)}): '
            res = input(msg) or "hidden"
            if res not in fields:
                if res in {self.quit, self.back}:
                    return None, res == self.quit, res == self.back
                else:
                    self.stdout.write(self.style.ERROR('No matching column'))
            elif fields[res].primary_key:
                self.stdout.write(self.style.ERROR(f'"{res}" is a primary '
                                                   f'key column, its values '
                                                   f'cannot be modified'))
            elif not fields[res].editable:
                self.stdout.write(self.style.ERROR(f'"{res}" is not editable'))
            else:
                return fields[res], False, False  # noqa

    def select_db_instances(self, db_model: Model, field: Field) -> \
            tuple[Optional[QuerySet], bool, bool]:
        """Return (QuerySet or None, aborted, go_back)"""
        while True:
            msg = f'Row name(s) to update (regexp search, ' \
                  f'case-insensitive. {", ".join(self.suffix)}): '
            res = input(msg)
            if res in {self.quit, self.back}:
                return None, res == self.quit, res == self.back
            elif res:
                # use regexp search (no match)
                queryset = db_model.objects.filter(name__iregex=res)  # noqa
                if queryset.count() == 0:
                    self.stdout.write(self.style.ERROR('No matching row'))
                else:
                    self.stdout.write('Matching table row(s): ')
                    self.print_table(queryset,
                                     fields={'id', 'name', field.name},
                                     main_fields=['name', field.name])  # noqa
                    return queryset, False, False

    def update_db_instance(self, queryset: QuerySet, field: Field) -> tuple[bool, str]:
        """Return (aborted, go_back)"""
        toggle = 't!'
        suffix = list(self.suffix)
        ok = False
        while not ok:
            if field.__class__ == BooleanField:
                suffix.insert(0, f'{toggle}=toggle: invert boolean value of ' 
                                 f'each row')
            res = input(f'Set the new value of "{field.name}" '
                        f'({field.__class__.__name__}) '
                        f'for each matching row ({", ".join(suffix)}): ')
            if res in {self.quit, self.back}:
                return res == self.quit, self.back
            else:
                try:
                    if field.__class__ == BooleanField and res == toggle:
                        true_ids = [_.id for _ in queryset.filter(**{field.name: True})]
                        self.update_value(queryset.filter(id__in=true_ids), field,
                                          'false')
                        self.update_value(queryset.exclude(id__in=true_ids), field,
                                          'true')
                        # update res to display as message below:
                        res = 'true if the value was false, and false ' \
                              'if it was true'
                    else:
                        self.update_value(queryset, field, res)
                    ok = True
                except DatabaseError as db_err:
                    self.stdout.write(self.style.ERROR(f'{str(db_err)}'))
            if ok:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully updated the column "{field.name}" '
                        f'of the chosen {queryset.count()} table row(s) '
                        f'(new value: {res})'
                    )
                )
                return False, input('Modify some other row (r), '
                                    'column (c), table (t) or quit (any key)?')

    f_types: dict[type[Field], Callable] = {
        CharField: lambda v: str(v),
        TextField: lambda v: str(v),
        IntegerField: lambda v: int(v),
        PositiveIntegerField: lambda v: int(v),
        SmallIntegerField: lambda v: int(v),
        FloatField: lambda v: float(v),
        BooleanField: lambda v: {'0': False, 'false': False,
                                 '1': True, 'true': True}[str(v).lower()],  # noqa
        DateField: lambda v: datetime.strptime(str(v), '%Y-%m-%d').date(),
        DateTimeField: lambda v: datetime.strptime(str(v), '%Y-%m-%d %H:%M:%S')
    }

    def update_value(self, queryset: QuerySet, field: Field, value: str):
        if field.__class__ not in self.f_types:
            raise DatabaseError(f'"{field}" type ({field.__class__.__name__}) '
                                f'is not supported')
        queryset.update(**{field.name: self.f_types[field.__class__](value)})

    def print_table(self, queryset: QuerySet,
                    fields: Optional[set[str]] = None,
                    main_fields: list[str] = ('name',),
                    max_rows=5):
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
