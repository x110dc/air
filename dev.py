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

# read config file:
config = ConfigObj(expanduser('~/.dev.cfg'))
jira_cfg = config['jira']
svn_cfg = config['svn']
aliases = config['aliases']

# open Jira connection:
options = {'server': jira_cfg['server']}
jira = JIRA(options,
        basic_auth=(jira_cfg['username'], jira_cfg['password']))


class MultipleMatchException(Exception):
    pass


class MergeException(Exception):
    pass

# helper functions:


def get_branches():
    '''
    Returns a list of branches in the SVN repo based on the 'branch_url' given
    in the configuration file.
    '''

    cmd = svn.ls(svn_cfg['branch_url'])
    return [x for x in cmd]


def get_unique_branch(search_string):
    '''
    Given a search string attempts to find one branch that contains the string
    in it's name. If more than one branch matches then an exception is raised.
    '''











    # get the names of the functions in the Commands class to use as names for
    # subcommands for the parser:
    methods = [x for x in inspect.getmembers(commands) if
            inspect.ismethod(x[1])]

    arger = argparse.ArgumentParser()
    arger.add_argument('-v', '--verbose', action='count', default=0)
    subparsers = arger.add_subparsers(dest='command')

    # add subcommands to the argument parser:
    for name, _ in methods:
        subparsers.add_parser(name)

    # add any aliases defined in the config file as allowed subcommand names:
    for x in aliases:
        subparsers.add_parser(x)

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
