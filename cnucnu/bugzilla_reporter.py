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

from bugzilla import Bugzilla
from config import global_config
from helper import filter_dict

import logging
log = logging.getLogger('cnucnu.bugzilla_reporter')


class BugzillaReporter(object):
    base_query = {'query_format': 'advanced',
                  'emailreporter1': '1', 'emailtype1': 'exact'}

    bug_status_open = ['NEW', 'ASSIGNED', 'MODIFIED', 'ON_DEV', 'ON_QA',
                       'VERIFIED', 'FAILS_QA', 'RELEASE_PENDING', 'POST']
    bug_status_closed = ['CLOSED']

    new_bug = {}

    def __init__(self, config=None):
        self._bz = None

        if not config:
            config = global_config.bugzilla_config
        self.config = config

        self.base_query['product'] = config['product']
        self.base_query['email1'] = config['user']
        self.new_bug['product'] = config['product']
        if "keywords" in config:
            self.new_bug['keywords'] = config['keywords']
        self.new_bug['version'] = config['version']
        self.new_bug['op_sys'] = 'Unspecified'
        self.new_bug['platform'] = 'Unspecified'
        self.new_bug['bug_severity'] = 'unspecified'
        # Using ASSIGNED returns an exception:
        # <Fault 32000: 'You are not allowed to file new bugs with the\n
        #  ASSIGNED status.'>
        # if the account is in editbugs, fedora_bugs, fedora_contrib,
        # setpriority
        # if not, then it is silently ignored
        #               'status': 'ASSIGNED',
        # Red Hat Bugzilla now supports filing bugs in state ASSIGNED:
        # https://bugzilla.redhat.com/show_bug.cgi?id=516208
        self.new_bug['status'] = self.config['bug status']

        self.bugzilla_username = config['user']

    @property
    def bz(self):
        if not self._bz:
            rpc_conf = filter_dict(self.config, ["url", "user", "password"])
            self._bz = Bugzilla(**rpc_conf)
        return self._bz

    def bug_url(self, bug):
        if isinstance(bug, str):
            bug_id = bug
        else:
            bug_id = bug.bug_id

        return "%s%s" % (self.config['bug url prefix'], bug_id)

    def report_outdated(self, package, dry_run=True):
        if not package.exact_outdated_bug:
            if not package.open_outdated_bug:
                new_bug, change_status = self.create_outdated_bug(package,
                                                                  dry_run)
                return self.bug_url(new_bug)
            else:
                open_bug = package.open_outdated_bug
                short_desc = open_bug.short_desc

                # short_desc should be '<name>-<version> <some text>'
                # To extract the version get everything before the first space
                # with split and then remove the name and '-' via slicing
                bug_version = short_desc.split(" ")[0][len(package.name) + 1:]

                if bug_version != package.latest_upstream:
                    update = {'summary': self.config["short_desc template"]
                              % package,
                              'comment': {'body':
                                          self.config["description template"] %
                                          package, 'is_private': False},
                              'ids': [open_bug.bug_id],
                              }
                    log.debug("About to update bug '%s' with '%r'" % (
                        open_bug.bug_id, update))
                    res = self.bz._proxy.Bug.update(update)
                    log.debug("Result from bug update: %r" % res)
                    log.info("Updated bug: %s" % self.bug_url(open_bug))
                    return self.bug_url(open_bug)
        else:
            bug = package.exact_outdated_bug
            log.info("already reported:%s %s" % (self.bug_url(bug),
                                                 bug.bug_status))
            return ""

    def create_outdated_bug(self, package, dry_run=True):
        bug_dict = {
            'component': package.name,
            'short_desc': self.config["short_desc template"] % package,
            'description': self.config["description template"] % package
        }
        bug_dict.update(self.new_bug)
        if not dry_run:
            new_bug = self.bz.createbug(**bug_dict)
            change_status = None
            log.debug("Created new bug: %r" % new_bug)
            log.info("Created bug: %s" % self.bug_url(new_bug))

            if new_bug.bug_status != self.config['bug status']:
                change_status = self.bz._proxy.bugzilla.changeStatus(
                    new_bug.bug_id, self.config['bug status'],
                    self.config['user'], "", "", False, False, 1)
                log.debug("Changed bug status %r" % change_status)
            return (new_bug, change_status)
        else:
            return (bug_dict, None)

    def get_exact_outdated_bug(self, package):
        short_desc_pattern = '%(name)s-%(latest_upstream)s ' % package
        query = {'component': package.name,
                 'bug_status': self.bug_status_open + self.bug_status_closed,
                 'short_desc': short_desc_pattern,
                 'short_desc_type': 'substring'}

        query.update(self.base_query)
        logging.debug("get_exact_outdated_bug: Bugzilla query: %s", query)
        bugs = self.bz.query(query)
        if bugs:
            # TODO if more than one bug, manual intervention might be required
            for bug in bugs:
                # The short_desc_pattern contains a space at the end, which is
                # currently not recognized by bugzilla. Therefore this test is
                # required:
                if bug.short_desc.startswith(short_desc_pattern):
                    return bug

        # not matching bug found
        return None

    def get_open_outdated_bug(self, package):
        q = {'component': [package.name],
             'bug_status': [self.config['bug status']]
             }

        q.update(self.base_query)
        bugs = self.bz.query(q)
        if bugs:
            # TODO if more than one bug, manual intervention is required
            return bugs[0]
        else:
            return bugs
