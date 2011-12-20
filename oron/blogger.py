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
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from jinja2.environment import Template
from optparse import OptionParser, OptionGroup
from ConfigParser import SafeConfigParser
from lxml import etree
from zope.testbrowser.browser import Browser

logging.basicConfig(format='%(message)s', level=logging.DEBUG)

log = logging.getLogger(__name__)

HTML_TEMPLATE = Template("""
<p>{{ initial_text }}</p>

{% for filename, size, href, img_html in links %}
{{ img_html }}<br/>
<a href="{{ href }}">Download  &mdash; {{ filename }}({{ size }})</a>
<br/>
<br/>
{% endfor %}

<p>{{ ending_text }}</p>
""")

class Blogger(object):
    def __init__(self, options):
        self.oron_folder_url = options.url
        self.title_base = options.title_base
        self.links_per_post = options.links_per_post
        self.screenshots_dir = options.screenshots
        self.output_dir = options.output

        # Email Options
        self.smtp_host = options.smtp_host
        self.smtp_port = options.smtp_port
        self.smtp_user = options.smtp_user
        self.smtp_pass = options.smtp_pass
        self.smtp_from = options.smtp_from
        self.smtp_use_tls = options.smtp_use_tls
        self.email_recipient = options.email
        self.email_initial_text = options.email_initial_text
        self.email_ending_text = options.email_ending_text

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
        total_posts = int(round(self.total_links/(self.links_per_post*1.0)))
        n = 1
        for chunk in chunker(filenames):
            title = self.title_base + ' - %d of %d' % (n, total_posts)
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
                caption_control = browser.getControl(name='imagename[]', index=0)
                caption_control.value = self.links[filename]['href']
                file_control = browser.getControl(name='images[]', index=0)
                file_control.add_file(
                    open(screenshot_path),
                    "image/jpeg", screenshot_name
                )
                browser.getControl('upload').click()

                doc = etree.HTML(browser.contents)
                image_html = "<em>Missing Image html for <b>%s</b></em>" % filename
                image_html_match = doc.xpath('//table/tr/td/p[contains(., "website")]/textarea/text()')
                if image_html_match:
                    image_html = image_html_match[0]
                else:
                    log.error("Failed to get uploaded image html")

                links.append((
                    filename,
                    self.links[filename]['size'],
                    self.links[filename]['href'],
                    image_html
                ))

            html = HTML_TEMPLATE.render(
                links=links, initial_text=self.email_initial_text,
                ending_text=self.email_ending_text
            )
            open(os.path.join(self.output_dir, title+'.txt'), 'w').write(html)

            n += 1
            server = None
            email = MIMEMultipart('alternative')
            email['Subject'] = title
            email['From'] = 'z0rr0@sapo.pt'
            email['To'] = self.email_recipient
            email.attach(MIMEText(html, 'html'))
            log.info("Sending post email")

            try:
                try:
                    # Python 2.6
                    server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=60)
                except:
                    # Python 2.5
                    server = smtplib.SMTP(self.smtp_host, self.smtp_port)
            except Exception, err:
                log.error("There was an error sending the notification email: %s", err)

            if server is None:
                log.error("Failed to setup SMTP server")
                continue

            security_enabled = self.smtp_use_tls

            if security_enabled:
                server.ehlo()
                if not server.esmtp_features.has_key('starttls'):
                    log.warning("TLS/SSL enabled but server does not support it")
                else:
                    server.starttls()
                    server.ehlo()

            if self.smtp_user and self.smtp_pass:
                try:
                    server.login(self.smtp_user, self.smtp_pass)
                except smtplib.SMTPHeloError, err:
                    log.error("The server didn't reply properly to the helo "
                              "greeting: %s", err)
                except smtplib.SMTPAuthenticationError, err:
                    log.error("The server didn't accept the username/password "
                              "combination: %s", err)
            try:
                try:
                    server.sendmail(self.smtp_from, self.email_recipient, email.as_string())
                except smtplib.SMTPException, err:
                    log.error("There was an error sending the notification email: %s", err)
            finally:
                if security_enabled:
                    # avoid false failure detection when the server closes
                    # the SMTP connection with TLS enabled
                    import socket
                    try:
                        server.quit()
                    except socket.sslerror:
                        pass
                else:
                    server.quit()
                log.info("Notification email sent.")
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

    username = password = email_recipient = None
    smtp_host = smtp_user = smtp_pass = smtp_from = None
    smtp_use_tls = False
    smtp_port = 25
    if os.path.isfile(os.path.expanduser('~/.oron')):
        cfg = SafeConfigParser()
        cfg.read([os.path.expanduser('~/.oron')])
        if cfg.has_option('DEFAULT', 'username'):
            username = cfg.get('DEFAULT', 'username')
        if cfg.has_option('DEFAULT', 'password'):
            password = cfg.get('DEFAULT', 'password')

        if cfg.has_option('email', 'recipient'):
            email_recipient = cfg.get('email', 'recipient')
        if cfg.has_option('email', 'host'):
            smtp_host = cfg.get('email', 'host')
        if cfg.has_option('email', 'port'):
            smtp_port = cfg.getint('email', 'port')
        if cfg.has_option('email', 'user'):
            smtp_user = cfg.get('email', 'user')
        if cfg.has_option('email', 'pass'):
            smtp_pass = cfg.get('email', 'pass')
        if cfg.has_option('email', 'from'):
            smtp_from = cfg.get('email', 'from')
        if cfg.has_option('email', 'use_tls'):
            smtp_use_tls = cfg.getboolean('email', 'use_tls')

    parser = OptionParser()
    parser.add_option('-u', '--url', help="Oron folder url")
    parser.add_option('-U', '--username', help="Oron username", default=username)
    parser.add_option('-P', '--password', help="Oron password", default=password)
    parser.add_option('-S', '--screenshots', help="Screenshots directory")
    parser.add_option('-T', '--title-base', help="Blog Post Title base")
    parser.add_option('-L', '--links-per-post', help="Blog Links Per Post",
                      type='int', default=6)
    parser.add_option('-O', '--output', help="HTML output directory")

    email = OptionGroup(parser, "Email configuration")

    email.add_option('--smtp-host', default=smtp_host)
    email.add_option('--smtp-port', type='int', default=smtp_port)
    email.add_option('--smtp-user', default=smtp_user)
    email.add_option('--smtp-pass', default=smtp_pass)
    email.add_option('--smtp-from', default=smtp_from)
    email.add_option('--smtp-use-tls', default=smtp_use_tls, action='store_true')
    email.add_option('-E', '--email', help="Email receiver of the post",
                      default=email_recipient)
    email.add_option('--email-initial-text', help="Initial email text.")
    email.add_option('--email-ending-text', help="Ending email text.")
    parser.add_option_group(email)


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
