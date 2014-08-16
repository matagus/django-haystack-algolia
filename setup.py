#!/bin/env python

import os
from distutils.core import setup


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name = 'haystack-algolia',
    version = '0.1',
    description = "An Algolia backend for Haystack",
    long_description = read('README.md'),
    classifiers = [
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Topic :: Internet :: WWW/HTTP :: Indexing/Search',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
        'Framework :: Django',
    ],
    author = 'Matias Agustin Mendez',
    author_email = 'matagus@gmail.com',
    url = 'http://github.com/matagus/haystack-algolia/',
    license = 'BSD License',
    packages = ['haystack_algolia'],
    #install_requires = [
        #'Django', 'haystack>=2.0'
    #],
    #package_data={
         #'haystack_algolia': [
             #'templates/panels/*',
             #'templates/search_configuration/*',
         #]
     #},
)
