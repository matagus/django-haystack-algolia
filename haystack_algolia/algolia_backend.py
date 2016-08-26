"""
A very basic haystack backend for Algolia: hosted cloudsearch as a service.
See http://www.algolia.com/
"""
from __future__ import unicode_literals

import datetime
import math
import re

from collections import defaultdict
from itertools import tee
from warnings import warn

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.models.loading import get_model
from django.utils import six

import haystack

from haystack import connections
from haystack.backends import BaseEngine, BaseSearchBackend, BaseSearchQuery, log_query
from haystack.constants import ID, DJANGO_CT, DJANGO_ID
from haystack.models import SearchResult
from haystack.utils import get_identifier

from algoliasearch import algoliasearch


DATETIME_REGEX = re.compile(
    r'^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})T'
    r'(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})(\.\d+)?$')

UPDATE_CHUNK_SIZE = 50


class AlgoliaSearchBackend(BaseSearchBackend):
    """
    """

    def __init__(self, connection_alias, **connection_options):
        super(AlgoliaSearchBackend, self).__init__(connection_alias, **connection_options)

        for key in ("APP_ID", "API_KEY", "INDEX_NAME_PREFIX"):
            if not key in connection_options:
                raise ImproperlyConfigured(
                    "You must specify a '{}' in your settings for connection '{}'."\
                        .format(key, connection_alias))

        self.connection_options = connection_options

        self.conn = algoliasearch.Client(
            connection_options["APP_ID"], connection_options["API_KEY"])

        self.index_name_prefix = connection_options.get("INDEX_NAME_PREFIX", "") or ""

        self.setup_complete = False

    def _get_index_for(self, model):
        model_klass = model._meta.concrete_model
        index_name = "{}{}.{}".format(self.index_name_prefix, model._meta.app_label, model._meta.model_name)
        return self.conn.initIndex(index_name)

    def _get_fields_to_index(self, model):
        model_klass = model._meta.concrete_model
        haystack_index = connections[self.connection_alias].get_unified_index().get_index(model_klass)

        # which fields to index
        fields = haystack_index.get_field_weights().items()
        return [field for (field, order) in sorted(fields, key=lambda item: item[1], reverse=True)]

    def setup(self):
        indexed_models = connections[self.connection_alias].get_unified_index().get_indexed_models()

        for model in indexed_models:
            index = self._get_index_for(model)

            index.setSettings(
                dict(
                    attributesToIndex=self._get_fields_to_index(model),
                    attributesForFaceting=[],
                    optionalWords=self.connection_options.get("OPTIONAL_WORDS")
                )
           )

    def update(self, index, iterable, commit=True):

        if not self.setup_complete:
            self.setup()

        prepped_docs_by_model = defaultdict(list)
        count_by_model = defaultdict(int)

        # prepare and group objects by model
        for obj in iterable:
            prepped_data = index.full_prepare(obj)
            final_data = {}

            # Convert the data to make sure it's happy.
            for key, value in prepped_data.items():
                final_data[key] = self._from_python(value)

            final_data['objectID'] = final_data[ID]
            del final_data["id"]

            prepped_docs_by_model[obj._meta.model].append(final_data)
            count_by_model[obj._meta.model] += 1

        # then update each model index objects
        for model, docs in prepped_docs_by_model.items():
            algolia_index = self._get_index_for(model)

            obj_count = count_by_model[model]
            chunks = int(math.ceil(obj_count / float(UPDATE_CHUNK_SIZE)))

            for doc_iterator in tee(docs, chunks):
                algolia_index.addObjects(doc_iterator)

    def remove(self, obj, commit=True):

        if not self.setup_complete:
            self.setup()

        index = self._get_index_for(obj._meta.model)
        index.deleteObject(get_identifier(obj))

    def clear(self, models=[], commit=True):

        if not self.setup_complete:
            self.setup()

        if not models:
            models = connections[self.connection_alias].get_unified_index().get_indexed_models()

        for model in models:
            index = self._get_index_for(model)
            index.clearIndex()

    @log_query
    def search(self, query_string, **kwargs):

        if not self.setup_complete:
            self.setup()

        hits = 0
        results = []
        result_class = kwargs.get('result_class') or SearchResult

        models = kwargs.get('models')

        if models is None or len(models) > 1:
            warn("Quering more than one model feature hasn't been implemented so far")
            return {'results': [], 'hits': 0}

        # set the sort order
        start_offset = kwargs['start_offset']
        end_offset = kwargs['end_offset']
        per_page = end_offset - start_offset
        page = int(start_offset / per_page)

        # query algolia.com
        index = self._get_index_for(list(models)[0])
        raw_results = index.search(query_string, dict(hitsPerPage=per_page, facets='*', page=page))

        # and then transform json response into haystack search result instances
        results = self._process_results(raw_results, result_class=result_class)

        return {
            'results': results["results"],
            'hits': results["hits"],
        }

    def _process_results(self, raw_results, result_class=SearchResult):

        results = []
        hits = raw_results['nbHits']

        if result_class is None:
            result_class = SearchResult

        unified_index = connections[self.connection_alias].get_unified_index()
        indexed_models = unified_index.get_indexed_models()

        for raw_result in raw_results.get('hits', []):
            app_label, model_name = raw_result[DJANGO_CT].split('.')
            additional_fields = {}
            model = get_model(app_label, model_name)

            if model and model in indexed_models:
                for key, value in raw_result.items():
                    index = unified_index.get_index(model)
                    string_key = str(key)

                    if string_key in index.fields and hasattr(index.fields[string_key], 'convert'):
                        additional_fields[string_key] = index.fields[string_key].convert(value)
                    else:
                        additional_fields[string_key] = self._to_python(value)

                del(additional_fields[DJANGO_CT])
                del(additional_fields[DJANGO_ID])

                score = 1  # FIXME
                result = result_class(app_label, model_name, raw_result[DJANGO_ID], score, **additional_fields)
                results.append(result)
            else:
                hits -= 1

        return {
            'results': results,
            'hits': hits,
            'facets': [],
            'spelling_suggestion': [],
        }

    def _iso_datetime(self, value):
        """
        If value appears to be something datetime-like, return it in ISO format.

        Otherwise, return None.
        """
        if hasattr(value, 'strftime'):
            if hasattr(value, 'hour'):
                return value.isoformat()
            else:
                return '%sT00:00:00' % value.isoformat()

    def _from_python(self, value):
        """Convert more Python data types to Algolia-understandable JSON."""
        iso = self._iso_datetime(value)
        if iso:
            return iso

        elif isinstance(value, six.binary_type):
            # TODO: Be stricter.
            return six.text_type(value, errors='replace')

        elif isinstance(value, set):
            return list(value)

        return value

    def _to_python(self, value):
        """Convert values from Algolia to native Python values."""

        if isinstance(value, (int, float, complex, list, tuple, bool)):
            return value

        if isinstance(value, six.string_types):
            possible_datetime = DATETIME_REGEX.search(value)

            if possible_datetime:
                date_values = possible_datetime.groupdict()

                for dk, dv in date_values.items():
                    date_values[dk] = int(dv)

                return datetime.datetime(
                    date_values['year'], date_values['month'],
                    date_values['day'], date_values['hour'],
                    date_values['minute'], date_values['second'])

        try:
            # This is slightly gross but it's hard to tell otherwise what the
            # string's original type might have been. Be careful who you trust.
            converted_value = eval(value)

            # Try to handle most built-in types.
            if isinstance(
                    converted_value,
                    (int, list, tuple, set, dict, float, complex)):
                return converted_value

        except Exception:
            # If it fails (SyntaxError or its ilk) or we don't trust it,
            # continue on.
            pass

        return value

    def more_like_this(self, model_instance, additional_query_string=None,
                       start_offset=0, end_offset=None,
                       limit_to_registered_models=None, result_class=None, **kwargs):
        return {
            'results': [],
            'hits': 0
        }


class AlgoliaSearchQuery(BaseSearchQuery):

    def build_query(self):
        # so far, pretty dummy

        if not self.query_filter:
            return '*'

        # no field filtering. It's an Algolia's feature, not a bug.
        queries = [value for field_name, value in self.query_filter.children]

        return ' '.join(queries)


class AlgoliaEngine(BaseEngine):

    backend = AlgoliaSearchBackend
    query = AlgoliaSearchQuery
