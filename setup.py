#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: sw=4 ts=4 fenc=utf-8 et
"""
    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

from setuptools import setup

import oron as package

setup(name=package.__package_name__,
      version=package.__version__,
      author=package.__author__,
      author_email=package.__email__,
      url=package.__url__,
      description=package.__summary__,
      long_description=package.__description__,
      license=package.__license__,
      platforms="Linux",
      keywords = "Oron Utilities",
      packages = ['oron'],
#      package_data = {
#          'oron': [
#              'media/*.avi',
#              'dotsos/ui/data/fonts/*.ttf',
#              'ui/data/*.png',
#              'ui/data/*.svg',
#              'ui/data/*.jpg',
#              'ui/glade/*.ui',
#              'i18n/*/LC_MESSAGES/dotsos.mo'
#          ]
#      },
      install_requires = [
        "Distribute",
      ],
      entry_points = """
      [console_scripts]
      oron-downloader = oron.downloader:main
      oron-uploader   = oron.uploader:main
      oron-blogger    = oron.blogger:main
      """,
      classifiers=[
          'Development Status :: 3 - Alpha',
          'Environment :: Desktop Environment',
          'Intended Audience :: System Administrators',
          'License :: OSI Approved :: BSD License',
          'Operating System :: Linux',
          'Programming Language :: Python',
          'Topic :: Utilities',
      ]
)
