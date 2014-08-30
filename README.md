haystack-algolia
================

An [Algolia](https://www.algolia.com/) backend for [Haystack 2.x](http://haystacksearch.org/).
Use Algolia service to index and search your django models.


INSTALLATION
------------

First, go to https://www.algolia.com/ and create an account. Then create an
index, you'll need it later.

Install haystack-algolia from github using pip:

    pip install -e git+https://github.com/matagus/haystack-algolia.git#egg=dev

Then add to your settings.py:


```python
HAYSTACK_CONNECTIONS = {
    'default': {
        'ENGINE': 'haystack_algolia.algolia_backend.AlgoliaEngine',
        'APP_ID': '<YOUR APP ID>',
        'API_KEY': '<YOUR API KEY>',
        'INDEX_NAME_PREFIX': 'production-',
        'TIMEOUT': 60 * 5
    }
}
```

Now you can use haystack as usual. Notice so far it only provides a few features:

 * Indexing your models for first time. Each model instances get indexed in a separate
 Algolia's index in order to use [certain Algolia optimizations](https://www.algolia.com/doc/guides/python#Sorting)
 * Updating indexes
 * Clearing indexes
 * Removing one object from its index
 * Searching models

TODO
----

Haystack features:

 * filtering by dates, numbers or tags: https://www.algolia.com/doc/guides/python#Filtering
 * narrowing results
 * faceting
 * more_like_this
 * highlighting
 * geo-search
 * reindexing without data-loss using a new index & then renaming it

In general:

 * tests


Notice that algolia.com does not support [dinamically defined (per query) sort
order](https://www.algolia.com/doc/guides/python#Sorting), so using
.order_by() in a haystack SearchQuerySet won't make any difference.

Also, filtering works in a pretty different way than in other haystack backends:
if you do SearchQuerySet().models(MyModel).filter(field1="foo", field2="bar") it
this backend will search for "foo bar" no matter in what fields it appears. I'll
be working in providing a more accurate filtering feature using [Algolia's
filtering API](https://www.algolia.com/doc/guides/python#Filtering).
