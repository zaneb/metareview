#!/usr/bin/env python3

#    Copyright 2014 Zane Bitter <zbitter@redhat.com>
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""
A tool for reviewing reviewers.

Prints all of the comments left by a given Gerrit reviewer.

By Zane Bitter <zbitter@redhat.com>
"""

import datetime
import json
import sys


class GerritClient(object):
    """
    An ssh client for interacting with Gerrit.

    GerritClient objects can be used as a context manager that returns a
    connected Paramiko SSHClient. e.g.

    >>> import sys
    >>> with GerritClient('gerrit.example.com') as client:
    ...     stdin, stdout, stderr = client.exec_command('gerrit --help')
    ...     sys.stdout.write(stderr.read())
    """

    def __init__(self, ssh_server, ssh_user=None, ssh_port=29418):
        """
        Initialise with a Gerrit server to connect to.

        The username used to connect can also be overridden (otherwise the
        default ssh settings are used), as can the port to connect to. The
        default port for Gerrit is 29418.
        """
        import paramiko

        self.client = paramiko.SSHClient()
        self.client.load_system_host_keys()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        self.ssh_server = ssh_server
        self.ssh_user = ssh_user
        self.ssh_port = ssh_port

    def comments_query(self, **query):
        """
        Return an iterator over patchset data for a Gerrit comments query.

        The query parameters can be specified as keyword arguments.
        """
        q_str = ' '.join(':'.join(param) for param in query.items())

        with self as ssh_client:
            count = 0
            while True:
                query_cmd = ' '.join(['gerrit query',
                                      '"%s"' % q_str,
                                      '--comments',
                                      '--format=JSON',
                                      '--start=%d' % count])

                stdin, stdout, stderr = ssh_client.exec_command(query_cmd)

                prior_count = count
                for record in map(load_patchset, stdout):
                    if 'type' in record and record['type'] == 'stats':
                        if not record.get('moreChanges', False):
                            return
                        count += record['rowCount']
                    else:
                        yield record
                if count == prior_count:
                    break

    def __enter__(self):
        """
        Open an ssh connection on entering the context manager.

        Returns a paramiko.SSHCLient object to interact with the server.
        """
        self.client.connect(self.ssh_server, port=self.ssh_port,
                            username=self.ssh_user)
        return self.client

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Close the connection on exit from the context manager.
        """
        self.client.close()


class GerritAsyncClient(object):
    """
    An ssh client for interacting with Gerrit.

    GerritClient objects can be used as a context manager that returns a
    connected asyncssh SSHClientConnection. e.g.

    >>> import sys
    >>> async with GerritAsyncClient('gerrit.example.com') as client:
    ...     output = await client.run('gerrit --help')
    ...     sys.stdout.write(output.stderr.read())
    """

    def __init__(self, ssh_server, ssh_user=None, ssh_port=29418):
        """
        Initialise with a Gerrit server to connect to.

        The username used to connect can also be overridden (otherwise the
        default ssh settings are used), as can the port to connect to. The
        default port for Gerrit is 29418.
        """
        self.ssh_server = ssh_server
        self.ssh_user = ssh_user
        self.ssh_port = ssh_port

    async def _run_query(self, ssh_client, query_cmd):
        stdin, stdout, stderr = await ssh_client.run(query_cmd)

    async def comments_query(self, **query):
        """
        Return an iterator over patchset data for a Gerrit comments query.

        The query parameters can be specified as keyword arguments.
        """
        q_str = ' '.join(':'.join(param) for param in query.items())

        async with self as ssh_client:
            count = 0
            while True:
                query_cmd = ' '.join(['gerrit query',
                                      '"%s"' % q_str,
                                      '--comments',
                                      '--format=JSON',
                                      '--start=%d' % count])

                async with ssh_client.create_process(query_cmd) as output:
                    prior_count = count
                    async for line in output.stdout:
                        record = load_patchset(line)
                        if 'type' in record and record['type'] == 'stats':
                            if not record.get('moreChanges', False):
                                return
                            count += record['rowCount']
                        else:
                            yield record
                    if count == prior_count:
                        break

    async def __aenter__(self):
        """
        Open an ssh connection on entering the context manager.

        Returns an asyncssh connection object to interact with the server.
        """
        import asyncssh

        self.client = await asyncssh.connect(self.ssh_server,
                                             port=self.ssh_port,
                                             username=self.ssh_user)
        return self.client

    async def __aexit__(self, *exc_info):
        self.client.close()
        await self.client.wait_closed()


def load_patchset(patchset_json):
    """Load a patchset from a JSON record returned from Gerrit."""
    return json.loads(patchset_json)


def file_data(filename):
    """Return an iterator over patchset data from a local file."""
    with file(filename) as reviewfile:
        for line in reviewfile:
            yield load_patchset(line)


def user_match(user, username):
    """
    Return True if this is the user we are looking for.

    Compares a user structure from a Gerrit record to a username (or email
    address). All users match if the username is None.
    """
    if username is None:
        return True

    def field_match(field):
        if field not in user:
            return False
        return user[field] == username

    return field_match('email' if '@' in username else 'username')


def extract_comments(patchset, author=None):
    """
    Extract all interesting comments from a given patchset.

    Interesting comments are ones added by the author in question, on patchsets
    that are not their own.
    """

    if 'comments' not in patchset:
        return

    if author is not None and user_match(patchset['owner'], author):
        return

    for comment in patchset['comments']:
        if user_match(comment['reviewer'], author):
            if 'Gerrit trivial rebase' in comment['message']:
                continue

            yield comment


def format_comment(patchset, comment, color=False):
    """Format a comment on a given patchset for output."""
    header = '%s %s' % (patchset['url'],
                        datetime.datetime.fromtimestamp(comment['timestamp']))
    if color:
        header = f'\033[96m{header}\033[39m'

    return '%s\n%s\n\n' % (header, comment['message'])


async def write_all_comments(stream, patchset_source,
                             username=None, color=False):
    """
    Write all of the comments from the patchset source to a stream.
    """
    async for patchset in patchset_source:
        for comment in extract_comments(patchset, username):
            stream.write(format_comment(patchset, comment, color))


async def metareview(options, username, stream, color=False):
    """Run a metareview with the given options and output stream."""
    gerrit_client = GerritAsyncClient(options.ssh_server, options.ssh_user)
    await write_all_comments(stream,
                             gerrit_client.comments_query(reviewer=username,
                                                          project=options.project),
                             username,
                             color)


def main():
    """Run the metareview command-line interface."""

    import autopage
    import asyncio
    import argparse
    import pydoc

    docstring = pydoc.getdoc(sys.modules[__name__])

    parser = argparse.ArgumentParser(description=docstring)
    parser.add_argument('-p', '--project', default='openstack/heat',
                        help='The project to look in. '
                             'Defaults to "%(default)s".')
    parser.add_argument('-u', '--ssh-user', default=None,
                        help='The Gerrit username to connect with.')
    parser.add_argument('-s', '--ssh-server', default='review.opendev.org',
                        help='The Gerrit server to connect to. '
                             'Defaults to "%(default)s".')
    parser.add_argument('reviewer', metavar='REVIEWER', nargs=1,
                        help="Reviewer whose comments to fetch.")

    options = parser.parse_args()

    pager = autopage.AutoPager(line_buffering=False, reset_on_exit=True)
    try:
        with pager as out_stream:
            asyncio.run(metareview(options,
                                   options.reviewer[0],
                                   out_stream,
                                   pager.to_terminal()))
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        sys.stderr.write(str(exc) + '\n')
    return pager.exit_code()


if __name__ == '__main__':
    sys.exit(main())
