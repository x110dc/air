#!/usr/bin/env python

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
        transition_names = [x['name'] for x in transitions]
        if status not in transition_names:
            raise InvalidJiraStatusException(
            '\'{}\' is not a valid status for this Jira issue. \
            Valid transitions: {}'.format(status, ', '.join(transition_names)))
        _id = [x['id'] for x in transitions if x['name'] == status][0]
        # transition it:
        self.server.transition_issue(issue, _id)
        return self.get_issue(ticket)

#users = self.jira.server.search_assignable_users_for_issues('',
#        project='CIGNAINC', maxResults=500)

    def add_watcher(self, ticket, person):

        issue = self.get_issue(ticket)
        self.server.add_watcher(issue, person)
        return issue

    def list_issues(self):
        '''
        if a JQL query is defined in the config use it.  If not:
            if a named filter is defined in the config use it.  If not:
                use the predefined filter.
        '''

        if 'jql' in self.config:
            return self.query(self.config['jql'])

        if 'filter' in self.config:
            name = self.config['filter']
            filters = self.server.favourite_filters()
            jql = [x.jql for x in filters if x.name == name][0]
            return self.query(jql)

        jql = 'assignee=currentUser() \
                AND status != Closed AND status != Resolved'

        return self.query(jql)

    def assign_issue(self, ticket, assignee):
        '''
        Given an issue and an assignee, assigns the issue to the assignee.
        '''
        issue = self.get_issue(ticket)
        self.server.assign_issue(assignee)
        return issue

    def add_comment(self, ticket, comment):
        '''
        Given an issue and a comment, adds the comment to the issue.
        '''
        issue = self.get_issue(ticket)
        self.server.add_comment(issue, comment)
        return issue

    def get_issue(self, ticket):
        '''
        Given an issue name, returns a Jira instance of that issue.
        '''
        return self.server.issue('{}'.format(ticket))
