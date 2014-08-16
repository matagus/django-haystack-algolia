"""
A very basic haystack backend for Algolia: hosted cloudsearch as a service.
See http://www.algolia.com/
"""
from __future__ import unicode_literals

import datetime
import re

from warnings import warn

from django.conf import settings
from django.utils import six
from django.core.exceptions import ImproperlyConfigured

import haystack

from haystack import connections
from haystack.backends import BaseEngine, BaseSearchBackend, BaseSearchQuery, log_query
from haystack.constants import ID
from haystack.models import SearchResult

from algoliasearch import algoliasearch

DATETIME_REGEX = re.compile(
    r'^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})T'
    r'(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})(\.\d+)?$')

if settings.DEBUG:
    import logging

    class NullHandler(logging.Handler):
        def emit(self, record):
            pass

    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)
    ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

    logger = logging.getLogger('haystack.simple_backend')
    logger.setLevel(logging.WARNING)
    logger.addHandler(NullHandler())
    logger.addHandler(ch)
else:
    logger = None


class AlgoliaSearchBackend(BaseSearchBackend):
    """
    """

    def __init__(self, connection_alias, **connection_options):
        super(AlgoliaSearchBackend, self).__init__(connection_alias, **connection_options)

        for key in ("APP_ID", "API_KEY", "INDEX_NAME"):
            if not key in connection_options:
                raise ImproperlyConfigured(
                    "You must specify a '{}' in your settings for connection '{}'."\
                        .format(key, connection_alias))

        self.connection_options = connection_options

        self.conn = algoliasearch.Client(
            connection_options["APP_ID"], connection_options["API_KEY"])

        self.index_name = connection_options["INDEX_NAME"]

        self.setup_complete = False

        self.log = logging.getLogger("haystack")

    def setup(self):

        unified_index = haystack.connections[self.connection_alias].get_unified_index()

        # which fields to index
        fields = set(unified_index.all_searchfields().keys())
        fields.add(unified_index.document_field)

        try:
            self.index = self.conn.initIndex(self.index_name)

            self.index.setSettings(
                dict(
                    attributesToIndex=list(fields),
                    attributesForFaceting=[],
                    optionalWords=self.connection_options.get("OPTIONAL_WORDS")
                )
            )
        except algoliasearch.AlgoliaException:
            warn('update is not implemented in this backend')
            raise

    def update(self, index, iterable, commit=True):

        if not self.setup_complete:
            self.setup()

        prepped_docs = []

        for obj in iterable:
            prepped_data = index.full_prepare(obj)
            final_data = {}

            # Convert the data to make sure it's happy.
            for key, value in prepped_data.items():
                final_data[key] = self._from_python(value)

            final_data['objectID'] = final_data[ID]
            del final_data["id"]

            prepped_docs.append(final_data)

        self.index.addObjects(prepped_docs)

    def remove(self, obj, commit=True):

        print(locals())

        if not self.setup_complete:
            self.setup()

        warn('remove is not implemented in this backend')

        #self.index.deleteObject("1")

    def clear(self, models=[], commit=True):

        if not self.setup_complete:
            self.setup()

        self.index.clearIndex()

    @log_query
    def search(self, query_string, **kwargs):

        print(locals())

        if not self.setup_complete:
            self.setup()

        hits = 0
        results = ["object-1", "object-2"]
        result_class = SearchResult
        models = connections[self.connection_alias].get_unified_index().get_indexed_models()

        if kwargs.get('result_class'):
            result_class = kwargs['result_class']

        if kwargs.get('models'):
            models = kwargs['models']

        if query_string:
            for model in models:
                pass

        # set the sort order
        self.index.setSettings({"customRanking": ["desc(name)"]})

        results = self.index.search(query_string, dict(hitsPerPage=20, facets='*', page=0))

        return {
            'results': results["hits"],
            'hits': hits,
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
        if not self.query_filter:
            return '*'

        return ''


class AlgoliaEngine(BaseEngine):

    backend = AlgoliaSearchBackend
    query = AlgoliaSearchQuery
