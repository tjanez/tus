# A script for recovering URLs from Firefox's sessionstore files.

# Copyright 2017 Tadej Janež.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# NOTE: The Firefox sessionstore format is loosely documented at:
# https://wiki.mozilla.org/Firefox/session_restore#The_structure_of_sessionstore.js

import json

import click


INDENT = "    "


def _print_entry(entry, indents):
    print(INDENT * indents + entry.get('title', "(no title)"))
    if 'url' not in entry:
        raise ValueError("Every Tab entry in a Session store file must have "
                         "an 'url' entry.")
    else:
        print(INDENT * (indents + 1) + entry['url'])


def _print_tab(tab, indents, text="Tab:"):
    print(INDENT * indents + text)
    entries = tab['entries']
    if not entries:
        raise ValueError("Every Tab in a Session store file must contain at "
                         "least one entry.")
    _print_entry(entries[0], indents + 1)
    if len(entries) > 1:
        print(INDENT * (indents + 1) + "History:")
        for entry in entries[1:]:
            _print_entry(entry, indents + 2)

@click.command()
@click.argument('session-file', type=click.Path(exists=True))
def main(session_file):
    """Print URLs contained in the given Firefox sessionstore file."""
    with open(session_file) as sf:
        try:
            session = json.load(sf)
        except JSONDecodeError as json_decode_error:
            raise ValueError("The provided Firefox Sessionstore file is not a "
                             "valid JSON file") from json_decode_error
    for i, window in enumerate(session['windows']):
        print("Window {}:".format(i + 1))
        if len(window['tabs']) > 0:
            for j, tab in enumerate(window['tabs']):
                _print_tab(tab, 1, text="Tab {}:".format(j + 1))
            # TODO: Do we want to provide the ability to print URLs of closed
            # tabs as an option?
            # for j, tab in enumerate(window['closedTabs']):
            #     _print_tab(tab, 1, text="Closed tab {}:".format(j + 1))
