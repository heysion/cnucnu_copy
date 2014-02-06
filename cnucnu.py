#!/usr/bin/python -ttu
# vim: fileencoding=utf8 foldmethod=marker
#{{{ License header: GPLv2+
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
#}}}

import logging
import sys
import os
import pprint as pprint_module
pp = pprint_module.PrettyPrinter(indent=4)
pprint = pp.pprint

import cnucnu
import cnucnu.errors as cc_errors
from cnucnu.config import global_config
from cnucnu.package_list import Repository, PackageList
from cnucnu.checkshell import CheckShell
from cnucnu.bugzilla_reporter import BugzillaReporter
from cnucnu.scm import SCM


log = logging.getLogger('cnucnu')


class Actions(object):
    def action_report_outdated(self, args):
        """ file bugs for outdated packages """
        br = BugzillaReporter(global_config.bugzilla_config)
        repo = Repository(**global_config.config["repo"])
        scm = SCM(**global_config.config["scm"])

        pl = PackageList(repo=repo, scm=scm, br=br,
                         **global_config.config["package list"])
        package_count = len(pl)
        log.info("Checking '%i' packages", package_count)
        for number, package in enumerate(pl, start=1):
            if package.name >= args.start_with:
                log.info("checking package '%s' (%i/%i)", package.name, number,
                         package_count)
                try:
                    if package.upstream_newer:
                        print "package '%s' outdated (%s < %s)" % (
                            package.name,
                            package.repo_version,
                            package.latest_upstream
                        )
                        bug_url = package.report_outdated(dry_run=args.dry_run)
                        if bug_url:
                            print bug_url
                except cc_errors.UpstreamVersionRetrievalError, e:
                    log.error("Failed to fetch upstream information for "
                              "package '%s' (%s)" % (package.name, e.message))
                except cc_errors.PackageNotFoundError, e:
                    log.error(e)
                except Exception, e:
                    log.exception("Exception occured while processing "
                                  "package '%s':\n%s" % (package.name,
                                                         pp.pformat(e)))
            else:
                log.info("skipping package '%s'", package.name)

    def action_dump_config(self, args):
        """ dump config to stdout """
        sys.stdout.write(global_config.yaml)
        sys.exit(0)

    def action_dump_default_config(self, args):
        """ dump default config to stdout """
        sys.stdout.write(cnucnu.config.Config().yaml)
        sys.exit(0)

    def action_shell(self, args):
        """ run interactive shell """
        shell = CheckShell(config=global_config)
        while True:
            if not shell.cmdloop():
                break

    @property
    def possible(self):
        """ possible actions """
        possible_actions = {}
        for method in dir(self):
            if method.startswith("action_"):
                possible_actions[
                    method[len("action_"):].replace("_", "-")
                ] = getattr(self, method).__doc__
        return possible_actions

    def action(self, action):
        action = action.replace("-", "_")
        return getattr(self, "action_" + action)

    def do(self, action, args):
        return self.action(action)(args)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    actions = Actions()

    parser.add_argument("--config", dest="config_filename",
                        help="config_filename, e.g. for bugzilla credentials")
    parser.add_argument("--dry-run", dest="dry_run",
                        help="Do not file or change bugs",
                        default=False, action="store_true")
    parser.add_argument("--loglevel", dest="loglevel",
                        help="Specify loglevel, default: %(default)s",
                        choices=("DEBUG", "INFO", "WARNING", "ERROR",
                                 "CRITICAL"),
                        default="WARNING")
    parser.add_argument("--start-with", dest="start_with",
                        help="Start with this package when reporting bugs",
                        metavar="PACKAGE", default="")

    subparsers = parser.add_subparsers(dest="action",
                                       help='command to perform')
    possible_actions = actions.possible.items()
    possible_actions.sort()
    for action, help_text in possible_actions:
        command_parser = subparsers.add_parser(action, help=help_text)

    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.loglevel.upper()))

    # default to ./cnucnu.yaml if it exists and no config file is specified on
    # the commandline
    yaml_file = args.config_filename
    if not yaml_file:
        new_yaml_file = "./cnucnu.yaml"
        if os.access(new_yaml_file, os.R_OK):
            yaml_file = new_yaml_file

    if yaml_file:
        global_config.update_yaml_file(yaml_file)

    actions.do(args.action, args)
