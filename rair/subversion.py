#!/usr/bin/env python

from __future__ import print_function

# stdlib
import string
import tempfile

# installed:
from sh import svn
from sh import CommandNotFound


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
            raise MultipleMatchException('more than one branch matches "{0}"')

        return branch[0]

    def diff(self, branch):
        """
        Given a branch name, a diff against trunk is produced and returned.
        """
        trunk = self.config['trunk_url']
        branch = '/'.join([self.config['branch_url'], branch])
        # if filterdiff exists, pipe diff through it to clean up parts that
        # Crucible doesn't like
        try:
            from sh import filterdiff
            proc = filterdiff(svn.diff(trunk, branch,
                                       diff_cmd='diff', x='-U 300 -a'),
                              clean=True)

        # if there's no filterdiff then hope for the best:
        except (CommandNotFound, ImportError):
            proc = svn.diff(trunk, branch, diff_cmd='diff', x='-U 300 -a')
        return proc.stdout

    def reintegrate(self, branch):
        """
        Reintegration a branch into trunk.
        """
        #TODO: pass commit message as param

        trunk_url = self.config['trunk_url']
        branch_url = '/'.join([self.config['branch_url'], branch])
        # checkout trunk
        working_dir = tempfile.mkdtemp()
        co = svn.co(trunk_url, working_dir)
        print(co.ran)
        print(co.stdout)
        # merge
        merge = svn.merge(branch_url, working_dir, reintegrate=True)
        print(merge.ran)
        print(merge.stdout)
        # commit
        commit = svn.commit(m='reintegrating into trunk', _cwd=working_dir)
        print(commit.ran)
        print(commit.stdout)
        #shutil.rmtree(working_dir)

    def make_branch(self, name, commit_msg):
        """
        Create a branch.
        """

        src = self.config['trunk_url']
        dest = '{0}/{1}'.format(self.config['branch_url'], name)

        process = svn.copy(src, dest, m=commit_msg)
        print(process.ran)
        print(process.stdout)
        return process
