
# the program we're testing:
from rair import air

# stdlib
import sys
import unittest
import tempfile
import argparse
from os.path import basename
from StringIO import StringIO
import contextlib
import re

# installed libraries:
from sh import svnadmin
from sh import svn
from configobj import ConfigObj

#
from rair.subversion import MultipleMatchException
from rair.atlassian_jira import InvalidJiraStatusException


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


class TestCrucible(unittest.TestCase):

    def setUp(self):
        # mock the configuration file:
        self.config = ConfigObj('./tests/config')
        self.config['jira']['password'] = get_jira_pass()
        self.jira = air.Jira(self.config['jira'])
        self.summary = "test bug for Crucible"
        self.crucible = air.Crucible(self.config['jira'])
        self.diff = open('./tests/diff.txt').read()
        self.bug = self.jira.create_issue(self.summary, self.summary)

    def tearDown(self):
        self.bug.delete()
        if self.review:
            self.review.abandon()

    def test_create_review(self):
        self.review = self.crucible.create_review(['jon.oelfke'],
                jira_ticket=self.bug.key)
        self.assertTrue(self.review)
        response = self.review.add_patch(self.diff)
        self.assertTrue(response)


class TestCrucibleGet(unittest.TestCase):

    def setUp(self):
        # mock the configuration file:
        self.config = ConfigObj('./tests/config')
        self.config['jira']['password'] = get_jira_pass()
        self.crucible = air.Crucible(self.config['jira'])

    def tearDown(self):
        if self.review:
            self.review.abandon()

    def test_get_review(self):
        self.review = self.crucible.create_review(['jon.oelfke'])
        actual = self.review.get().data['state']
        expected = 'Draft'
        self.assertEqual(expected, actual)


class TestMakeBranch(unittest.TestCase):

    def setUp(self):
        # mock the configuration file:
        self.config = ConfigObj('./tests/config')
        self.config['jira']['password'] = get_jira_pass()

        self.summary = "test bug for making branch"
        self.jira = air.Jira(self.config['jira'])
        self.bug = self.jira.create_issue(self.summary, self.summary)
        self.cmd = air.Commands(self.config)

        self.repo_url, self.repo_file = setup_svn()
        self.config['svn']['root_url'] = self.repo_url
        self.config['svn']['branch_url'] = self.repo_url + '/branches'
        self.config['svn']['trunk_url'] = self.repo_url + '/trunk'

    def tearDown(self):
        self.bug.delete()

    def test_make_branch(self):
        sys.argv = ['bogus', 'make_branch', '-t', self.bug.key]
        d = air.Dispatcher(self.config)
        out = StringIO()
        d.go(out=out)
        # now that branch should exist in the list of branches:
        branch_name = '{}_{}'.format(self.bug.key, self.summary.replace(' ', '_'))
        self.assertIn(branch_name, self.cmd.svn.get_branches())


class TestSvn(unittest.TestCase):

    def setUp(self):
        self.config = ConfigObj('./tests/config')
        self.config['jira']['password'] = get_jira_pass()
        self.repo_url, self.repo_file = setup_svn()
        self.arger = argparse.ArgumentParser()
        self.cmd = air.Commands(self.config)

        # use new values for SVN url:
        self.config['svn']['root_url'] = self.repo_url
        self.config['svn']['branch_url'] = self.repo_url + '/branches'
        self.config['svn']['trunk_url'] = self.repo_url + '/trunk'

    def test_get_unique_branch(self):
        expected = 'foo-branch'
        actual = self.cmd.svn.get_unique_branch('foo')
        self.assertEqual(expected, actual)

        with self.assertRaises(MultipleMatchException):
            actual = self.cmd.svn.get_unique_branch('branch')

    def test_get_branches(self):
        expected = [u'foo-branch', u'new-branch']
        actual = self.cmd.svn.get_branches()
        self.assertEqual(expected, actual)

    def test_diff(self):
        diff = self.cmd.svn.diff('new-branch')
        self.assertRegexpMatches(diff, '-123')


class TestRefresh(unittest.TestCase):

    def setUp(self):
        self.config = ConfigObj('./tests/config')
        self.config['jira']['password'] = get_jira_pass()
        self.repo_url, self.repo_file = setup_svn()
        self.arger = argparse.ArgumentParser()
        self.cmd = air.Commands(self.config)

        # use new values for SVN url:
        self.config['svn']['root_url'] = self.repo_url
        self.config['svn']['branch_url'] = self.repo_url + '/branches'
        self.config['svn']['trunk_url'] = self.repo_url + '/trunk'

        self.summary = "test refresh"
        self.jira = air.Jira(self.config['jira'])
        self.svn = air.Subversion(self.config['svn'])
        self.bug = self.jira.create_issue(self.summary, self.summary)
        self.svn.make_branch(self.bug, "test commit message")

    def tearDown(self):
        self.jira.transition_issue(self.bug, status='Resolve Issue')

    def test_refresh(self):
        out = StringIO()
        self.cmd.refresh(self.arger, ['-t', self.bug], out=out)
        output = out.getvalue().strip()
        self.assertRegexpMatches(output, 'Committed revision 8')

    def test_refresh_exception(self):
        create_conflict(self.repo_url, self.repo_file)
        with self.assertRaises(air.MergeException):
            self.cmd.refresh(self.arger, ['-t', 'new-branch'])


class TestCloseBug(unittest.TestCase):

    def setUp(self):
        # mock the configuration file:
        self.config = ConfigObj('./tests/config')
        self.config['jira']['password'] = get_jira_pass()
        self.summary = "test bug to close"
        self.jira = air.Jira(self.config['jira'])
        self.bug = self.jira.create_issue(self.summary, self.summary)

    def test_close_bug(self):
        sys.argv = ['bogus', 'close_ticket', '-t', self.bug.key]
        d = air.Dispatcher(self.config)
        out = StringIO()
        d.go(out=out)
        actual = out.getvalue().strip()
        match = re.search('MMSANDBOX-\d*', actual)
        self.issue = match.group()
        self.assertRegexpMatches(actual, 'MMSANDBOX-\d* closed.')


class TestCloseTask(unittest.TestCase):

    def setUp(self):
        # mock the configuration file:
        self.config = ConfigObj('./tests/config')
        self.config['jira']['password'] = get_jira_pass()
        self.summary = "test issue to close"
        self.jira = air.Jira(self.config['jira'])
        self.issue = self.jira.create_issue(self.summary, self.summary,
                kind="Task")

    def test_close_task(self):
        sys.argv = ['bogus', 'close_ticket', '-t', self.issue.key]
        d = air.Dispatcher(self.config)
        out = StringIO()
        d.go(out=out)
        actual = out.getvalue().strip()
        match = re.search('MMSANDBOX-\d*', actual)
        self.issue = match.group()
        self.assertRegexpMatches(actual, 'MMSANDBOX-\d* closed.')


class TestJira(unittest.TestCase):

    def setUp(self):
        # mock the configuration file:
        self.config = ConfigObj('./tests/config')
        self.config['jira']['password'] = get_jira_pass()
        self.bug = None
        self.task = None

    def tearDown(self):
        self.jira = air.Jira(self.config['jira'])
        for x in [self.bug, self.task]:
            if x is not None:
                self.jira.delete_issue(x)

    def test_create_bug(self):
        sys.argv = ['bogus', 'create_bug', "this is a test bug"]
        d = air.Dispatcher(self.config)
        out = StringIO()
        d.go(out=out)
        actual = out.getvalue().strip()
        match = re.search('MMSANDBOX-\d*', actual)
        self.bug = match.group()
        self.assertRegexpMatches(actual, 'bug created: MMSANDBOX-\d*')

    def test_create_task(self):
        sys.argv = ['bogus', 'create_task', "this is a test task"]
        d = air.Dispatcher(self.config)
        out = StringIO()
        d.go(out=out)
        actual = out.getvalue().strip()
        match = re.search('MMSANDBOX-\d*', actual)
        self.task = match.group()
        self.assertRegexpMatches(actual, 'task created: MMSANDBOX-\d*')


class TestCloseJiraIssue(unittest.TestCase):

    def setUp(self):
        self.config = ConfigObj('./tests/config')
        self.config['jira']['password'] = get_jira_pass()
        self.summary = "test bug for closing issue"
        self.jira = air.Jira(self.config['jira'])
        self.bug = self.jira.create_issue(self.summary, self.summary)

    def tearDown(self):
        self.bug.delete()

    def test_transition_issue(self):
        '''
        Check that attempting to close an issue actually closes it.
        '''
        issue = self.jira.transition_issue(self.bug, status='Resolve Issue')
        expected = 'Resolved'
        self.assertEqual(expected, issue.fields.status.name)

    def test_bad_transition(self):
        '''
        Check that trying an invalid status transition throws the right
        exception.
        '''
        with self.assertRaises(InvalidJiraStatusException):
            self.jira.transition_issue(self.bug, status='Gobbldygook')


class TestListIssues(unittest.TestCase):

    def setUp(self):
        # the test config has both a JQL string and a filter name
        self.config = ConfigObj('./tests/config')
        self.config['jira']['password'] = get_jira_pass()
        self.summary = "test bug for listing issues"
        self.jira = air.Jira(self.config['jira'])
        self.bug = self.jira.create_issue(self.summary, self.summary)

    def tearDown(self):
        self.jira.transition_issue(self.bug, status='Resolve Issue')

    def test_jql(self):
        # create a bug (in setUp) and then make the JQL query just search for
        # that bug; then we're relatively confident we're using the JQL
        self.jira.config['list']['jql'] = \
                'assignee=currentUser() AND issue={}'.format(self.bug.key)
        issues = self.jira.list_issues()
        # there should only be one issue:
        self.assertEqual(1, len(issues))
        issue = issues[0]
        expected = self.bug.key
        actual = issue.key
        # and it should be the one we just created:
        self.assertEqual(expected, actual)

    @unittest.skip('I do not know of a way to create a filter \
        programmatically so this test would only work for me')
    def test_filter(self):
        pass


class TestAddComment(unittest.TestCase):

    def setUp(self):
        # mock the configuration file:
        self.config = ConfigObj('./tests/config')
        self.config['jira']['password'] = get_jira_pass()

        self.summary = "test bug for start of work"
        self.jira = air.Jira(self.config['jira'])
        self.bug = self.jira.create_issue(self.summary, self.summary)

    def tearDown(self):
        self.jira.transition_issue(self.bug, status='Resolve Issue')

    def test_add_comment(self):
        sys.argv = ['bogus', 'add_comment', '-t', self.bug.key, "this", "is", "a",
                "test", "comment"]
        d = air.Dispatcher(self.config)
        out = StringIO()
        d.go(out=out)
        output = out.getvalue().strip()
        self.assertRegexpMatches(output, 'Comment added to')

        # check ticket for comment
        issue = self.jira.get_issue(self.bug)
        actual = issue.fields.comment.comments[0].body
        expected = 'this is a test comment'
        self.assertEqual(expected, actual)


class TestConfig(unittest.TestCase):

    def setUp(self):
        # mock the configuration file:
        self.config = ConfigObj('./tests/config')
        self.config['jira']['password'] = get_jira_pass()

        self.summary = "test bug for start of work"
        self.jira = air.Jira(self.config['jira'])
        self.bug = self.jira.create_issue(self.summary, self.summary)
        self.cmd = air.Commands(self.config)

        self.repo_url, self.repo_file = setup_svn()
        self.config['svn']['root_url'] = self.repo_url
        self.config['svn']['branch_url'] = self.repo_url + '/branches'
        self.config['svn']['trunk_url'] = self.repo_url + '/trunk'

    def tearDown(self):
        self.jira.transition_issue(self.bug, status='Resolve Issue')

    def test_svn_config(self):
        # for this test, remove the svn section of the config file and make
        # sure the code handles it
        del self.config['svn']
        self.cmd = air.Commands(self.config)


class TestFinishWork(unittest.TestCase):

    def setUp(self):
        # mock the configuration file:
        self.config = ConfigObj('./tests/config')
        self.config['jira']['password'] = get_jira_pass()

        self.summary = "test bug for finish work"
        self.jira = air.Jira(self.config['jira'])
        self.bug = self.jira.create_issue(self.summary, self.summary)
        self.cmd = air.Commands(self.config)
        self.jira.transition_issue(self.bug, status='Start Progress')

    def tearDown(self):
        self.bug.delete()

    def test_finish_work(self):
        sys.argv = ['bogus', 'finish_work', '-t', self.bug.key]
        d = air.Dispatcher(self.config)
        out = StringIO()
        actual = d.go(out=out)
        # the issue should now be "Ready for Review":
        expected = 'Ready for Review'
        actual = self.jira.get_issue(self.bug).fields.status.name
        self.assertEqual(expected, actual)


class TestStartWork(unittest.TestCase):

    def setUp(self):
        # mock the configuration file:
        self.config = ConfigObj('./tests/config')
        self.config['jira']['password'] = get_jira_pass()

        self.summary = "test bug for start of work"
        self.jira = air.Jira(self.config['jira'])
        self.bug = self.jira.create_issue(self.summary, self.summary)
        self.cmd = air.Commands(self.config)

        self.repo_url, self.repo_file = setup_svn()
        self.config['svn']['root_url'] = self.repo_url
        self.config['svn']['branch_url'] = self.repo_url + '/branches'
        self.config['svn']['trunk_url'] = self.repo_url + '/trunk'

    def tearDown(self):
        self.bug.delete()

    def test_start_work(self):
        sys.argv = ['bogus', 'start_work', '-t', self.bug.key]
        d = air.Dispatcher(self.config)
        out = StringIO()
        actual = d.go(out=out)

        # a branch should've been created:
        actual = self.cmd.svn.get_unique_branch('start')
        self.assertTrue(actual)

        # and the associated issue should now be "In Progress":
        expected = 'In Progress'
        actual = self.jira.get_issue(self.bug).fields.status.name
        self.assertEqual(expected, actual)
        issue = self.jira.get_issue(self.bug)
        actual = issue.fields.comment.comments[0].body
        self.assertRegexpMatches(actual, 'SVN URL')


@contextlib.contextmanager
def capture():
    oldout, olderr = sys.stdout, sys.stderr
    try:
        out = [StringIO(), StringIO()]
        sys.stdout, sys.stderr = out
        yield out
    finally:
        sys.stdout, sys.stderr = oldout, olderr
        out[0] = out[0].getvalue()
        out[1] = out[1].getvalue()


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
        out = StringIO()
        actual = d.go(out=out)
        output = out.getvalue().strip()
        self.assertEqual(0, actual)
        self.assertGreater(len(output), 0)

    @unittest.skip("removed main -- test air command instead")
    def test_main(self):
        '''
        This is kinda lame and doesn't test much, but it makes sure there's
        test coverage for main().
        '''
        sys.argv = ['bogus', 'list_tickets']
        actual = air.main()
        expected = 0
        self.assertEqual(expected, actual)
