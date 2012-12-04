#!/usr/bin/env python

from __future__ import print_function

# installed:
from jira.client import JIRA


class InvalidJiraStatusException(Exception):
    pass


'''
class JiraIssue(object):


    def __init__(self, issue):
        if isinstance(issue, jira.resources.Issue):
            self.issue = issue
        elif isinstance(issue, str):
            self.issue = self.server.issue('{}'.format(issue))
        else:
            raise IssueNotRecognized('issue \'{}\' not \
                    recognized'.format(issue))

    def __str__(self):
        pass
'''


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

    def transition_issue(self, ticket, status='Resolve Issue'):
        # find ID for status:
        issue = self.get_issue(ticket)
        transitions = self.server.transitions(issue)
        # TODO: what if status isn't in list of transitions?
        transition_names = [x['name'] for x in transitions]
        if status not in transition_names:
            raise InvalidJiraStatusException(
            '\'{}\' is not a valid status for this Jira issue. \
            Valid transitions: {}'.format(status, ', '.join(transition_names)))
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
