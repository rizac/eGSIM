'''
Models for the django app

Currently they represent only read-only data

Created on 5 Apr 2019

@author: riccardo
'''

from django.db import models
# primary keys are auto added if not present

ENTITIES = (('gsim', 'Ground Shaking Intensity Model'),
            ('imt', 'Intensity Measure Type'),
            ('trt', 'Tectonic Region Type'))


class Errors(models.Model):
    entity_key = models.CharField(max_length=100, unique=True)
    entity_type = models.CharField(max_length=4, choices=ENTITIES)
    type = models.CharField(max_length=100)
    message = models.CharField(max_length=300)

    def __str__(self):
        return '%s "%s": %s (%s)' % (self.entity_type,
                                     self.entity_key,
                                     self.type,
                                     self.message)


class Trt(models.Model):
    key = models.CharField(max_length=100, unique=True)
    oq_att = models.CharField(max_length=100)
    oq_name = models.CharField(max_length=100)

    def __str__(self):
        return self.key


class Imt(models.Model):
    key = models.CharField(max_length=100, unique=True)
    needs_args = models.BooleanField(default=False, null=False)

    def __str__(self):
        return self.key


class Gsim(models.Model):
    # currently, the max length of the OQ gsims is 43 ...
    key = models.CharField(max_length=200, null=False, unique=True)
    trt = models.ForeignKey(Trt, on_delete=models.CASCADE, null=False)
    imts = models.ManyToManyField(Imt, related_name='gsims')
    warning = models.CharField(max_length=100,
                               default=None, null=True)

    def asjson(self):
        '''Converts this object as a json-serializable tuple of strings:
        (gsim, imts, tectonic_region_type) where the first and last arguments
        are strings, and the second is a list of strings'''
        return self.key, [_.key for _ in self.imts.all()], \
            self.trt.key, self.warning or ''

    def __str__(self):
        return self.key
