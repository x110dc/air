#!/usr/bin/env python

from __future__ import print_function

# stdlib
import argparse
from os.path import expanduser
import tempfile
import shutil
import inspect
import sys

# installed:
from configobj import ConfigObj
from sh import svn

#
from subversion import Subversion
from atlassian_jira import Jira


class MergeException(Exception):
    pass


class Commands(object):
    '''
    This class encapsulates all the of the subcommands available for this
    program.  Each function is a subcommand and must have the following
    signature:

    my_awesome_function(self, arger, out=sys.stdout)

    The 'arger' is an instance of ArgumentParse class and will be passed to
    every function as the first (non-self) argument.  The ArgumentParse class
    will have been parsed up to the point of determining the subcommand but
    further processing of command line arguments is left to this function.

    The method should send it's output to the buffer passed in as the 'out'
    parameter.  If no parameter is passed output should be sent to sys.stdout.
    '''

    def __init__(self, config):
        self.config = config
        self.jira = Jira(config['jira'])
        self.svn = Subversion(config['svn'])

    def start_work(self, arger, out=sys.stdout):

        self.make_branch(arger)
        opts = arger.parse_args()
        issue = self.jira.get_issue(opts.ticket)
        self.jira.transition_issue(opts.ticket, status='Start Progress')
        branch = self.svn.get_unique_branch(opts.ticket)
        comment = 'SVN URL: ' + self.config['svn']['branch_url'] + '/' + branch
        self.jira.add_comment(issue.key, comment)
        out.write('Branch created and issue marked as "In Progress"')

    def refresh(self, arger, out=sys.stdout):
        '''
        Given a Jira ticket, refresh the associated branch from trunk.  If
        conflicts are found during the merge process an exception is raised
        and the merge process will need to be completed manually.
        '''

        #arger.add_argument('ticket', nargs='?')
        arger.add_argument('ticket')
        opts = arger.parse_args()

        branch = self.svn.get_unique_branch(opts.ticket)

        src = '{}/{}'.format(self.config['svn']['branch_url'], branch)
        try:
            working_dir = tempfile.mkdtemp()
            svn.co(src, working_dir)
            merge = svn.merge(self.config['svn']['trunk_url'],
                    _cwd=working_dir, accept='postpone')
            out.write(merge.stdout)
            if 'conflicts' in merge:
                raise MergeException(
                        'unable to merge due to conflicts; merge manually')
            commit = svn.commit(m='refreshed from trunk', _cwd=working_dir)
            out.write(commit.stdout)
        finally:
            shutil.rmtree(working_dir)

    def make_branch(self, arger, out=sys.stdout):
        '''
        Given a Jira ticket number an Svn branch is created for it.
        '''

        arger.add_argument('ticket')
        opts = arger.parse_args()
        issue = self.jira.get_issue(opts.ticket)

        summary = issue.fields.summary.replace(' ', '_')
        message = 'creating branch for {}'.format(issue.key)
        src = self.config['svn']['trunk_url']
        dest = '{}/{}_{}'.format(self.config['svn']['branch_url'], issue.key,
                summary)

        process = svn.copy(src, dest, m=message)

        out.write(process.stdout)

    def create_bug(self, arger, out=sys.stdout):
        '''
        Given a brief description a Jira bug will be created. This uses options
        specified in the config file to screate the ticket.
        '''

        arger.add_argument('text')
        summary = arger.parse_args().text

        bug = self.jira.create_issue(summary, summary)

        out.write('ticket created: {}\n'.format(bug))

    def list_tickets(self, arger, out=sys.stdout):
        '''
        Lists all Jira tickets assigned to me.
        '''

        tickets = self.jira.query('assignee=currentUser() \
                AND status != Closed AND status != Resolved \
                AND fixVersion != "Post-GA Release"')
        for key, summary in [(x.key, x.fields.summary) for x in tickets]:
            out.write('{}:\t{}\n'.format(key, summary))


def get_parser(names):

    arger = argparse.ArgumentParser()
    arger.add_argument('-v', '--verbose', action='count', default=0)
    subparsers = arger.add_subparsers(dest='command')

    [subparsers.add_parser(x) for x in names]

    return arger


class Dispatcher(object):

    def __init__(self, config):
        self.config = config
        self.commands = Commands(config)
        self.aliases = config['aliases']

    def go(self, out=sys.stdout):
        # get the names of the functions in the Commands class to use
        # as names for  subcommands for the parser:
        # TODO: use filter() here?
        methods = [x for x in inspect.getmembers(self.commands) if
                inspect.ismethod(x[1])]

        names = [x[0] for x in methods] + self.aliases.keys()
        names.remove('__init__')
        arger = get_parser(names)

        opts = arger.parse_known_args()
        subcommand = opts[0].command

        # substitute the real command:
        if subcommand in self.aliases:
            subcommand = self.aliases[subcommand]

        # call the subcommand, pass the argument parser object
        if hasattr(self.commands, subcommand):
            getattr(self.commands, subcommand)(arger, out=out)

        return 0


def main():

    config = ConfigObj(expanduser('~/.dev.cfg'))
    Dispatcher(config).go()
    return 0

if __name__ == '__main__':
    main()
