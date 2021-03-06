import csv
import itertools

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldError
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.forms import modelformset_factory
from django.http import StreamingHttpResponse
from django.shortcuts import reverse, render, redirect, Http404
import plotly.express as px
from sklearn.decomposition import PCA

from .forms import *
from .helpers import locate_start_data, to_decimal
from .models import Molecule, Spectrum, Performance, Contribution, APPROVAL_STATES


def validate_raw_data(article_form, molecule_form, spectrum_form, performance_form, user):
    try:
        if not article_form.is_valid():
            raise FieldError
        else:
            article, created_article = article_form.get_model()
            created_molecule, created_spectrum, created_performance = False, False, False
            try:
                molecule_form.is_valid()
                molecule = Molecule.objects.get(Q(inchi=molecule_form.data.get('inchi')) |
                                                Q(smiles=molecule_form.data.get('smiles')))
            except ObjectDoesNotExist:
                if not molecule_form.is_valid():
                    raise FieldError
                molecule_form.article = article
                molecule = molecule_form.save()
                created_molecule = True

            try:
                spectrum = Spectrum.objects.get(molecule=molecule)
            except ObjectDoesNotExist:
                if not spectrum_form.is_valid():
                    raise FieldError
                spectrum = spectrum_form.save(commit=False)
                spectrum.article, spectrum.molecule = article, molecule
                spectrum.save()
                created_spectrum = True

            if not performance_form.is_valid(article, molecule):
                raise FieldError

            performance = performance_form.save(commit=False)

            performance.article, performance.molecule, performance.user = article, molecule, user
            performance.save()

            created_performance = True

            return True, [(article, created_article), (molecule, created_molecule), (spectrum, created_spectrum),
                          (performance, created_performance)]

    except FieldError:
        return False, [(article_form, False), (molecule_form, False), (spectrum_form, False), (performance_form, False)]


@login_required
def single_upload(request):
    article_form = ArticleForm(request.POST or None)
    molecule_form = MoleculeForm(request.POST or None)
    spectrum_form = SpectrumForm(request.POST or None)
    performance_form = PerformanceForm(request.POST or None)
    forms = {'article_form': article_form, 'molecule_form': molecule_form, 'spectrum_form': spectrum_form,
             'performance_form': performance_form}

    if request.method == "POST":
        if article_form.is_valid():
            passed, data_objects = validate_raw_data(user=request.user, **forms)

            if passed is True:
                Contribution.objects.create_from_data([data_objects], user=request.user)
                messages.add_message(request, messages.SUCCESS,
                                     'The data was uploaded and is awaiting review. Thank you!')
                return redirect(reverse("single-upload"))

    context = {
        'molecule_form': molecule_form,
        'article_form': article_form,
        'spectrum_form': spectrum_form,
        'performance_form': performance_form,
    }

    return render(request, 'app/doi/single-upload.html', context)


@login_required
def file_upload(request):
    user = request.user
    file_form = SpreadsheetForm(request.POST or None, request.FILES or None)
    if request.method == 'POST':
        if file_form.is_valid():
            # Posted valid data
            from xlrd import open_workbook, XLRDError

            upload = file_form.save(commit=False)
            upload.user = user
            upload.save()

            try:
                book = open_workbook(settings.MEDIA_ROOT + '/' + str(upload.file))
            except XLRDError:
                messages.add_message(request, messages.ERROR,
                                     'The file was not recognized as a valid spreadsheet file. '
                                     'Please download the sample file and try again.')
                return redirect(reverse('file-upload-page'))

            sheet = book.sheet_by_index(0)

            start_data = locate_start_data(sheet)
            if not start_data:
                messages.add_message(request, messages.ERROR,
                                     'Could not find start-tag. Compare your sheet with the sample sheet.')
                return redirect(reverse('file-upload-page'))

            results, total_status = [], True

            try:
                with transaction.atomic():
                    for row_index in range(start_data, sheet.nrows):
                        row = sheet.row_values(row_index, 0, 24)

                        try:
                            # Populate article, molecule, spectrum and performance forms with the data from the user

                            article_form = ArticleForm({'doi': row[0]})
                            molecule_form = MoleculeForm(
                                {'user': user, 'smiles': row[14], 'inchi': row[15], 'keywords': row[19]})
                            spectrum_form = SpectrumForm({
                                'absorption_maxima': to_decimal(row[16]), 'emission_maxima': to_decimal(row[17]),
                                'solvent': row[18]
                            })
                            performance_form = PerformanceForm({
                                'voc': to_decimal(row[1]), 'jsc': to_decimal(row[2]), 'ff': to_decimal(row[3]),
                                'pce': to_decimal(row[4]), 'electrolyte': row[5], 'active_area': row[6],
                                'co_adsorbent': row[7],
                                'co_sensitizer': row[8], 'semiconductor': row[9], 'dye_loading': row[10],
                                'exposure_time': row[11], 'solar_simulator': row[12],
                                'comment': row[13]
                            })

                            forms = {'article_form': article_form, 'molecule_form': molecule_form,
                                     'spectrum_form': spectrum_form,
                                     'performance_form': performance_form}

                            passed, data = validate_raw_data(user=user, **forms)
                            _, _, _, r = data
                            _, created = r
                            if not created:
                                print("Row {} did not yield performance".format(row_index))
                            results.append(data)

                            if passed is not True:
                                total_status = False

                        except IndexError:
                            # Failed to get some value, raise error.
                            total_status = False
                            messages.add_message(request, messages.ERROR,
                                                 'Critical error at row {}. '.format(row_index))

                    if total_status is not True:
                        raise IntegrityError
            except IntegrityError as e:
                messages.add_message(request, messages.ERROR,
                                     'Critical error at row {}. '.format(row_index))
                print(e)

            if total_status is not True:
                # Iterate over attribute error, for every row
                errors = []
                # _, objects = zip(*results)
                for row_nr, row_data in enumerate(results):
                    row_data, _ = zip(*row_data)
                    for instance in row_data:
                        if not hasattr(instance, 'pk'):
                            for k, v in instance.errors.items():
                                errors.append(
                                    {'row': start_data + 1 + row_nr, 'key': k.replace('_', ' ').title(), 'message': v})

                if errors:
                    messages.add_message(request, messages.ERROR, 'Upload failed')
                    return render(request, 'app/doi/file-upload.html', context={'file_form': file_form, 'errors': errors})
            else:
                Contribution.objects.create_from_data(results, user=user)
                messages.add_message(request, messages.SUCCESS,
                                     'The data was uploaded and is awaiting review. Thank you!')
                return redirect(reverse('file-upload-page'))

    return render(request, 'app/doi/file-upload.html', context={'file_form': file_form})


@login_required
def contributions_evaluation_overview(request):
    to_evaluate = Contribution.objects.all().order_by('-created')
    ApprovalFormSet = modelformset_factory(Contribution, fields=('status',))

    if request.method == 'POST':
        formset = ApprovalFormSet(request.POST)
        if formset.is_valid():
            instances = formset.save(commit=False)
            for instance in instances.changed_objects():
                instance.save()

    else:
        formset = ApprovalFormSet(
            queryset=Contribution.objects.filter(status__in=[APPROVAL_STATES.DENIED, APPROVAL_STATES.WAITING]))
    context = {
        'contributions': to_evaluate,
        'formset': formset,
        'admin': True,
    }
    return render(request, 'evaluate_contributions.html', context=context)


@login_required
def contribution_performances(request, short_id):
    contribution = Contribution.objects.get(short_id=short_id)
    atomic_contrib_performances = contribution.items.filter(content_type=ContentType.objects.get_for_model(Performance))
    performances = Performance.objects.filter(contribution__in=atomic_contrib_performances)
    approval_form = None

    if request.user.has_perm('set_contribution_status'):
        approval_form = ApprovalForm(request.POST or None, instance=contribution)

        if request.method == 'POST':
            if approval_form.is_valid():
                approval_form.save()
                messages.add_message(request, messages.SUCCESS,
                                     'The contribution has been marked as {}'.format(
                                         APPROVAL_STATES.for_value(contribution.status).display))
                return redirect(reverse("dye:evaluate-contributions"))

    return render(request, 'single_evaluation.html',
                  context={'approval_form': approval_form, 'performances': performances})


def performance_list(request):
    context = paginate_performances(request, get_performances(), {})
    return render(request, 'performance_list.html', context)


def performance_details(request, short_id):
    try:
        performance = Performance.objects.get(short_id=short_id)
    except Performance.DoesNotExist:
        raise Http404

    context = {
        'performance': performance,
        'related_form': PerformanceStructureSearchForm(initial={'smiles': performance.molecule.smiles,
                                                                'complete_molecule': True}),
    }

    return render(request, 'performance_detail.html', context)


def performance_search(request):
    context = {}
    context['search'] = False
    if request.method == 'POST':
        range_form = PerformanceRangeSearchForm(request.POST)
        keyword_form = PerformanceKeywordSearchForm(request.POST)
        structure_form = PerformanceStructureSearchForm(request.POST)

        if range_form.is_valid() and keyword_form.is_valid() and structure_form.is_valid():
            performances = get_performances(**range_form.cleaned_data, **keyword_form.cleaned_data,
                                            **structure_form.cleaned_data)
            context = paginate_performances(request, performances, context)
            context['hits'] = performances.count()
            context['search'] = True
    else:
        range_form = PerformanceRangeSearchForm()
        keyword_form = PerformanceKeywordSearchForm()
        structure_form = PerformanceStructureSearchForm(
            initial={'search_type': PerformanceStructureSearchForm.SUBSTRUCTURE})
        performances = get_performances()
        context = paginate_performances(request, performances, context)

    context['range_form'] = range_form
    context['keyword_form'] = keyword_form
    context['structure_form'] = structure_form

    return render(request, 'performance_list.html', context)


def get_performances(**search):
    performances = Performance.objects.filter(status=APPROVAL_STATES.APPROVED)

    # Search after keyword
    if search.get('keyword'):
        keyword = search.get('keyword')
        performances = performances.filter(molecule__keywords__icontains=keyword) | \
                       performances.filter(article__keywords__icontains=keyword) | \
                       performances.filter(electrolyte__icontains=keyword) | \
                       performances.filter(comment__icontains=keyword)

    # Search after different range criterias
    if search.get('min_voc'):
        performances = performances.filter(voc__gte=search.get('min_voc'))
    if search.get('max_voc'):
        performances = performances.filter(voc__lte=search.get('max_voc'))
    if search.get('min_jsc'):
        performances = performances.filter(jsc__gte=search.get('min_jsc'))
    if search.get('max_jsc'):
        performances = performances.filter(jsc__lte=search.get('max_jsc'))
    if search.get('min_ff'):
        performances = performances.filter(ff__gte=search.get('min_ff'))
    if search.get('max_ff'):
        performances = performances.filter(ff__lte=search.get('max_ff'))
    if search.get('min_pce'):
        performances = performances.filter(pce__lte=search.get('min_pce'))
    if search.get('max_pce'):
        performances = performances.filter(pce__lte=search.get('max_pce'))

    # Structure search
    if search.get('smiles'):
        # If the molecule search is not a partial structure
        if search.get('complete_molecule'):
            performances = performances.filter(molecule__smiles=search.get('smiles'))
        else:
            if search.get('search_type') == PerformanceStructureSearchForm.SUBSTRUCTURE:
                molecules = Molecule.objects.substructure_search(search.get('smiles'))
            else:
                molecules = Molecule.objects.similarity_search(search.get('smiles'),
                                                               tanimoto_threshold=search.get('tanimoto_threshold'))
            performances = performances.filter(molecule__in=molecules)

    return performances


def paginate_performances(request, performance_list, context):
    paginator = Paginator(performance_list, settings.PAGINATION_NUMBER)

    page = request.GET.get('page')
    try:
        performances = paginator.page(page)
        page = int(page)
    except PageNotAnInteger:
        performances = paginator.page(1)
        page = 1
    except EmptyPage:
        performances = paginator.page(paginator.num_pages)
        page = paginator.num_pages

    if page - 5 < 1:
        first_page = 1
    else:
        first_page = page - 5

    if page + 5 > paginator.num_pages:
        last_page = paginator.num_pages
    else:
        last_page = page + 5

    context['performances'] = performances
    context['pages'] = [i for i in range(first_page, last_page + 1)]
    context['num_pages'] = paginator.num_pages

    return context


class Echo:
    def write(self, value):
        return value


def download_all_performances_csv(request):
    all_performances = list(Performance.objects.all().select_related('molecule', 'article', 'molecule__spectrum'))

    rows = ([instance.voc, instance.jsc, instance.ff, instance.pce, instance.electrolyte,
             instance.active_area, instance.co_adsorbent, instance.co_sensitizer,
             instance.semiconductor, instance.dye_loading, instance.exposure_time,
             instance.solar_simulator, instance.comment,

             instance.article.author, instance.article.title, instance.article.journal, instance.article.volume,
             instance.article.doi, instance.article.pages, instance.article.issue_nr, instance.article.eid,
             instance.article.year, instance.article.electronic_id, instance.article.keywords,

             instance.molecule.smiles, instance.molecule.keywords,

             instance.molecule.spectrum.absorption_maxima, instance.molecule.spectrum.emission_maxima,
             instance.molecule.spectrum.solvent]
            for instance in all_performances
            )

    pseudo_buffer = Echo()
    writer = csv.writer(pseudo_buffer)
    first_row = ["VOC", "JSC", "FF", "PCE", "Electrolyte", "Active area", "Co-adsorbent", "Co-sensitizer",
                 "Semiconductor", "Dye loading", "Exposure time", "Solar simulator", "Performance comment",

                 "Article author", "Article title", "Article journal", "Article volume", "Article DOI",
                 "Article pages", "Article issue nr", "Article EID", "Article year", "Article year",
                 "Article electronic id", "Article keywords",

                 "Molecule SMILE", "Molecule keywords",

                 "Molecule spectrum absorption maxima", "Molecule spectrum emission maxima",
                 "Molecule spectrum solvent"]

    response = StreamingHttpResponse((writer.writerow(row) for row in itertools.chain([first_row], rows)),
                                     content_type="text/csv")
    response['Content-Disposition'] = 'attachment; filename="datadump.csv"'
    return response


@login_required
def my_contributions(request):
    contributions = Contribution.objects.filter(user=request.user).order_by('-created')
    return render(request, 'app/doi/my_contributions.html', context={'contributions': contributions})


def get_pca(request):
    pass


def batch_download_info(request):
    return render(request, 'app/doi/batch-download.html')


def index(request):
    context = {}

    return render(request, 'app/home.html', context)


def about_page(request):
    return render(request, 'app/about.html', {'title': 'About'})