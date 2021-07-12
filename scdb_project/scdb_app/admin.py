from django.contrib import admin
from .models import Performance, Article, Spectrum, Spreadsheet, Contribution, AtomicContribution

admin.site.register(Article)
admin.site.register(Spectrum)
admin.site.register(Performance)
admin.site.register(Spreadsheet)
admin.site.register(Contribution)
admin.site.register(AtomicContribution)
