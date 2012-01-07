# -*- coding: utf-8 -*-
"""
    oron.uploader
    ~~~~~~~~~~~~~

    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

from __future__ import division

import os
import sys
import shutil
import logging
import mimetypes
import subprocess
from optparse import OptionParser
from ConfigParser import SafeConfigParser
from oron.utils import OronLinksParser

logging.basicConfig(format='%(message)s', level=logging.DEBUG)

log = logging.getLogger(__name__)

class OronUploader(object):
    def __init__(self, username, password, source_dirs, rate, compare_url=None,
                 move_uploaded=True, match_mimetype='video'):
        self.username = username
        self.password = password
        if source_dirs is []:
            source_dirs = [os.getcwd()]
        self.source_dirs = source_dirs
        self.rate = rate
        self.uploaded_filenames = []
        if compare_url is not None:
            links_parser = OronLinksParser(compare_url)
            links_parser.parse()
            self.uploaded_filenames = links_parser.filenames.keys()
        self.move_uploaded = move_uploaded
        self.match_mimetype = match_mimetype
        self.uploaded = 0
        self.files_to_upload = set()
        self.errors = 0

        self.search_files_to_upload()
        log.info("Found %d files to upload", len(self.files_to_upload))

    def search_files_to_upload(self):
        msg = "Search files to upload"
        if self.match_mimetype:
            msg += " matching mimetype \"%s\"" % self.match_mimetype
        log.info(msg+'...')
        for source_dir in self.source_dirs:
            for pname in os.listdir(source_dir):
                if pname == '.url.txt':
                    continue
                elif pname in self.uploaded_filenames:
                    continue
                pname_path = os.path.join(source_dir, pname)
                mimetype = mimetypes.guess_type(pname_path)
                if os.path.islink(pname_path):
                    continue
                elif os.path.isdir(pname_path):
                    continue
                elif self.match_mimetype and not filter(None, mimetype):
                    continue
                elif self.match_mimetype and mimetype and self.match_mimetype not in mimetype[0]:
                    continue
                elif os.path.isfile(pname_path):
                    self.files_to_upload.add(pname_path)

    def upload(self):
        for fpath in self.files_to_upload:
            log.info("Uploading %s at a max rate of %sK/s...",
                     os.path.basename(fpath), self.rate)
            retcode = subprocess.call([
                "lftp",
                "%s:%s@ftp.oron.com" % (self.username, self.password),
                "-e",
                "set net:limit-rate 0:%s; put %s; exit" % (self.rate*1024, fpath)
            ])

            if retcode != 0:
                log.error("Something went wrong. exiting.....")
                self.errors += 1
                if self.errors > 3:
                    sys.exit(1)
                continue
            else:
                self.errors = 0

            if self.move_uploaded:
                uploaded_path = os.path.join(os.path.dirname(fpath, 'upped'))
                if not os.path.isdir(uploaded_path):
                    os.makedirs(uploaded_path)
                shutil.move(fpath, self.uploaded_path)
            self.uploaded += 1
            log.info("Uploaded %s of %s files",
                     self.uploaded, len(self.files_to_upload))


def main():
    username = password = None
    rate = 90
    if os.path.isfile(os.path.expanduser('~/.oron')):
        cfg = SafeConfigParser()
        cfg.read([os.path.expanduser('~/.oron')])
        if cfg.has_option('DEFAULT', 'username'):
            username = cfg.get('DEFAULT', 'username')
        if cfg.has_option('DEFAULT', 'password'):
            password = cfg.get('DEFAULT', 'password')
        if cfg.has_option('DEFAULT', 'upload-rate'):
            rate = cfg.get('DEFAULT', 'upload-rate')


    parser = OptionParser()
    parser.add_option('-U', '--username', help="Oron username", default=username)
    parser.add_option('-P', '--password', help="Oron password", default=password)
    parser.add_option('-s', '--source-dir', default=[], action='append',
                      help="Downloads destination directory")
    parser.add_option('-r', '--upload-rate', default=rate, type='int',
                      help="Upload rate. Default: %default KB/s")
    parser.add_option('-u', '--compare-url', default=None,
                      help="The oron folder url to compare for already "
                           "uploaded files")
    parser.add_option('-d', '--dont-move-uploaded', default=False,
                      action='store_true', help="Don't move uploaded files")
    parser.add_option('-m', '--match-mimetype', default=None, help='Match specific mimetype')

    options, args = parser.parse_args()
    if not options.source_dir and not args:
        parser.error("You need to pass the path to upload from")


    uploader = OronUploader(
        options.username, options.password, options.source_dir,
        options.upload_rate, compare_url=options.compare_url,
        move_uploaded=not options.dont_move_uploaded,
        match_mimetype=options.match_mimetype
    )
    uploader.upload()

if __name__ == '__main__':
    main()
