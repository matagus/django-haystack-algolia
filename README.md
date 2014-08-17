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
        'INDEX_NAME': '<INDEX NAME>',
        'TIMEOUT': 60 * 5
    }
}
```

Now you can use haystack as usual. Notice so far it only provides a few features:

 * Indexing your models for first time
 * Updating an index
 * Clearing the whole index
 * Searching models without filtering nor faceting.

TODO
----

 * partially clear an index
 * make updates in batchs
 * query just one or several models, not all models
 * filtering by dates and numbers
 * faceting
 * more_like_this
 * highlighting


Notice algolia.com does not support [dinamically defined (per query) sort
order](https://www.algolia.com/doc/guides/python#Sorting), so using
.order_by() in a haystack SearchQueryset won't make any difference.
