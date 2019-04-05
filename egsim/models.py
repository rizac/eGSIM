'''
Models for the django app

Currently they represent only read-only data

Created on 5 Apr 2019

@author: riccardo
'''

from django.db import models

# primary keys auto added?


class Warning(models.Model):
    key = models.CharField(max_length=100, unique=True)
    message = models.CharField(max_length=300)
    is_critical = models.BooleanField()

    def __str__(self):
        return self.key


class Trt(models.Model):
    key = models.CharField(max_length=100, unique=True)
    oq_att = models.CharField(max_length=100)
    oq_name = models.CharField(max_length=100)

    def __str__(self):
        return self.key


class Imt(models.Model):
    key = models.CharField(max_length=100, unique=True)
    warning = models.ForeignKey(Warning, on_delete=models.CASCADE,
                                default=None, null=True)

    def __str__(self):
        return self.key


class Gsim(models.Model):
    # currently, the max length of the OQ gsims is 43 ...
    key = models.CharField(max_length=200, null=False, unique=True)
    trt = models.ForeignKey(Trt, on_delete=models.CASCADE)
    imt = models.ManyToManyField(Imt)
    warning = models.ForeignKey(Warning, on_delete=models.CASCADE, 
                                default=None, null=True)

    def __str__(self):
        return self.key

