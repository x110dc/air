#!/usr/bin/env python3

# the program we're testing:
import air

# stdlib
import sys
import unittest
import tempfile
import argparse
import inspect
from os.path import basename

# installed libraries:
from sh import svnadmin
from sh import svn
from configobj import ConfigObj


def overwrite(file_object, text):
        if file_object.closed:
            file_object = open(file_object.name, 'w')
        file_object.write(text)
        file_object.close()


def create_svn_repo():

    repo_dir = tempfile.mkdtemp()

    # create repo, with trunk and branches directories
    svnadmin.create(repo_dir)
    repo_url = '{}{}'.format('file://', repo_dir)
    trunk_url = '{}/trunk'.format(repo_url)
    branch_url = '{}/branches'.format(repo_url)
    svn.mkdir(trunk_url, m='trunk dir')
    svn.mkdir(branch_url, m='branches dir')

    return repo_url


def setup_svn():

    # create repo
    repo_url = create_svn_repo()
    trunk_url = '{}/trunk'.format(repo_url)
    branch_url = '{}/branches'.format(repo_url)

    # checkout trunk
    working_dir = tempfile.mkdtemp()
    svn.co(trunk_url, working_dir)

    # create a file
    repo_file = tempfile.NamedTemporaryFile(dir=working_dir, delete=False)
    overwrite(repo_file, '123\n')
    # commit it
    svn.add(repo_file.name, _cwd=working_dir)
    svn.commit(m='message', _cwd=working_dir)

    # create a branch
    new_branch_url = '{}/new-branch'.format(branch_url)
    svn.cp(trunk_url, new_branch_url, m='creating new branch')
    svn.switch(new_branch_url, _cwd=working_dir)
    # change the file and commit
    overwrite(repo_file, '456\n')
    svn.commit(m='message', _cwd=working_dir)

    # create another branch
    new_branch_url = '{}/foo-branch'.format(branch_url)
    svn.cp(trunk_url, new_branch_url, m='creating another new branch')

    return [repo_url, repo_file]


def create_conflict(repo_url, repo_file):

    trunk_url = '{}/trunk'.format(repo_url)

    # checkout trunk
    working_dir = tempfile.mkdtemp()
    svn.co(trunk_url, working_dir)

    # change the same file on trunk
    svn.co(trunk_url, working_dir)
    repo_file = working_dir + '/' + basename(repo_file.name)
    repo_file = open(repo_file, 'w')
    overwrite(repo_file, '789\n')
    svn.commit(m='creating conflict', _cwd=working_dir)

#    svn.up(_cwd=working_dir)
#    svn.merge(new_branch_url, _cwd=working_dir, accept='postpone')


def get_jira_pass():

    with open('./.pass', 'r') as pfile:
        return pfile.readline().rstrip()


class TestMakeBranch(unittest.TestCase):

    def setUp(self):
        # mock the configuration file:
        self.config = ConfigObj('./tests/config')
        self.config['jira']['password'] = get_jira_pass()

        self.summary = "test bug"
        self.jira = air.Jira(self.config['jira'])
        self.bug = self.jira.create_issue(self.summary, self.summary)
        self.cmd = air.Commands(self.config)

        self.repo_url, self.repo_file = setup_svn()
        self.config['svn']['root_url'] = self.repo_url
        self.config['svn']['branch_url'] = self.repo_url + '/branches'
        self.config['svn']['trunk_url'] = self.repo_url + '/trunk'

    def test_make_branch(self):
        sys.argv = ['bogus', 'make_branch', self.bug]
        arger = air.get_parser(['make_branch'])
        branch_name = '{}_{}'.format(self.bug, self.summary.replace(' ', '_'))
        self.cmd.make_branch(arger)
        self.assertIn(branch_name, self.cmd.svn.get_branches())

    def tearDown(self):
        self.jira.transition_issue(self.bug, status='Closed')


class TestSvn(unittest.TestCase):

    def setUp(self):
        self.config = ConfigObj('./tests/config')
        self.config['jira']['password'] = get_jira_pass()
        self.repo_url, self.repo_file = setup_svn()
        self.arger = air.get_parser(['refresh'])
        self.cmd = air.Commands(self.config)

        # use new values for SVN url:
        self.config['svn']['root_url'] = self.repo_url
        self.config['svn']['branch_url'] = self.repo_url + '/branches'
        self.config['svn']['trunk_url'] = self.repo_url + '/trunk'

    def test_get_unique_branch(self):
        expected = 'foo-branch'
        actual = self.cmd.svn.get_unique_branch('foo')
        self.assertEqual(expected, actual)

        with self.assertRaises(air.MultipleMatchException):
            actual = self.cmd.svn.get_unique_branch('branch')

    def test_get_branches(self):
        expected = [u'foo-branch', u'new-branch']
        actual = self.cmd.svn.get_branches()
        self.assertEqual(expected, actual)

    def test_refresh(self):
        sys.argv = ['bogus', 'refresh', 'new-branch']
        output = self.cmd.refresh(self.arger)
        self.assertRegexpMatches(str(output[-1]), 'Committed revision 7')

    def test_refresh_exception(self):
        sys.argv = ['bogus', 'refresh', 'new-branch']
        create_conflict(self.repo_url, self.repo_file)
        with self.assertRaises(air.MergeException):
            self.cmd.refresh(self.arger)


class TestJira(unittest.TestCase):

    def setUp(self):
        # mock the configuration file:
        self.config = ConfigObj('./tests/config')
        self.config['jira']['password'] = get_jira_pass()

        self.arger = argparse.ArgumentParser()
        subparsers = self.arger.add_subparsers(dest='command')

        self.cmd = air.Commands(self.config)

        methods = [x for x in inspect.getmembers(self.cmd) if
            inspect.ismethod(x[1])]

        # add subcommands to the argument parser:
        for name, _ in methods:
            subparsers.add_parser(name)

    def test_create_bug(self):
        sys.argv = ['bogus', 'create_bug', 'this is a test bug']
        actual = self.cmd.create_bug(self.arger)[0]
#TODO: close this bug via tearDown()
        self.assertRegexpMatches(actual, 'ticket created: MMSANDBOX-\d*')

class TestCloseJiraIssue(unittest.TestCase):

    def setUp(self):
        self.config = ConfigObj('./tests/config')
        self.config['jira']['password'] = get_jira_pass()
        self.summary = "test bug"
        self.jira = air.Jira(self.config['jira'])
        self.bug = self.jira.create_issue(self.summary, self.summary)

    def test_transition_issue(self):
        issue = self.jira.transition_issue(self.bug, status='Closed')
        expected = 'Closed'
        self.assertEqual(expected, issue.fields.status.name)


class TestMain(unittest.TestCase):

    def setUp(self):
        # mock the configuration file:
        self.config = ConfigObj('./tests/config')
        self.config['jira']['password'] = get_jira_pass()

    def test_aliases(self):
        '''
        Testing that aliases specified in the the config file work.
        '''
        sys.argv = ['bogus', 'jirals']
        d = air.Dispatcher(self.config)
        self.assertIsInstance(d.go(), list)

    def test_main(self):
        '''
        This is kinda lame and doesn't test much, but it makes sure there's
        test coverage for main().
        '''
        sys.argv = ['bogus', 'list_tickets']
        actual = air.main()
        expected = 0
        self.assertEqual(expected, actual)
