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
import re
import urllib


def restore_underscore(name):
    return name.replace("-", "_")


ALIASES = {
    "CPAN-DEFAULT": {
        "prefix": "perl-",
        "url": "http://search.cpan.org/dist/{name}/",
    },
    "DEBIAN-DEFAULT": {
        "url": "http://ftp.debian.org/debian/pool/main/{name[0]}/{name}/",
    },
    "DEFAULT": {
        "regex":
        r"(?i)"  # ignore case
        r"\b{name}[-_]"  # word-boundary, name and dash/underscore
        r"(?:(?:src|source)[-_])?"  # optional src or source string
        r"([^-/_\s]*?"  #
        r"\d"
        r"[^-/_\s]*?)"
        r"(?:[-_.](?:src|source|orig))?"
        r"\.(?:[jt]ar|t[bglx]z|tbz2|zip)\b"
    },
    "DIR-LISTING-DEFAULT": {
        "regex": 'href="([0-9][0-9.]*)/"'
    },
    "DRUPAL-DEFAULT": {
        "prefix": ["drupal6-", "drupal7-"],
        "regex": "(?s)Recommended releases.*?>{raw_name[6]}.x-([^<]*)",
        "url": "http://drupal.org/project/{name}",
    },
    "FM-DEFAULT": {
        "regex": '<a href="/projects/[^/]*/releases/[0-9]*">([^<]*)</a>',
        "url": "http://freshmeat.net/projects/{name}",
    },
    "GNU-DEFAULT": {
        "url": "http://ftp.gnu.org/gnu/{name}/"
    },
    "GNOME-DEFAULT": {
        "url": "http://download.gnome.org/sources/{name}/*/",
    },
    "GOOGLE-DEFAULT": {
        "url": "http://code.google.com/p/{name}/downloads/list"
    },
    "HACKAGE-DEFAULT": {
        "prefix": "ghc-",
        "url": "http://hackage.haskell.org/package/{name}",
    },
    "LP-DEFAULT": {
        "url": "https://launchpad.net/{name}/+download"
    },
    "NPM-DEFAULT": {
        "prefix": "nodejs-",
        "regex": '"version":"([0-9.]*?)"',
        "url": "http://registry.npmjs.org/{name}",
    },
    "PEAR-DEFAULT": {
        "name_modifiers": [restore_underscore],
        "prefix": "php-pear-",
        "url": "http://pear.php.net/package/{name}/download/All",
    },
    "PECL-DEFAULT": {
        "name_modifiers": [restore_underscore],
        "prefix": "php-pecl-",
        "url": "http://pecl.php.net/package/{name}/download",
    },
    "PYPI-DEFAULT": {
        "url": "https://pypi.python.org/packages/source/{name[0]}/{name}/",
    },
    "RUBYGEMS-DEFAULT": {
        "prefix": "rubygem-",
        "regex":
        '"gem_uri":"http:\/\/rubygems.org\/gems\/{name}-([0-9.]*?)\.gem"',
        "url": "http://rubygems.org/api/v1/gems/{name}.json",
    },
    "SF-DEFAULT": {
        "url": "http://sourceforge.net/api/file/index/project-name/{name}/"
        "mtime/desc/limit/200/rss"
    },
}


def unalias(name, value, what):
    """ Unalias `value` for package `name`.
    :param what: "regex" or "url"
    :returns: Unaliased value
    """

    raw_name = name

    # allow name override with e.g. DEFAULT:othername
    if value and ":" in value:
        alias, name_override = value.split(":", 1)
        if alias in ALIASES.keys():
            value = alias
            name = name_override
    else:
        name_override = False

    # Use while loop to allow to fall back to DEFAULT value
    while value in ALIASES.keys():
        if not name_override:
            prefixes = ALIASES[value].get("prefix", [])
            if isinstance(prefixes, basestring):
                prefixes = [prefixes]
            for prefix in prefixes:
                if name.startswith(prefix):
                    name = name[len(prefix):]

            name_modifiers = ALIASES[value].get("name_modifiers", [])
            for modifier in name_modifiers:
                name = modifier(name)

        # Use DEFAULT regex if None is defined
        value = ALIASES[value].get(what, "DEFAULT")
        if what == "regex":
            format_values = {"name": re.escape(name),
                             "raw_name": re.escape(raw_name)}
        elif what == "url":
            format_values = {"name": urllib.quote(name, safe=""),
                             "raw_name": urllib.quote(raw_name, safe="")}
        else:
            raise NotImplementedError("what needs ot be 'regex' or 'url'")

        value = value.format(**format_values)
    return value
