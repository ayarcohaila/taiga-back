# Copyright (C) 2014 Andrey Antukh <niwi@niwi.be>
# Copyright (C) 2014 Jesús Espino <jespinog@gmail.com>
# Copyright (C) 2014 David Barragán <bameda@dbarragan.com>
# Copyright (C) 2014 Anler Hernández <hello@anler.me>
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import absolute_import
from __future__ import unicode_literals
from markdown import Extension
from markdown.inlinepatterns import Pattern
from markdown.util import etree
import re


def build_url(label, base, end):
    """ Build a url from the label, a base, and an end. """
    clean_label = re.sub(r'([ ]+_)|(_[ ]+)|([ ]+)', '_', label)
    return '%s%s%s' % (base, clean_label, end)


class WikiLinkExtension(Extension):
    def __init__(self, configs):
        # set extension defaults
        self.config = {
            'base_url': ['/', 'String to append to beginning or URL.'],
            'end_url': ['/', 'String to append to end of URL.'],
            'html_class': ['wikilink', 'CSS hook. Leave blank for none.'],
            'build_url': [build_url, 'Callable formats URL from label.'],
        }
        configs = dict(configs) or {}
        # Override defaults with user settings
        for key, value in configs.items():
            self.setConfig(key, value)

    def extendMarkdown(self, md, md_globals):
        self.md = md

        # append to end of inline patterns
        WIKILINK_RE = r'\[\[([\w0-9_ -]+)(\|[\w0-9_ -]+)?\]\]'
        wikilinkPattern = WikiLinks(WIKILINK_RE, self.getConfigs())
        wikilinkPattern.md = md
        md.inlinePatterns.add('wikilink', wikilinkPattern, "<not_strong")


class WikiLinks(Pattern):
    def __init__(self, pattern, config):
        super(WikiLinks, self).__init__(pattern)
        self.config = config

    def handleMatch(self, m):
        base_url, end_url, html_class = self._getMeta()
        label = m.group(2).strip()
        url = self.config['build_url'](label, base_url, end_url)

        if m.group(3):
            title = m.group(3).strip()[1:]
        else:
            title = label

        a = etree.Element('a')
        a.text = title
        a.set('href', url)
        if html_class:
            a.set('class', html_class)
        return a

    def _getMeta(self):
        """ Return meta data or config data. """
        base_url = self.config['base_url']
        end_url = self.config['end_url']
        html_class = self.config['html_class']
        return base_url, end_url, html_class
