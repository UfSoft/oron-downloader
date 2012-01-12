# -*- coding: utf-8 -*-
"""
    oron.downloader
    ~~~~~~~~~~~~~~~

    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

from __future__ import division

import os
import re
import sys
import socket
import urllib2
import logging
import subprocess
from optparse import OptionParser
from ConfigParser import SafeConfigParser
from lxml import etree
from zope.testbrowser.browser import Browser

logging.basicConfig(format='%(message)s', level=logging.DEBUG)

log = logging.getLogger(__name__)

class OronDownloader(object):
    def __init__(self, downloads_urls, urls_file, username, password,
                 dest_dir=None, generate_thumbs=True, font_path=None,
                 stop_at_quota=500):
        self.downloads_urls = downloads_urls
        self.urls_file = urls_file
        self.username = username
        self.password = password
        if dest_dir is None:
            dest_dir = os.getcwd()
        self.dest_dir = dest_dir
        self.generate_thumbs = generate_thumbs
        self.font_path = font_path
        self.stop_at_quota = stop_at_quota
        log.info("Starting Browser")
        self.browser = Browser("http://oron.com")
        self.to_download = 0
        self.downloaded = 0
        self.download_quota = 0
        self.downloads_until_quota_reload = 10

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
        self.load_download_quota()

    def load_download_quota(self):
        log.info("Loading download quota...")
        self.browser.open("http://oron.com/?op=my_account")
        doc = etree.HTML(self.browser.contents)
        quota_string_match = doc.xpath('//form/table/tr[3]/td[2]/text()')
        if quota_string_match:
            self.download_quota = int(quota_string_match[0].split()[0])
            log.info("You have %d Mb of download quota.", self.download_quota)
        else:
            log.error("Failed to retrieve download quota!")
            sys.exit(1)

    def check_quota(self):
        if self.download_quota <= self.stop_at_quota:
            log.info("Download quota is now %d. Stop downloading for now...",
                     self.download_quota)
            sys.exit(0)

        if not self.downloads_until_quota_reload:
            self.downloads_until_quota_reload = 10
            self.load_download_quota()
        else:
            self.downloads_until_quota_reload -= 1

    def download(self):
        self.login()
        self.check_quota()
        if self.urls_file:
            log.info("Opening download URLs file: %s", self.urls_file)
            self.find_download_links_from_file()
        else:
            log.info("Processing %d oron folder urls", len(self.downloads_urls))
            for url in self.downloads_urls:
                log.info("Opening downloads URL: %s", url)
                self.browser.open(url)
                self.find_download_links(self.browser.contents)


    def find_download_links_from_file(self):
        urls = open(self.urls_file, 'r').readlines(True)
        self.to_download = len([u for u in urls if u.strip()])
        log.info("Processing %d oron file urls", self.to_download)

        for url in urls:
            if not url.strip():
                continue
            url = url.strip()
            log.info('-'*78)
            log.info("Opening URL: %s", url)
            self.browser.open(url.strip())
            doc = etree.HTML(self.browser.contents)
            info_node = node = doc.xpath('//div[@class="content"]/form/table/tr/td')
            #log.info("Info node match: %s", info_node)
            if info_node:
                info_node = info_node[0]
            else:
                file_not_found_match = doc.xpath('//h2/text()')
                if file_not_found_match:
                    log.error("File was not found on server. Skipping...")
                else:
                    log.error("Could not find out the filename. Skipping...")
                continue

            filename_match = info_node.xpath('./b/text()')
            #log.info("filename match is %s", filename_match)
            if filename_match:
                filename = filename_match[0].encode('utf8')

            size = info_node.xpath('./text()')[-1].strip().split('File size:')[-1].strip().upper()

            fpath = os.path.join(self.dest_dir, filename)
            spath = os.path.join(self.dest_dir, 'seen', filename)
            upath = os.path.join(self.dest_dir, 'upped', filename)
            uspath = os.path.join(self.dest_dir, 'upped-n-seen', filename)
            usnpath = os.path.join(self.dest_dir, 'upped-not-seen', filename)

            process_next = False
            for path in (fpath, spath, upath, uspath, usnpath):
                try:
                    if os.path.isfile(path):
                        if self.humanize_bytes(os.path.getsize(path)) == size:
                            log.info("Filename %s already downloaded(%s). Skipping...",
                                     filename, path)
                            self.downloaded += 1
                            process_next = True
                            break
                        log.info("Downloaded %s/%s of %s so far. Continuing...",
                                 self.humanize_bytes(os.path.getsize(path)), size,
                                 filename)
                except UnicodeEncodeError:
                    print 'Unicode error for filename', filename
                    process_next = True
                    break
            if process_next:
                continue

            errors = 1
            while errors <= 4:
                log.info("Processing[%s] %s from %s", errors, filename, url)
                try:
                    self.download_link(url)
                    break
                except (socket.error, urllib2.URLError), err:
                    log.error("Failed to download link: %s", err)
                    errors += 1
            else:
                log.info("Too many errors, continue to next link")
                continue

            if self.generate_thumbs:
                self.generate_thumb(filename)

            self.download_quota -= round(float(
                os.path.getsize(os.path.join(self.dest_dir, filename))
            )/1024/1024, 1)

            if self.download_quota <= self.stop_at_quota:
                log.info("Download quota is now %d. Stop downloading for now...",
                         self.download_quota)
                sys.exit(0)

            if not self.downloads_until_quota_reload:
                self.downloads_until_quota_reload = 10
                self.load_download_quota()
            else:
                self.downloads_until_quota_reload -= 1


    def find_download_links(self, contents):
        log.info("Searching for download links")
        doc = etree.HTML(contents)
        self.to_download = len(doc.xpath(
            '//table[@class="tbl2"]/tr/td[1]/a[@target="_blank"]/small'
        ))
        log.info("Found %d links to download.", self.to_download)
        trs = doc.xpath('//table[@class="tbl2"]/tr')
        for tr in trs:
            link_td = tr.xpath('td[1]/a')
            size_td = tr.xpath('td[2]/small/nobr/text()')
            if not link_td or not size_td:
                continue

            filename_search = link_td[0].xpath('small/text()')
            if not filename_search:
                continue
            log.info('-'*78)
            filename = filename_search[0]

            href = link_td[0].attrib['href']
            size = size_td[0].upper()
            fpath = os.path.join(self.dest_dir, filename)
            upath = os.path.join(self.dest_dir, 'upped', filename)
            uspath = os.path.join(self.dest_dir, 'upped-n-seen', filename)
            usnpath = os.path.join(self.dest_dir, 'upped-not-seen', filename)

            process_next = False
            for path in (fpath, upath, uspath, usnpath):
                if os.path.isfile(path):
                    if self.humanize_bytes(os.path.getsize(path)) == size:
                        log.info("Filename %s already downloaded(%s). Skipping...",
                                 filename, path)
                        self.downloaded += 1
                        process_next = True
                        break
                    log.info("Downloaded %s/%s of %s so far. Continuing...",
                             self.humanize_bytes(os.path.getsize(path)), size,
                             filename)
            if process_next:
                continue

            errors = 1
            while errors <= 4:
                log.info("Processing[%s] %s from %s", errors, filename, href)
                try:
                    self.download_link(href)
                    break
                except (socket.error, urllib2.URLError), err:
                    log.error("Failed to download link: %s", err)
                    errors += 1
            else:
                log.info("Too many errors, continue to next link")
                continue

            if self.generate_thumbs:
                self.generate_thumb(filename)

            self.download_quota -= round(float(
                os.path.getsize(os.path.join(self.dest_dir, filename))
            )/1024/1024, 1)

            self.check_quota()


    def download_link(self, href):
        log.info("Generating URL...")
        self.browser.open(href)
        self.browser.getForm(name='F1').submit(" Create Download Link ")
        self.browser.getLink("Download File")
        fdoc = etree.HTML(self.browser.contents)
        wget_links = fdoc.xpath('//table/tr/td/a[@class="atitle"]')
        for wget_link in wget_links:
            print 'Gathered Link HREFs',
            try:
                print wget_link, wget_link.attrib['href']
            except Exception:
                pass
            href = wget_link.attrib['href']
        log.info("Generated URL: %s", href)
        subprocess.call(["wget", "-c", href ])
        self.downloaded += 1
        log.info("Downloaded %s/%s", self.downloaded, self.to_download)

    def humanize_bytes(self, bytes, precision=1):
        """Return a humanized string representation of a number of bytes.

            Assumes `from __future__ import division`.

            >>> humanize_bytes(1)
            '1 byte'
            >>> humanize_bytes(1024)
            '1.0 kB'
            >>> humanize_bytes(1024*123)
            '123.0 kB'
            >>> humanize_bytes(1024*12342)
            '12.1 MB'
            >>> humanize_bytes(1024*12342,2)
            '12.05 MB'
            >>> humanize_bytes(1024*1234,2)
            '1.21 MB'
            >>> humanize_bytes(1024*1234*1111,2)
            '1.31 GB'
            >>> humanize_bytes(1024*1234*1111,1)
            '1.3 GB'
        """
        abbrevs = (
            (1<<50L, 'PB'),
            (1<<40L, 'TB'),
            (1<<30L, 'GB'),
            (1<<20L, 'MB'),
            (1<<10L, 'kB'),
            (1, 'bytes')
        )
        if bytes == 1:
            return '1 byte'
        for factor, suffix in abbrevs:
            if bytes >= factor:
                break
        return '%.*f %s' % (precision, bytes / factor, suffix)

    def generate_thumb(self, filename):
        log.info("Generating thumbs for %s", filename)
        screenshots_dest_dir = os.path.join(self.dest_dir, 'screenshots')
        if not os.path.isdir(screenshots_dest_dir):
            os.makedirs(screenshots_dest_dir)

        cmd = subprocess.Popen([
            'mplayer', '-vo', 'null', '-ao', 'null', '-frames', '0',
            '-identify', os.path.join(self.dest_dir, filename)
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        output = cmd.stdout.read()
        match = re.search(r'ID_LENGTH=([\d\.]+)', output)
        try:
            skip_length = int(round(float(match.group(1))))/12
        except Exception, err:
            self.generate_thumbs = False
            log.warn("Something went wrong parsing video length. "
                     "Disabling thumbs generation.")
            print ''.join(['---8<'*30, '---'])
            log.exception(err)
            print ''.join(['---8<'*30, '---'])
            output
            print ''.join(['---8<'*30, '---'])
            return

        try:
            args = [
                'mtn', '-f', self.font_path,
                '-r', '4',
                '-o', '%s.jpg' % os.path.splitext(filename)[-1],
                '-O', screenshots_dest_dir,
                '-D', '8',
                '-g', '2',
                '-b', '0.5',
                '-s', str(skip_length),
                os.path.join(self.dest_dir, filename)
            ]
            #log.debug("CMDLINE: %s", ' '.join(args))
            subprocess.call(args, stderr=subprocess.PIPE)
        except Exception, err:
            log.warn("Something went wrong while generating thumbs. "
                     "Disabling thumbs generation.")
            self.generate_thumbs = False
            log.exception(err)


def main():
    username = password = font = None
    stop_at_quota = 500
    if os.path.isfile(os.path.expanduser('~/.oron')):
        cfg = SafeConfigParser()
        cfg.read([os.path.expanduser('~/.oron')])
        if cfg.has_option('DEFAULT', 'username'):
            username = cfg.get('DEFAULT', 'username')
        if cfg.has_option('DEFAULT', 'password'):
            password = cfg.get('DEFAULT', 'password')
        if cfg.has_option('DEFAULT', 'font'):
            font = cfg.get('DEFAULT', 'font', None)
        if cfg.has_option('DEFAULT', 'stop_at_quota'):
            stop_at_quota = cfg.get('DEFAULT', 'stop_at_quota')


    parser = OptionParser()
    parser.add_option('-u', '--url', help="Oron download url", action="append", default=[])
    parser.add_option('-f', '--urls-file', help="Oron download urls file")
    parser.add_option('-U', '--username', help="Oron username", default=username)
    parser.add_option('-P', '--password', help="Oron password", default=password)
    parser.add_option(
        '-Q', '--stop-at-quota', type="int", default=stop_at_quota,
        help="Stop downloading when quota reaches this value."
    )
    parser.add_option(
        '-d', '--dest-dir', help="Downloads destination directory",
        default=None
    )
    parser.add_option(
        '-t', '--generate-thumbs', action='store_true', default=False,
        help='Generate thumbnail previews of the downloaded videos',
    )
    parser.add_option(
        '-F', '--font', default=font,
        help="Font path to generate the screenshots"
    )

    options, args = parser.parse_args()
    if not options.url and options.dest_dir:
        download_url_file = os.path.join(options.dest_dir, '.url.txt')
        if os.path.isfile(download_url_file):
            for line in open(download_url_file, 'r').readlines():
                options.url.append(line.strip())

    if not (options.url or options.urls_file):
        if not options.url:
            parser.error("You need to pass the Oron downloads URL")
        elif not options.urls_files:
            parser.error("You need to pass the Oron download URLs file")
        else:
            parser.error("You need to pass either the Oron downloads URL or "
                         "the Oron downloads URLs file")
    elif not options.username:
        parser.error("You need to pass the Oron username")
    if not options.password:
        parser.error("You need to pass the Oron password")
    if options.generate_thumbs and not options.font:
        parser.error("You need to pass the font path")

    #if options.url and os.path.isfile(options.url):
    #    options.url = open(options.url, 'r').read().strip()

    downloader = OronDownloader(options.url, options.urls_file,
                                options.username, options.password,
                                options.dest_dir, options.generate_thumbs,
                                options.font, options.stop_at_quota)

    try:
        downloader.download()
    except KeyboardInterrupt:
        log.info("CTRL-C pressed. Exiting...")

if __name__ == '__main__':
    main()

