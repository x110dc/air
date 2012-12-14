# the program we're testing:
from rair import air
from rair.crucible import Review

# stdlib
import unittest
import sys
from StringIO import StringIO
import re

# installed libraries:
from configobj import ConfigObj

from tests import get_jira_pass
from tests import setup_svn
from tests import create_branch


class TestCrucibleCreateReview(unittest.TestCase):

    def setUp(self):
        # mock the configuration file:
        self.config = ConfigObj('./tests/config')
        self.config['jira']['password'] = get_jira_pass()
        self.repo_url, self.repo_file = setup_svn()
        # use new values for SVN url:
        self.config['svn']['root_url'] = self.repo_url
        self.config['svn']['branch_url'] = self.repo_url + '/branches'
        self.config['svn']['trunk_url'] = self.repo_url + '/trunk'

        self.svn = air.Subversion(self.config['svn'])

        self.jira = air.Jira(self.config['jira'])
        self.summary = "test bug for Crucible"
        self.crucible = air.Crucible(self.config['jira'])
        self.diff = open('./tests/diff.txt').read()
        self.bug = self.jira.create_issue(self.summary, self.summary)
        self.jira.transition_issue(self.bug, status='Start Progress')
        create_branch(self.repo_url, '{}_test_ticket'.format(self.bug.key))

        self.review = None

    def tearDown(self):
        self.bug.delete()
        if self.review is not None:
            self.review.abandon()

    def test_create_review(self):
        self.review = self.crucible.create_review(['jon.oelfke'],
                jira_ticket=self.bug.key)
        self.assertTrue(self.review)
        response = self.review.add_patch(self.diff)
        self.assertTrue(response)

    def test_start_review(self):
        sys.argv = ['bogus', 'start_review', '--ticket',
                self.bug.key, '--person', 'jon.oelfke']
        d = air.Dispatcher(self.config)
        out = StringIO()
        actual = d.go(out=out)
        output = out.getvalue().strip()
        match = re.search('CR-MMSANDBOX-\d*', output)
        review_id = match.group()
        self.review = Review(self.crucible, review_id)
        self.assertEqual(0, actual)
        self.assertGreater(len(output), 0)


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
