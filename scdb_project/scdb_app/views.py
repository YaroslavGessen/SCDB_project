from django.shortcuts import render
from django.http import HttpResponse
from .models import Performance, Article, Post
from django.views.generic import ListView
from django.contrib.auth.decorators import login_required
from .forms import ArticleForm, PerformanceForm
from django.core.exceptions import FieldError

def home_page(request):
    context = {
        'articles': Article.objects.all(),
        'performances': Performance.objects.all()
    }
    return render(request, 'app/home.html', context)


class PostListView(ListView):
    model = Post
    template_name = 'app/home.html'
    context_object_name = 'performances'


def about_page(request):
    return render(request, 'app/about.html', {'title': 'About'})


def validate_raw_data(article_form, performance_form, user):
    """
    :param *form: Forms necessary to create a "performance" object
    :return: Tuple: (Passed, [(object_1, created_1), (object_2, created_2), ... ]).
        Passed: True if there were no errors during the process, false otherwise
        Objects: list of tuples containing the object it self as well as a boolean if it was created now
    """
    try:
        if not article_form.is_valid():
            raise FieldError
        else:
            article, created_article = article_form.get_model()

            # article exists or was created
            created_molecule, created_spectrum, created_performance = False, False, False

            if not performance_form.is_valid(article):
                raise FieldError

            performance = performance_form.save(commit=False)

            performance.article, performance.molecule, performance.user = article, user
            performance.save()

            created_performance = True

            return True, [(article, created_article),
                          (performance, created_performance)]

    except FieldError:
        return False, [(article_form, False), (performance_form, False)]


@login_required
def single_upload(request):
    article_form = ArticleForm(request.POST or None)
    performance_form = PerformanceForm(request.POST or None)
    forms = {'article_form': article_form, 'performance_form': performance_form}

    if request.method == "POST":
        if article_form.is_valid():
            passed, data_objects = validate_raw_data(user=request.user, **forms)

    context = {
        'article_form': article_form,
        'performance_form': performance_form,
    }

    return render(request, 'app/home.html', context)
