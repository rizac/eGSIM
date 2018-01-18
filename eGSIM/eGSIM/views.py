'''
Created on 17 Jan 2018

@author: riccardo
'''
from django.http import HttpResponse
from django.shortcuts import render

def index(request):
    return render(request, 'home.html', {'project_name':'eGSIM'})
#     return HttpResponse('Hello World!')