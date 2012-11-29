#!/usr/bin/env python

from __future__ import print_function

# stdlib
import argparse
import string
from os.path import expanduser
import tempfile
import shutil
import inspect

# installed:
from configobj import ConfigObj
from jira.client import JIRA
from sh import svn


class MultipleMatchException(Exception):
    pass


class MergeException(Exception):
    pass


class Subversion(object):
    '''
    This class encapsulates interaction with Subversion
    '''

    def __init__(self, config):
        self.config = config
        self.strippers = ''.join(['/', string.whitespace])

    def get_branches(self):
        '''
        Returns a list of branches in the SVN repo based on the 'branch_url'
        given in the configuration file.
        '''

        cmd = svn.ls(self.config['branch_url'])
        return [x.rstrip(self.strippers) for x in cmd]

    def get_unique_branch(self, search_string):
        '''
        Given a search string attempts to find one branch that contains the
        string in it's name. If more than one branch matches then an exception
        is raised.
        '''

        branches = self.get_branches()
        branch = [x.rstrip(self.strippers)
                for x in branches if search_string in x]
        if len(branch) > 1:
            raise MultipleMatchException('more than one branch matches "{}"')

        return branch[0]


class Jira(object):
    '''
    Encapsulates interaction with Jira server.
    '''

    def __init__(self, config):
        self.config = config
        self.options = {'server': config['server']}
        self.server = JIRA(self.options,
                basic_auth=(config['username'], config['password']))

    def query(self, jql_query):
        '''
        Run a JQL query.
        '''
        return self.server.search_issues(jql_query)

    def create_issue(self, summary, description, kind='Bug'):
        '''
        Create a Jira issue -- defaults to a bug.
        '''

        new_issue = self.server.create_issue(
            project={'key': self.config['project']},
            summary=summary,
            description=summary,
#       components=[{'id': '10301', 'name': 'Server Engineering'}],
            assignee={'name': self.config['username']},
            issuetype={'name': kind})

        return new_issue.key

    def transition_issue(self, ticket, status='Closed'):
        # find ID for status:
        issue = self.get_issue(ticket)
        transitions = self.server.transitions(issue)
        # TODO: what if status isn't in list of transitions?
        _id = [x['id'] for x in transitions if x['name'] == status][0]
        # close it:
        self.server.transition_issue(issue, _id)
        return self.get_issue(ticket)

    def add_comment(self, ticket, comment):

        issue = self.get_issue(ticket)
        self.server.add_comment(issue, comment)
        return issue

    def get_issue(self, ticket):
        '''
        Given an issue name, returns a Jira instance of that issue.
        '''
        return self.server.issue('{}'.format(ticket))


class Commands(object):
    '''
    This class encapsulates all the of the subcommands available for this
    program.  Each function is a subcommand and must have the following
    signature:

    my_awesome_function(self, arger)

    The 'arger' is an instance of ArgumentParse class and will be passed to
    every function as the first (non-self) argument.  The ArgumentParse class
    will have been parsed up to the point of determining the subcommand but
    further processing of command line arguments is left to this function.
    '''

    def __init__(self, config):
        self.config = config
        self.jira = Jira(config['jira'])
        self.svn = Subversion(config['svn'])

    def start_work(self, arger):

        self.make_branch(arger)
        opts = arger.parse_args()
        issue = self.jira.get_issue(opts.ticket)
        self.jira.transition_issue(opts.ticket, status='In Progress')
        branch = self.svn.get_unique_branch(opts.ticket)
        comment = 'SVN URL: ' + self.config['svn']['branch_url'] + '/' + branch
        self.jira.add_comment(issue.key, comment)
        return 'Branch created and issue marked as "In Progress"'

    def refresh(self, arger):
        '''
        Given a Jira ticket, refresh the associated branch from trunk.  If
        conflicts are found during the merge process an exception is raised
        and the merge process will need to be completed manually.
        '''
        output = list()

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
            output.append(merge)
            if 'conflicts' in merge:
                raise MergeException(
                        'unable to merge due to conflicts; merge manually')
            commit = svn.commit(m='refreshed from trunk', _cwd=working_dir)
            output.append(commit)
        finally:
            shutil.rmtree(working_dir)
        return output

    def make_branch(self, arger):
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

        return process.stdout

    def create_bug(self, arger):
        '''
        Given a brief description a Jira bug will be created. This uses options
        specified in the config file to screate the ticket.
        '''

        arger.add_argument('text')
        summary = arger.parse_args().text

        bug = self.jira.create_issue(summary, summary)

        return ['ticket created: {}'.format(bug)]

    def list_tickets(self, arger):
        '''
        Lists all Jira tickets assigned to me.
        '''
        output = list()

        tickets = self.jira.query('assignee=currentUser() \
                AND status != Closed AND status != Resolved \
                AND fixVersion != "Post-GA Release"')
        for key, summary in [(x.key, x.fields.summary) for x in tickets]:
            output.append('{}:\t{}'.format(key, summary))
        return output


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

    def go(self):
        # get the names of the functions in the Commands class to use
        # as names for  subcommands for the parser:
        # TODO: use filter() here?
        methods = [x for x in inspect.getmembers(self.commands) if
                inspect.ismethod(x[1])]

        names = [x[0] for x in methods] + self.aliases.keys()
        arger = get_parser(names)

        opts = arger.parse_known_args()
        subcommand = opts[0].command

        # substitute the real command:
        if subcommand in self.aliases:
            subcommand = self.aliases[subcommand]

        # call the subcommand, pass the argument parser object
        if hasattr(self.commands, subcommand):
            output = getattr(self.commands, subcommand)(arger)
            return output


def main():

    config = ConfigObj(expanduser('~/.dev.cfg'))
    dispatcher = Dispatcher(config)
    out = dispatcher.go()
    [print(x) for x in out]
    return 0

if __name__ == '__main__':
    main()
