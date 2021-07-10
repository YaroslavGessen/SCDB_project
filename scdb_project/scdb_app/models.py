from django.db import models
from tinyuuidfield.fields import TinyUUIDField
from django.contrib.auth.models import User


class Post(models.Model):
    author = models.ForeignKey(User, on_delete=models.CASCADE)


class Article(models.Model):
    author = models.CharField(max_length=1000)
    title = models.CharField(max_length=1000)
    journal = models.CharField(max_length=250)
    volume = models.CharField(max_length=100, blank=True, null=True)
    doi = models.CharField(max_length=500, verbose_name='DOI', unique=True)
    pages = models.CharField(max_length=20, blank=True, null=True)
    issue_nr = models.CharField(max_length=100, blank=True, null=True)
    eid = models.CharField(blank=True, null=True, max_length=100)
    year = models.DateField()
    electronic_id = models.CharField(max_length=250)
    created = models.DateTimeField(auto_now_add=True, auto_now=False)

    keywords = models.CharField(max_length=1000, blank=True, null=True)

    def __str__(self):
        return '{} - "{}", vol. {}, issue {}, {} '.format(self.doi, self.title, self.volume, self.issue_nr, self.year)


class Performance(models.Model):
    voc = models.DecimalField(verbose_name='VOC', decimal_places=4, max_digits=15, help_text='[mV]')
    jsc = models.DecimalField(verbose_name='JSC', decimal_places=5, max_digits=15, help_text='[mA/cm^2]')
    ff = models.DecimalField(verbose_name='FF', decimal_places=5, max_digits=13)
    pce = models.DecimalField(verbose_name='PCE', decimal_places=5, max_digits=13, help_text='%, 0-1')
    rs = models.FloatField(verbose_name='Rs', help_text='Rs')
    rsh = models.FloatField(verbose_name='Rsh', help_text='Rsh')
    electrolyte = models.CharField(max_length=1000)
    active_area = models.CharField(max_length=30, help_text='[cm2]', blank=True, null=True)
    co_adsorbent = models.CharField(max_length=250, blank=True, null=True)
    co_sensitizer = models.CharField(max_length=1000, blank=True, null=True)
    semiconductor = models.CharField(max_length=1000)
    dye_loading = models.CharField(max_length=1000, help_text='[nmol/cm2]', blank=True, null=True)
    exposure_time = models.CharField(max_length=500, blank=True, null=True)
    solar_simulator = models.CharField(max_length=1000, default='AM 1.5g')

    short_id = TinyUUIDField(length=10)

    # Now optional
    comment = models.TextField(blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True, auto_now=False)
    article = models.ForeignKey(Article, related_name='performances', on_delete=models.CASCADE)
