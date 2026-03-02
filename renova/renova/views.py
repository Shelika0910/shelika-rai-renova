from django.shortcuts import render

def core_views(request):
    return render(request, 'base.html')
