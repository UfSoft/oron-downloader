# -*- coding: utf-8 -*-
"""
    oron.utils
    ~~~~~~~~

    :copyright: © 2012 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

import logging
from lxml import etree
from zope.testbrowser.browser import Browser

log = logging.getLogger(__name__)

class OronFile(object):
    def __init__(self, url, filename, size):
        self.url = url
        self.filename = filename
        self.size = size

class OronLinksParser(object):
    def __init__(self, url, browser=None):
        self.url = url.strip()
        if browser is None:
            browser = Browser()
        self.browser = browser
        self.filenames = {}
        self.total_files = 0

    def parse(self):
        log.info("Opening downloads URL: %s", self.url)
        self.browser.open(self.url)
        # Test to see if we're browsing a folder
        doc = etree.HTML(self.browser.contents)
        folder_xpath = doc.xpath(
            '//table[@class="tbl2"]/tr/td[1]/a[@target="_blank"]/small'
        )
        if folder_xpath:
            self.total_files = len(folder_xpath)
            self.find_download_links(doc)
        elif doc.xpath('//div[@class="content"]/form/table/tr/td'):
            self.total_files = 1
            self.find_download_link_data(doc)
        else:
            log.error("Unable to find out if it's a single file or a folder")

    def find_download_link_data(self, doc):
        info_node = doc.xpath('//div[@class="content"]/form/table/tr/td')
        if info_node:
            info_node = info_node[0]
        else:
            file_not_found_match = doc.xpath('//h2/text()')
            if file_not_found_match:
                log.error("File was not found on server. Skipping...")
            else:
                log.error("Could not find out the filename. Skipping...")

        filename_match = info_node.xpath('./b/text()')
        if filename_match:
            filename = filename_match[0]

        size = info_node.xpath('./text()')[-1].strip().split('File size:')[-1].strip().upper()
        self.filenames[filename] = OronFile(self.url, filename, size)

    def find_download_links(self, doc):
        log.info("Found %d links to download.", self.total_files)
        trs = doc.xpath('//table[@class="tbl2"]/tr')
        for tr in trs:
            link_td = tr.xpath('td[1]/a')
            size_td = tr.xpath('td[2]/small/nobr/text()')
            if not link_td or not size_td:
                continue

            filename_search = link_td[0].xpath('small/text()')
            if not filename_search:
                continue
            filename = filename_search[0]

            href = link_td[0].attrib['href']
            size = size_td[0].upper()

            self.filenames[filename] = OronFile(href, filename, size)
