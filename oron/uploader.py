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
import subprocess

logging.basicConfig(format='%(message)s', level=logging.DEBUG)

log = logging.getLogger(__name__)

class OronUploader(object):
    def __init__(self, username, password, source_dir, rate):
        self.username = username
        self.password = password
        if source_dir is None:
            source_dir = os.getcwd()
        self.source_dir = source_dir
        self.rate = rate
        self.uploaded = 0
        self.uploaded_path = os.path.join(source_dir, 'upped')
        self.files_to_upload = set()
        self.errors = 0

        if not os.path.isdir(self.uploaded_path):
            os.makedirs(self.uploaded_path)

        self.search_files_to_upload()
        log.info("Found %d files to upload", len(self.files_to_upload))

    def search_files_to_upload(self):
        for pname in os.listdir(self.source_dir):
            if pname == '.url.txt':
                continue
            pname_path = os.path.join(self.source_dir, pname)
            if os.path.islink(pname_path):
                continue
            elif os.path.isdir(pname_path):
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

            shutil.move(fpath, self.uploaded_path)
            self.uploaded += 1
            log.info("Uploaded %s of %s files",
                     self.uploaded, len(self.files_to_upload))


def main():
    from optparse import OptionParser
    from ConfigParser import SafeConfigParser

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
    parser.add_option('-s', '--source-dir', default=None,
                      help="Downloads destination directory")
    parser.add_option('-r', '--upload-rate', default=rate, type='int',
                      help="Upload rate. Default: %default KB/s")

    options, args = parser.parse_args()
    if not options.source_dir and not args:
        parser.error("You need to pass the path to upload from")


    uploader = OronUploader(
        options.username, options.password, options.source_dir,
        options.upload_rate
    )
    uploader.upload()

if __name__ == '__main__':
    main()