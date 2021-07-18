import re

import pybel
from django.utils.timezone import datetime
from habanero import Crossref


def get_doi_metadata(doi):
    cr = Crossref()
    crossref_object = cr.works(ids=f'{doi}')
    author = []
    for i in range(len(crossref_object['message']['author'])):
        author.append(crossref_object['message']['author'][i]['given'] +
                      ' ' + crossref_object['message']['author'][i]['family'])

    try:
        author = ','.join(author)
        title = ' '.join(crossref_object['message']['title'])
        journal = ' '.join(crossref_object['message']['container-title'])
        volume = crossref_object['message']['volume']
        doi = crossref_object['message']['DOI']
        pages = crossref_object['message']['page']
        year = crossref_object['message']['issued']['date-parts'][0][0]
        electornic_id = crossref_object['message']['DOI']
    except IndexError:
        return None

    new_article_data = {
        'author': author,
        'title': title,
        'journal': journal,
        'volume': volume,
        'doi': doi,
        'pages': pages,
        'electronic_id': electornic_id,
        'year': datetime(year=int(year), month=1, day=1)
    }

    return new_article_data


def to_decimal(string):
    if not isinstance(string, float):
        illegal_characters = re.search('([^0-9^.^,^-])', string)
        if illegal_characters:
            return string
        else:
            rep = re.compile('(\-?\d*\.?\d+)')

            result = rep.search(string)
            if result:
                return result
            else:
                return None
    else:
        if len(str(string)) >= 7:
            string = round(string, 6)
        return string


def locate_start_data(sheet):
    start_data = None
    for row_index in range(sheet.nrows):
        if "**%BEGIN%**" in sheet.row_values(row_index, 0, 1):
            start_data = row_index + 2
            break
    return start_data


def generate_coordinates_babel(smiles):
    try:
        pybelmol = pybel.readstring('smi', smiles)
        pybelmol.make3D()
        sdf_string = pybelmol.write("sdf")
        return sdf_string
    except:
        return ''
