from django import forms
from .models import Article, Performance
from .helper import get_doi_metadata


class ArticleModelForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = [
            'author',
            'title',
            'journal',
            'volume',
            'doi',
            'pages',
            'issue_nr',
            'eid',
            'year',
            'electronic_id',
            'keywords',
        ]


class ArticleForm(forms.Form):
    doi = forms.CharField(max_length=500, label="DOI", required=True)

    def is_valid(self):
        super().is_valid()

        article_doi = self.cleaned_data.get('doi')
        article = Article.objects.filter(doi__iexact=article_doi).first()

        if article:
            self.model_instance = article
            self.created = False
            return True
        else:
            article_data = get_doi_metadata(article_doi)
            if not article_data:
                self.add_error('doi', 'DOI not found')
                return False

            article_model = ArticleModelForm(article_data)
            if article_model.is_valid():
                article_model.save()
                self.model_instance = article_model.instance
                self.created = True
                return True
            else:
                erred_fields = ', '.join(article_model.errors.keys())
            # TODO: Add try and expect if connection to DOI is not found
                self.add_error('doi',
                               'DOI provided has incomplete ({}) data. Please contact us regarding this.'.format(
                                   erred_fields))
                return False


class PerformanceForm(forms.ModelForm):
    class Meta:
        model = Performance
        fields = [
            'voc',
            'jsc',
            'ff',
            'pce',
            'electrolyte',
            'active_area',
            'co_adsorbent',
            'co_sensitizer',
            'semiconductor',
            'dye_loading',
            'exposure_time',
            'solar_simulator',
            'comment',
        ]

    def is_valid(self, article, molecule):
        super().is_valid()
        if self.errors:
            return False

        # Try to get existing performance, add error if duplicate found
        try:
            performance = Performance.objects.get(article=article, molecule=molecule,
                                                  voc=str(self.data.get('voc')),
                                                  jsc=str(self.data.get('jsc')),
                                                  ff=str(self.data.get('ff')),
                                                  pce=str(self.data.get('pce')))
            if performance:
                self.add_error('voc', 'The performance measure exists already for the given molecule')
                return False
        except Performance.DoesNotExist:
            # All ok
            pass

        return True

    def clean(self):
        super().clean()
