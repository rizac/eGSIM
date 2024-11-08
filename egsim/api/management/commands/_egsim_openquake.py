"""
eGSIM management command. See `Command.help` for details
"""
import warnings

from django.core.management import CommandError, BaseCommand

from egsim.smtk import registered_gsims, gsim, intensity_measures_defined_for, \
    ground_motion_properties_required_by, get_sa_limits
from egsim.smtk.flatfile import FlatfileMetadata
from ... import models


class Command(BaseCommand):
    """Class implementing the command functionality"""

    # As help, use the module docstring (until the first empty line):
    help = """Populate the Database with all valid OpenQuake models"""

    def handle(self, *args, **options):
        """Executes the command

        :param args: positional arguments (?). Unclear what should be given
            here. Django doc and Google did not provide much help, source code
            inspection suggests it is here for legacy code (OptParse)
        :param options: any argument (optional or positional), accessible
            as options[<paramname>]. For info see:
            https://docs.djangoproject.com/en/2.2/howto/custom-management-commands/
        """
        self.stdout.write('Populating the database with OpenQuake models')
        models.Gsim.objects.all().delete()
        if models.Gsim.objects.all().count():
            raise CommandError('Table is not empty (deletion failed?), check the DB')
        ok = 0
        with warnings.catch_warnings():
            for name, model_cls in registered_gsims.items():
                if model_cls.superseded_by:
                    continue
                if model_cls.experimental or model_cls.non_verified or \
                        model_cls.adapted:
                    warnings.simplefilter('ignore')
                else:
                    warnings.simplefilter('error')

                # try to see if we can initialize it:
                ok += self.write_model(name, model_cls)

        discarded = len(registered_gsims) - ok
        self.stdout.write(self.style.SUCCESS(f'Models saved: {ok}, '
                                             f'discarded: {discarded}'))

    def write_model(self, name, cls):
        prefix = 'Discarding'
        try:
            _ = gsim(name)  # check we can initialize the model
            imtz = intensity_measures_defined_for(_)
            if not imtz:
                self.stdout.write(f"  {prefix} {name}. No intensity measure defined")
                return False
            gmp = ground_motion_properties_required_by(_)
            if not gmp:
                self.stdout.write(f"  {prefix} {name}. No ground motion property "
                                  f"defined")
                return False
            invalid = sorted(c for c in gmp if not FlatfileMetadata.has(c))
            if invalid:
                self.stdout.write(f"  {prefix} {name}. Unregistered "
                                  f"ground motion properties: {invalid}")
                return False
            sa_lim = get_sa_limits(_)
            models.Gsim.objects.create(
                name=name,
                imts=" ".join(sorted(imtz)),
                min_sa_period=None if sa_lim is None else sa_lim[0],
                max_sa_period=None if sa_lim is None else sa_lim[1],
                unverified=cls.non_verified,
                adapted=cls.adapted,
                experimental=cls.experimental)
        except (TypeError, KeyError, IndexError, ValueError, AttributeError) as exc:
            self.stdout.write(f"  {prefix} {name}. Initialization error: "
                              f"{str(exc)}")
            return False
        return True
