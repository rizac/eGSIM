'''
Models for the django app

Currently they represent only read-only data from Tectonic Regionalisations
(provided by custom input files) and OpenQuake Imts, Gsims and Trt

Created on 5 Apr 2019

@author: riccardo
'''
from django.db import models
# primary keys are auto added if not present


ENTITIES = (('gsim', 'Ground Shaking Intensity Model'),
            ('imt', 'Intensity Measure Type'),
            ('trt', 'Tectonic Region Type'))


class Error(models.Model):
    '''Model representing the Errors table. The table stores information
    during the creation of the database for diagnistic purposes only'''

    entity_key = models.TextField(unique=True)
    entity_type = models.CharField(max_length=4, choices=ENTITIES)
    type = models.TextField()
    message = models.TextField()

    def __str__(self):
        return '%s "%s": %s (%s)' % (self.entity_type,
                                     self.entity_key,
                                     self.type,
                                     self.message)


class Trt(models.Model):
    '''Model representing the db table of the (OpenQuake) Tectonic region types
    '''
    key = models.TextField(unique=True)
    oq_att = models.CharField(max_length=100)
    oq_name = models.TextField()

    def __str__(self):
        return self.key


class TectonicRegion(models.Model):
    '''Model representing the db table of Tectonic regions used for gsim
    selection
    '''

    model = models.TextField(null=False)
    geojson = models.TextField(blank=True)
    type = models.ForeignKey(Trt, on_delete=models.CASCADE, null=False)

    def __str__(self):
        return "Tr %d (model: %s, type: %s)" \
            % (self.id, self.model, self.trt.key)  # pylint: disable=no-member


class Imt(models.Model):
    '''Model representing the db table of the (OpenQuake) Intensity Measure
    Types
    '''

    key = models.CharField(max_length=100, unique=True)
    needs_args = models.BooleanField(default=False, null=False)

    def __str__(self):
        return self.key


class Gsim(models.Model):
    '''Model representing the db table of the (OpenQuake) Ground Shaking
    Intensity Models, or GMPE
    '''

    # currently, the max length of the OQ gsims is 43 ...
    key = models.TextField(null=False, unique=True)
    trt = models.ForeignKey(Trt, on_delete=models.CASCADE, null=False)
    imts = models.ManyToManyField(Imt, related_name='gsims')
    needs_args = models.BooleanField(default=False, null=False)
    warning = models.TextField(default=None, null=True)

    def asjson(self):
        '''Converts this object as a json-serializable tuple of strings:
        (gsim, imts, tectonic_region_type, warning) where arguments are all
        strings except 'imts' which is a tuple of strings'''
        trt = self.trt.key  # pylint: disable=no-member
        imts = (_.key for _ in self.imts.all())  # pylint: disable=no-member
        return self.key, tuple(imts), trt, self.warning or ''

    def __str__(self):
        return self.key


def empty_all():
    '''Emtpies all tables'''
    Error.objects.all().delete()  # pylint: disable=no-member
    Gsim.objects.all().delete()  # pylint: disable=no-member
    Imt.objects.all().delete()  # pylint: disable=no-member
    TectonicRegion.objects.all().delete()  # pylint: disable=no-member
    Trt.objects.all().delete()  # pylint: disable=no-member

