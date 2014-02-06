#!/usr/bin/python
# vim: fileencoding=utf8 foldmethod=marker
# {{{ License header: GPLv2+
#    This file is part of cnucnu.
#
#    Cnucnu is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 2 of the License, or
#    (at your option) any later version.
#
#    Cnucnu is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with cnucnu.  If not, see <http://www.gnu.org/licenses/>.
# }}}

import cmd
import difflib
import getpass
import re
import readline
import sys
import thread

import simplemediawiki

from package_list import Package, PackageList, Repository
from bugzilla_reporter import BugzillaReporter
from helper import pprint
from scm import SCM
from errors import UpstreamVersionRetrievalError, PackageNotFoundError

try:
    import fedora_cert
except ImportError:
    pass


def diff(a, b):
    differ = difflib.Differ()
    diff_result = differ.compare(a.splitlines(True), b.splitlines(True))
    diff_lines = [l for l in diff_result if not l.startswith(" ")]
    return diff_lines


class WikiEditor(object):
    def __init__(self, config):

        try:
            mediawiki = config["package list"]["mediawiki"]
        except KeyError:
            raise NotImplementedError("Only mediawiki support available")

        base_url = mediawiki["base url"]
        api_url = base_url + "api.php"
        page = mediawiki["page"]

        self.logged_in = False
        self.mw = simplemediawiki.MediaWiki(api_url)
        self.page = page

    def _query(self, data):
        base_query = {'action': 'query', 'titles': self.page}
        base_query.update(data)
        return self.mw.call(base_query)['query']['pages'].popitem()[1]

    def update(self, name, data, callback, reason=""):
        if not self.logged_in:
            try:
                try:
                    fas_username = fedora_cert.read_user_cert()
                except (fedora_cert.fedora_cert_error):
                    raise NameError
            except NameError:
                fas_username = getpass.getuser("FAS username: ")

            self.mw.login(
                fas_username,
                getpass.getpass("Password for FAS user '{0}': ".format(
                    fas_username)))
            self.logged_in = True

        meta_data = self._query({'prop': 'info|revisions',
                                 'intoken': 'edit'})

        source = self._query(
            {'prop': 'revisions',
                'rvprop': 'content'})['revisions'][0]['*']

        starttimestamp = meta_data["starttimestamp"]
        edittoken = meta_data["edittoken"]

        pattern = r'\n \* {0} [^\n]*\n'.format(name)

        if data:
            repl = "\n * {0}\n".format(data)
            what = "Update"
        else:
            repl = "\n"
            what = "Remove"
        if reason:
            reason = " - {0}".format(reason)
        summary = "{0} {1}{2}".format(what, name, reason)

        new_text = re.sub(pattern, repl, source, count=1)
        diff_lines = diff(source, new_text)
        if diff_lines:
            print summary
            sys.stdout.writelines(diff_lines)
            response = raw_input("Apply? (Y/n)")

            if response in ("", "y", "Y"):
                def update_thread():
                    edit = self.mw.call({'action': 'edit',
                                        'title': self.page,
                                        'text': new_text,
                                        'summary': summary,
                                        'token': edittoken,
                                        'starttimestamp': starttimestamp})
                    callback(edit)
                thread.start_new_thread(update_thread, ())
            else:
                print "Not applied"


class CheckShell(cmd.Cmd):
    def __init__(self, config):
        cmd.Cmd.__init__(self)
        readline.set_completer_delims(' ')

        self.repo = Repository()
        self.package = Package("", None, None, self.repo)
        self._package_list = None
        self.prompt_default = " URL:"
        self.update_prompt()
        self.config = config
        self._br = None
        self.scm = SCM()
        self.we = WikiEditor(config=config.config)
        self.messages = []

    @property
    def package_list(self):
        if not self._package_list:
            self._package_list = PackageList(repo=self.repo)
            if self.package.name:
                self._package_list.append(self.package)
        return self._package_list

    @property
    def br(self):
        if not self._br:
            bugzilla_config = self.config.bugzilla_config
            try:
                self._br = BugzillaReporter(bugzilla_config)

            except Exception, e:
                print "Cannot query bugzilla, maybe config is faulty or missing", repr(e), dict(e), str(e)
        return self._br

    def update_prompt(self):
        self.prompt = ""
        if "messages" in dir(self):
            while self.messages:
                message = self.messages.pop()
                self.prompt += "Message: {0}\n".format(message)
        self.prompt += "Name: {p.name}\n"\
                       "Final Regex: {p.regex}\n"\
                       "Final URL: {p.url}\n"\
                       "\x1b[1m{p.name} {p.raw_regex} {p.raw_url} ".format(
                           p=self.package)
        self.prompt += "%s>\x1b[0m " % self.prompt_default

    def default(self, line):
        if not self.package.url:
            self.do_url(line)
        else:
            self.do_regex(line)

    def do_EOF(self, args):
        self.emptyline()

    def do_fm(self, args):
        self.package.name = args
        self.package.regex = "FM-DEFAULT"
        self.package.url = "FM-DEFAULT"

    def do_html(self, args):
        print self.package.url
        print self.package.html

    def complete_inspect(self, text, line, begidx, endidx):
        package_names = [p.name for p in self.package_list if p.name.startswith(text)]
        return package_names

    def do_inspect(self, args):
        try:
            self.package = self.package_list[args]
        except KeyError, ke:
            print ke

    def do_name(self, args):
        self.package = Package(args, self.package.regex, self.package.url, self.repo)
        if not self.package.regex:
            self.package.regex = "DEFAULT"
        if not self.package.url:
            self.package.url = "SF-DEFAULT"

    def do_regex(self, args):
        self.package.regex = args

    def do_report(self, args):
        pprint(self.package.report_outdated(dry_run=False))

    def do_remove(self, args):
        self.do_update(args, entry="")

    def do_update(self, args, entry=None):
        if entry is None:
            entry = "{p.name} {p.raw_regex} {p.raw_url}".format(p=self.package)

        self.we.update(self.package.name, entry, self.messages.append,
                       reason=args)

    def do_url(self, args):
        self.package.url = args

    def emptyline(self):
        if self.package.url:
            self.package.url = None
        else:
            print
            sys.exit(0)

    def postcmd(self, stop, line):
        if not self.package.url:
            self.prompt_default = " URL:"
        else:
            self.prompt_default = " Regex:"

        self.update_prompt()
        if self.package.url and self.package.regex:
            try:
                print "Upstream Versions:", set(self.package.upstream_versions)
                print "Latest:", self.package.latest_upstream

                if self.package.name:
                    print "%(repo_name)s Version: %(repo_version)s %(repo_release)s %(status)s" % self.package

                    sourcefile = self.package.upstream_version_in_scm
                    if sourcefile:
                        print "Found in SCM:", sourcefile
                    else:
                        print "Not Found in SCM"
                    bug = self.package.exact_outdated_bug
                    if bug:
                        print "Exact Bug:", "%s %s:%s" % (self.br.bug_url(bug), bug.bug_status, bug.short_desc)
                    bug = self.package.open_outdated_bug
                    if bug:
                        print "Open Bug:", "%s %s:%s" % (self.br.bug_url(bug), bug.bug_status, bug.short_desc)
            except UpstreamVersionRetrievalError, uvre:
                print "\x1b[1mCannot retrieve upstream Version:\x1b[0m", uvre
            except PackageNotFoundError, e:
                print e
        return stop
