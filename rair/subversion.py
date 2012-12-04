#!/usr/bin/env python

from __future__ import print_function

# stdlib
import string

# installed:
from sh import svn


class MultipleMatchException(Exception):
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
