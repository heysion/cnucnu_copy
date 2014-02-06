#!/usr/bin/python -tt
# vim: fileencoding=utf8  foldmethod=marker
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

import unittest
import sys
sys.path.insert(0, '../..')

from cnucnu.package_list import unalias, ALIASES


class AliasTest(unittest.TestCase):
    def testDefaultRegex(self):
        regex = unalias("testname", "DEFAULT", "regex")
        self.assertEqual(regex, ALIASES["DEFAULT"]["regex"].format(
            name="testname"))

    def testCPAN(self):
        url = unalias("perl-test", "CPAN-DEFAULT", "url")
        self.assertEqual(url, "http://search.cpan.org/dist/test/")

        url = unalias("perl-test", "CPAN-DEFAULT:overridden-name", "url")
        self.assertEqual(url, "http://search.cpan.org/dist/overridden-name/")

    def testDebian(self):
        url = unalias("testpackage", "DEBIAN-DEFAULT", "url")
        self.assertEqual(
            url,
            "http://ftp.debian.org/debian/pool/main/t/testpackage/"
        )

    def testDrupalRegex(self):
        regex = unalias("drupal6-testpackage", "DRUPAL-DEFAULT", "regex")
        self.assertEqual(
            regex,
            "(?s)Recommended releases.*?>6.x-([^<]*)"
        )

        regex = unalias("drupal7-testpackage", "DRUPAL-DEFAULT", "regex")
        self.assertEqual(
            regex,
            "(?s)Recommended releases.*?>7.x-([^<]*)"
        )

    def testDrupalUrl(self):
        url = unalias("drupal6-testpkg", "DRUPAL-DEFAULT", "url")
        self.assertEqual(
            url,
            "http://drupal.org/project/testpkg"
        )

    def testPHPPear(self):
        url = unalias("php-pear-Test-Case", "PEAR-DEFAULT", "url")
        self.assertEqual(
            url,
            "http://pear.php.net/package/Test_Case/download"
        )


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(AliasTest)
    unittest.TextTestRunner(verbosity=2).run(suite)
    #unittest.main()
