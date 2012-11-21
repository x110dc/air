#!/usr/bin/env python

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

# read config file:
config = ConfigObj(expanduser('~/.dev.cfg'))
jira_cfg = config['jira']
svn_cfg = config['svn']
aliases = config['aliases']

# open Jira connection:
options = {'server': jira_cfg['server']}
jira = JIRA(options,
        basic_auth=(jira_cfg['username'], jira_cfg['password']))


def refresh(branch):

    src = '{}/{}'.format(svn_cfg['branch_url'], branch)
    try:
        working_dir = tempfile.mkdtemp()
        print 'Checking out {}'.format(src)
        co = svn.co(src, working_dir)
        if co.exit_code:
            raise Exception("unable to check out branch")
        print 'Merging trunk into {}'.format(branch)
        merge = svn.merge(svn_cfg['trunk_url'], _cwd=working_dir,
                accept='postpone')
        print merge
        if 'conflicts' in merge:
            raise Exception(
                    'unable to merge due to conflicts; merge manually')
        print 'Committing...'
        commit = svn.commit(m='refreshed from trunk', _cwd=working_dir)
        print commit
    finally:
        print 'Cleaning up.'
        shutil.rmtree(working_dir)


def get_unique_branch(branches, search_string):

    strippers = ''.join(['/', string.whitespace])
    branch = [x.rstrip(strippers) for x in branches if search_string in x]
    if len(branch) > 1:
        raise Exception('more than one branch matches "{}"')

    return branch[0]


def get_branches():

    cmd = svn.ls(svn_cfg['branch_url'])
    return [x for x in cmd]


def make_branch(issue):

    summary = issue.fields.summary.replace(' ', '_')
    message = 'creating branch for {}'.format(issue.key)
    src = svn_cfg['trunk_url']
    dest = '{}{}_{}'.format(svn_cfg['branch_url'], issue.key, summary)

    process = svn.copy(src, dest, m=message)

    if process.exit_code:
        print process.stderr

    print process.stdout


def create_ticket(summary):

    new_issue = jira.create_issue(
                project={'key': jira_cfg['project']},
                summary=summary,
                description=summary,
                components=[{'id': '10301', 'name': 'Server Engineering'}],
                assignee={'name': jira_cfg['username']},
                issuetype={'name': 'Bug'})
    return new_issue.key


def list_tickets():
    tickets = jira.search_issues('assignee=currentUser() \
            AND status != Closed AND status != Resolved \
            AND fixVersion != "Post-GA Release"')
    for key, summary in [(x.key, x.fields.summary) for x in tickets]:
        print '{}:\t{}'.format(key, summary)


def get_ticket(ticket):
    return jira.issue('{}-{}'.format(jira_cfg['project'], ticket))


def main():
    # get the names of the functions in the Commands class to use as names for
    # subcommands for the parser:
    methods = [x for x in inspect.getmembers(commands) if
            inspect.ismethod(x[1])]

    # shamelessly stolen from:
    # http://stackoverflow.com/questions/362426/implementing-a-command-action-parameter-style-command-line-interfaces
    arger = argparse.ArgumentParser()

    arger.add_argument('-v', '--verbose', action='count', default=0)

    subparsers = arger.add_subparsers(dest='command')

    mkticket_parser = subparsers.add_parser('mkticket')
    mkticket_parser.add_argument('text')
    # add subcommands to the argument parser:
    for name, _ in methods:
        subparsers.add_parser(name)

    mkbranch_parser = subparsers.add_parser('mkbranch')
    mkbranch_parser.add_argument('ticket')
    # add any aliases defined in the config file as allowed subcommand names:
    for x in aliases:
        subparsers.add_parser(x)

    refresh_parser = subparsers.add_parser('refresh')
    refresh_parser.add_argument('ticket', nargs='?')
    opts = arger.parse_known_args()
    subcommand = opts[0].command

    # substitute the real command:
    if subcommand in aliases:
        subcommand = aliases[subcommand]

    # call the subcommand, pass the argument parser object
    if hasattr(commands, subcommand):
        output = getattr(commands, subcommand)(arger)
        [print(x) for x in output]
    else:
        print ('Unrecognized command: {}'.format(subcommand))


if __name__ == '__main__':
    main()
