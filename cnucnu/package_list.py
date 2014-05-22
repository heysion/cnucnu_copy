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
""" :author: Till Maas
    :contact: opensource@till.name
    :license: GPLv2+
"""
__docformat__ = "restructuredtext"

# python default modules
import fnmatch
import re
# sre_constants contains re exceptions
import sre_constants
import string
import subprocess

#extra modules
import pycurl
import pkgdb2client

# cnucnu modules
import cnucnu
from cnucnu.bugzilla_reporter import BugzillaReporter
from cnucnu.config import global_config
import cnucnu.errors as cc_errors
from cnucnu import helper
from cnucnu.helper import cmp_upstream_repo, get_html, expand_subdirs, \
    upstream_max
from cnucnu.scm import SCM
from cnucnu.wiki import MediaWiki


class Repository:
    def __init__(self, name="", path=""):
        if not (name and path):
            c = global_config.config["repo"]
            name = c["name"]
            path = c["path"]

        self.name = name
        self.path = path
        self.repoid = "cnucnu-%s" % "".join(
            c for c in name if c in string.letters)

        self.repofrompath = "%s,%s" % (self.repoid, self.path)

        self._nvr_dict = None

    @property
    def nvr_dict(self):
        if not self._nvr_dict:
            self._nvr_dict = self.repoquery()
        return self._nvr_dict

    def repoquery(self, package_names=[]):
        # TODO: get rid of repofrompath message even with --quiet
        cmdline = ["/usr/bin/repoquery",
                   "--quiet",
                   "--archlist=src",
                   "--all",
                   "--repoid",
                   self.repoid,
                   "--qf",
                   "%{name}\t%{version}\t%{release}"]
        if self.repofrompath:
            cmdline.extend(['--repofrompath', self.repofrompath])
        cmdline.extend(package_names)

        repoquery = subprocess.Popen(cmdline, stdout=subprocess.PIPE)
        (list_, stderr) = repoquery.communicate()
        new_nvr_dict = {}
        for line in list_.split("\n"):
            if line != "":
                name, version, release = line.split("\t")
                new_nvr_dict[name] = (version, release)
        return new_nvr_dict

    def package_version(self, package):
        try:
            return self.nvr_dict[package.name][0]
        except KeyError:
            raise cc_errors.PackageNotFoundError(
                "package '%s' not found in repository '%s' (%s)" % (
                    package.name, self.name, self.path))

    def package_release(self, package):
        return self.nvr_dict[package.name][1]


class Package(object):
    def __init__(self, name, regex, url, repo=Repository(), scm=SCM(),
                 br=BugzillaReporter(), package_list=None):
        # :TODO: add some sanity checks
        self.name = name

        self.raw_regex = regex
        self.regex = regex
        self.raw_url = url
        self.url = url
        self.repo = repo
        self.repo_name = repo.name
        self.scm = scm
        self.br = br
        self.package_list = package_list

        self._html = None
        self._latest_upstream = None
        self._upstream_versions = None
        self._repo_version = None
        self._repo_release = None
        self._rpm_diff = None

    def _invalidate_caches(self):
        self._latest_upstream = None
        self._upstream_versions = None
        self._rpm_diff = None

    def __str__(self):
        return "%(name)s: repo=%(repo_version)s "\
            "upstream=%(latest_upstream)s" % self

    def __repr__(self):
        return "%(name)s %(regex)s %(url)s" % self

    def __getitem__(self, key):
        return getattr(self, key)

    def set_regex(self, regex):
        self.raw_regex = regex
        regex = cnucnu.unalias(self.name, regex, "regex")
        self.__regex = regex
        self._invalidate_caches()

    regex = property(lambda self: self.__regex, set_regex)

    def set_url(self, url):
        self.raw_url = url
        url = cnucnu.unalias(self.name, url, "url")
        self.__url = url
        self.html = None

    url = property(lambda self: self.__url, set_url)

    def set_html(self, html):
        self._html = html
        self._invalidate_caches()

    def get_html(self):
        if not self._html:
            try:
                self.__url = expand_subdirs(self.url)
                html = get_html(self.url)
            # TODO: get_html should raise a generic retrieval error
            except IOError:
                raise cc_errors.UpstreamVersionRetrievalError(
                    "%(name)s: IO error while retrieving upstream URL. - "
                    "%(url)s - %(regex)s" % self)
            except pycurl.error, e:
                raise cc_errors.UpstreamVersionRetrievalError(
                    "%(name)s: Pycurl while retrieving upstream URL. - "
                    "%(url)s - %(regex)s" % self + " " + str(e))
            self._html = html
        return self._html

    html = property(get_html, set_html)

    @property
    def upstream_versions(self):
        if not self._upstream_versions:
            try:
                upstream_versions = re.findall(self.regex, self.html)
            except sre_constants.error:
                raise cc_errors.UpstreamVersionRetrievalError(
                    "%s: invalid regular expression" % self.name)
            for index, version in enumerate(upstream_versions):
                if type(version) == tuple:
                    version = ".".join([v for v in version if not v == ""])
                    upstream_versions[index] = version
                if " " in version:
                    raise cc_errors.UpstreamVersionRetrievalError(
                        "%s: invalid upstream version:>%s< - %s - %s " % (
                            self.name, version, self.url, self.regex))
            if len(upstream_versions) == 0:
                raise cc_errors.UpstreamVersionRetrievalError(
                    "%(name)s: no upstream version found. - %(url)s - "
                    "%(regex)s" % self)

            self._upstream_versions = upstream_versions

            # invalidate sub caches
            self._latest_upstream = None
            self._rpm_diff = None

        return self._upstream_versions

    @property
    def latest_upstream(self):
        if not self._latest_upstream:
            self._latest_upstream = upstream_max(self.upstream_versions)

            # invalidate _rpm_diff cache
            self._rpm_diff = None

        return self._latest_upstream

    @property
    def nagging(self):
        return self.name not in self.package_list.ignore_packages

    @property
    def repo_version(self):
        if not self._repo_version:
            self._repo_version = self.repo.package_version(self)
        return self._repo_version

    @property
    def repo_release(self):
        if not self._repo_release:
            self._repo_release = self.repo.package_release(self)
        return self._repo_release

    @property
    def rpm_diff(self):
        if not self._rpm_diff:
            self._rpm_diff = cmp_upstream_repo(self.latest_upstream,
                                               (self.repo_version,
                                                self.repo_release))
        return self._rpm_diff

    @property
    def upstream_newer(self):
        return self.rpm_diff == 1

    @property
    def repo_newer(self):
        return self.rpm_diff == -1

    @property
    def status(self):
        if self.upstream_newer:
            return "(outdated)"
        elif self.repo_newer:
            return "(%(repo_name)s newer)" % self
        else:
            return ""

    @property
    def upstream_version_in_scm(self):
        return self.scm.has_upstream_version(self)

    @property
    def exact_outdated_bug(self):
        return self.br.get_exact_outdated_bug(self)

    @property
    def open_outdated_bug(self):
        return self.br.get_open_outdated_bug(self)

    def report_outdated(self, dry_run=True):
        if self.nagging:
            if not self.upstream_newer:
                print "Upstream not newer, report_outdated aborted!", str(self)
                return None

            if self.upstream_version_in_scm:
                print "Upstream Version found in SCM, skipping bug report: "\
                    "%(name)s U:%(latest_upstream)s R:%(repo_version)s" % self
                return None

            return self.br.report_outdated(self, dry_run)
        else:
            print "Nagging disabled for package: %s" % str(self)
            return None


class PackageList:
    def __init__(self, repo=Repository(), scm=SCM(), br=BugzillaReporter(),
                 mediawiki=False, packages=None):
        """ A list of packages to be checked.

        :Parameters:
            repo : `cnucnu.Repository`
                Repository to compare with upstream
            scm : `cnucnu.SCM`
                SCM to compares sources files with upstream version
            mediawiki : dict
                Get a list of package names, urls and regexes from a mediawiki
                page defined in the dict.
            packages : [cnucnu.Package]
                List of packages to populate the package_list with

        """
        self.ignore_owners = []
        self._ignore_packages = None

        if not mediawiki:
            mediawiki = global_config.config["package list"]["mediawiki"]
        if not packages and mediawiki:

            w = MediaWiki(base_url=mediawiki["base url"])
            page_text = w.get_pagesource(mediawiki["page"])

            ignore_owner_regex = re.compile('\\* ([^ ]*)')
            self.ignore_owners = [
                o[0].encode("UTF-8") for o in
                helper.match_interval(page_text, ignore_owner_regex,
                                      "== Package Owner Ignore List ==",
                                      "<!-- END PACKAGE OWNER IGNORE LIST -->")
            ]

            packages = []
            repo.package_list = self
            package_line_regex = re.compile(
                '^\s+\\*\s+(\S+)\s+(.+?)\s+(\S+)\s*$')
            for package_data in helper.match_interval(
                page_text, package_line_regex,
                    "== List Of Packages ==", "<!-- END LIST OF PACKAGES -->"):
                (name, regex, url) = package_data
                matched_names = fnmatch.filter(repo.nvr_dict.keys(), name)
                if len(matched_names) == 0:
                    # Add non-matching name to trigger an error/warning later
                    # FIXME: Properly report bad names
                    matched_names = [name]
                for name in matched_names:
                    packages.append(
                        Package(name, regex, url, repo, scm, br,
                                package_list=self))

        self.packages = packages
        self.append = self.packages.append
        self.__len__ = self.packages.__len__

    @property
    def ignore_packages(self):
        if self._ignore_packages is None:
            pkgdb = pkgdb2client.PkgDB()
            ignore_packages = []
            for owner in self.ignore_owners:
                try:
                    # raises PkgDBException if owner is no point of contact for
                    # any package
                    pkgs = pkgdb.get_packages(poc=owner)["packages"]
                    p_names = [p["name"] for p in pkgs]
                    ignore_packages.extend(p_names)
                except pkgdb2client.PkgDBException:
                    pass
            ignore_packages = set(ignore_packages)
            self._ignore_packages = ignore_packages
        return self._ignore_packages

    def __getitem__(self, key):
        if isinstance(key, int):
            return self.packages[key]
        elif isinstance(key, str):
            for p in self.packages:
                if p.name == key:
                    return p
            raise KeyError("Package %s not found" % key)

    def get(self, key, default=None):
        try:
            return self.__getitem__(key)
        except KeyError:
            return default


if __name__ == '__main__':
    pl = PackageList()
    p = pl.packages[0]
    print p.upstream_versions
