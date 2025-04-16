from typing import Optional

from django.core.management import BaseCommand

from egsim.api import models
from egsim.api.models import EgsimDbModel


class Command(BaseCommand):

    help = """Django command to hide or show eGSIM table rows in order to make 
    the relative items accessible or not in the API"""

    def handle(self, *args, **options):
        """Execute the command"""
        tables = {}
        for key in dir(models):
            try:
                cls = getattr(models, key)
                if issubclass(cls, models.EgsimDbModel) and \
                        not cls._meta.abstract:
                    tables[key] = cls
            except Exception:  # noqa
                pass
        quit = "q!"
        back = '<!'
        hidden = 'h!'
        visible = 'v!'
        toggle = 't!'
        db_model: Optional[EgsimDbModel] = None
        queryset = None
        suffix = f'{quit}=quit, {back}=back to previous question'
        while True:
            if db_model is None:
                self.stdout.write(f'{len(tables)} table(s): ' +
                                  self.style.WARNING(" ".join(tables)))
                res = None
                while res is None:
                    res = input(f'Select a table ({suffix}): ')
                    if res not in tables:
                        if res == quit:
                            self.stdout.write(self.style.ERROR('Aborted by user'))
                            return
                        res = None
                    else:
                        db_model = tables[res]  # noqa
            elif queryset is None:
                self.stdout.write(
                    f'{db_model.objects.count()} table rows: ' +
                    self.style.WARNING(self.rows2str(db_model.objects))
                )
                msg = f'Select rows (case insensitive regexp search. {suffix}): '
                while queryset is None:
                    res = input(msg)
                    if res == quit:
                        self.stdout.write(self.style.ERROR('Aborted by user'))
                        return
                    elif res == back:
                        db_model = None
                        break
                    elif res:
                        queryset = db_model.objects.filter(name__iregex=res)  # re.search
                        if queryset.count() == 0:
                            self.stdout.write(self.style.ERROR('No matching rows'))
                            queryset = None
            else:
                self.stdout.write(
                    f'{queryset.count()} matching table row(s): ' +
                    self.style.WARNING(self.rows2str(queryset))
                )
                res = None
                while res is None:
                    res = input(f"Type {hidden} to hide them, "
                                f"{visible} to make them visible, "
                                f"{toggle} to toggle visibility ({suffix}): ")
                    if res == quit:
                        self.stdout.write(self.style.ERROR('Aborted by user'))
                        return
                    elif res == back:
                        queryset = None
                        break
                    elif res in (hidden, visible, toggle):
                        h_queryset = None
                        v_queryset = None
                        if res == toggle:
                            hidden_names = [_.name for _ in queryset.filter(hidden=True)]
                            v_queryset = queryset.filter(name__in=hidden_names)
                            h_queryset = queryset.exclude(name__in=hidden_names)
                        elif res == hidden:
                            h_queryset = queryset
                        else:
                            v_queryset = queryset
                        if h_queryset is not None and h_queryset.count() > 0:
                            h_queryset.update(hidden=True)
                            self.stdout.write(
                                f'Hidden table rows ({h_queryset.count()}): ' +
                                self.style.SUCCESS(
                                    self.rows2str(h_queryset)
                                )
                            )
                        if v_queryset is not None and v_queryset.count() > 0:
                            v_queryset.update(hidden=False)
                            self.stdout.write(
                                f'Visible table rows ({v_queryset.count()}): ' +
                                self.style.SUCCESS(
                                    self.rows2str(v_queryset)
                                )
                            )
                        return
                    else:
                        res = None

    def rows2str(self, queryset, max_items: Optional[int] = 10, sep=' '):
        if max_items is not None and queryset.count() <= max_items + 3:
            max_items = None
        ret = ' '.join(_.name for _ in queryset.order_by('name').all()[:max_items])
        if max_items is not None:
            ret += f' (showing first {max_items} only)'
        return ret

