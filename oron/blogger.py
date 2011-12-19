# -*- coding: utf-8 -*-
"""
    oron.blogger
    ~~~~~~~~~~~~

    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

import os
import sys
import logging
import subprocess
from jinja2 import Template
from optparse import OptionParser
from ConfigParser import SafeConfigParser
from lxml import etree
from zope.testbrowser.browser import Browser

logging.basicConfig(format='%(message)s', level=logging.DEBUG)

log = logging.getLogger(__name__)

HTML_TEMPLATE = Template("""
{% for filename, size, href, img_html in links %}
{{ img_html }}<br/>
<a href="{{ href }}">Download  &mdash; {{ filename }}({{ size }})</a>
<br/>
<br/>
{% endfor %}
""")

class Blogger(object):
    def __init__(self, options):
        self.oron_folder_url = options.url
        self.title_base = options.title_base
        self.links_per_post = options.links_per_post
        self.screenshots_dir = options.screenshots
        self.output_dir = options.output

        log.info("Starting Browser")
        self.browser = Browser("http://oron.com")
        self.total_links = 0
        self.links = {}

    def login(self):
        if self.browser and self.browser.contents:
            if self.username in self.browser.contents and \
                                            'Logout' in self.browser.contents:
                log.info("Already logged in!")
                return
        log.info("Logging into Oron.com")
        self.browser.open('http://oron.com/login')
        self.browser.getControl(name='login').value = self.username
        self.browser.getControl(name='password').value = self.password
        self.browser.getForm(name='FL').submit(' Submit ')
        if self.username not in self.browser.contents:
            log.error("Failed to login...")
            print self.browser.contents
            sys.exit(1)
        log.info("Logged in successfully")

    def grab_links(self):
        log.info("Loading oron folder url: %s", self.oron_folder_url)
        self.browser.open(self.oron_folder_url)
        doc = etree.HTML(self.browser.contents)
        self.total_links = len(doc.xpath(
            '//table[@class="tbl2"]/tr/td[1]/a[@target="_blank"]/small'
        ))
        log.info("Found %d links to create blog posts.", self.total_links)
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

            self.links[filename] = {
                'href': href, 'size': size, 'filename': filename
            }


    def create_posts(self):
        self.grab_links()
        filenames = sorted(self.links.keys())
        chunker = Chunker(self.links_per_post)
        n = 1
        for chunk in chunker(filenames):
            title = self.title_base + ' %d - %d' % (n, n+len(chunk)-1)
            print
            links = []
            for filename in chunk:
                screenshot_name = filename + '.jpg'
                screenshot_path = os.path.join(self.screenshots_dir, screenshot_name)
                if not os.path.isfile(screenshot_path):
                    log.error("Screenshot %s does not exist!!!", screenshot_name)
                    continue

                log.info("Uploading screenshot %s", screenshot_name)
                browser = Browser("http://www.freeporndumpster.com/legacy.php")
                file_control = browser.getControl(name='images[]', index=0)
                file_control.add_file(
                    open(screenshot_path),
                    "image/jpeg", screenshot_name
                )
                browser.getControl('upload').click()

                doc = etree.HTML(browser.contents)
                image_html_match = doc.xpath('//table/tr/td/p[contains(., "website")]/textarea/text()')
                if not image_html_match:
                    log.error("Failed to get uploaded image html")
                    continue

                image_html_match = image_html_match[0]
                links.append((
                    filename,
                    self.links[filename]['size'],
                    self.links[filename]['href'],
                    image_html_match
                ))

            html = HTML_TEMPLATE.render(links=links)
            open(os.path.join(self.output_dir, title+'.txt'), 'w').write(html)

            print title
            print html
            n += len(chunk)
            print
            if n > 26:
                break


class Chunker(object):
    """Split `iterable` on evenly sized chunks.

    Leftovers are remembered and yielded at the next call.
    """
    def __init__(self, chunksize):
        assert chunksize > 0
        self.chunksize = chunksize
        self.chunk = []

    def __call__(self, iterable):
        """Yield items from `iterable` `self.chunksize` at the time."""
        assert len(self.chunk) < self.chunksize
        for item in iterable:
            self.chunk.append(item)
            if len(self.chunk) == self.chunksize:
                # yield collected full chunk
                yield self.chunk
                self.chunk = []


def main():

    username = password = None
    if os.path.isfile(os.path.expanduser('~/.oron')):
        cfg = SafeConfigParser()
        cfg.read([os.path.expanduser('~/.oron')])
        if cfg.has_option('DEFAULT', 'username'):
            username = cfg.get('DEFAULT', 'username')
        if cfg.has_option('DEFAULT', 'password'):
            password = cfg.get('DEFAULT', 'password')

    parser = OptionParser()
    parser.add_option('-u', '--url', help="Oron folder url")
    parser.add_option('-U', '--username', help="Oron username", default=username)
    parser.add_option('-P', '--password', help="Oron password", default=password)
    parser.add_option('-S', '--screenshots', help="Screenshots directory")
    parser.add_option('-T', '--title-base', help="Blog Post Title base")
    parser.add_option('-L', '--links-per-post', help="Blog Links Per Post",
                      type='int', default=6)
    parser.add_option('-O', '--output', help="HTML output directory")


    options, args = parser.parse_args()

    if not options.url:
        parser.error("You need to pass the Oron folder URL")
    if not options.title_base:
        parser.error("You need to provide a base title")
    if not options.screenshots:
        parser.error("You need to provide the path to the screenshots")
    if not options.output:
        parser.error("You need to provide the path to the html output directory")

    blogger = Blogger(options)
    blogger.create_posts()

if __name__ == '__main__':
    main()
