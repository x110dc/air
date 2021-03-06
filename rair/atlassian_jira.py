#!/usr/bin/env python

# installed:
from jira.client import JIRA
from jira.resources import Issue


class InvalidJiraStatusException(Exception):
    pass


'''
class JiraIssue(object):


    def __init__(self, issue):
        if isinstance(issue, jira.resources.Issue):
            self.issue = issue
        elif isinstance(issue, str):
            self.issue = self.server.issue('{0}'.format(issue))
        else:
            raise IssueNotRecognized('issue \'{0}\' not \
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

        return new_issue

    def close_issue(self, ticket):
        issue = self.get_issue(ticket)
        transitions = self.server.transitions(issue)
        transition_names = [x['name'] for x in transitions]
        if 'Stop Progress' in transition_names:
            self.transition_issue(ticket, status='Stop Progress')
            transitions = self.server.transitions(issue)
            transition_names = [x['name'] for x in transitions]

        if 'Resolve Issue' in transition_names:
            self.transition_issue(ticket, status='Resolve Issue')
            return self.get_issue(ticket)
        else:
            raise InvalidJiraStatusException(
                    '\nattempt to close ticket failed. \
            \nValid transitions: {0}'.format(', '.join(transition_names)))

    def transition_issue(self, ticket, status='Resolve Issue'):

        issue = self.get_issue(ticket)
        transitions = self.server.transitions(issue)
        transition_names = [x['name'] for x in transitions]
        if status not in transition_names:
            raise InvalidJiraStatusException(
            '\n\'{0}\' is not a valid status for this Jira issue. \
            \nValid transitions: {1}'.format(
                status, ', '.join(transition_names)))
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

    def list_reviewable(self):
        '''
        if a JQL query is defined in the config use it.  If not:
            if a named filter is defined in the config use it.  If not:
                use the predefined filter.
        '''

        section = self.config.get('review', None)
        jql = 'status IN ("Ready for Review", "In Review") \
            ORDER BY priority, updatedDate ASC'

        if not section:
            return self.query(jql)

        jql_config = section.get('jql', None)
        if jql_config:
            return self.query(jql_config)

        filter_name = section.get('filter', None)

        if filter_name:
            filters = self.server.favourite_filters()
            jql = [x.jql for x in filters if x.name == filter_name][0]
            return self.query(jql)

        return self.query(jql)

    def list_issues(self):
        '''
        if a JQL query is defined in the config use it.  If not:
            if a named filter is defined in the config use it.  If not:
                use the predefined filter.
        '''

        section = self.config.get('list', None)
        jql = 'assignee=currentUser() \
                AND status != Closed AND status != Resolved'

        if not section:
            return self.query(jql)

        jql_config = section.get('jql', None)
        if jql_config:
            return self.query(jql_config)

        filter_name = section.get('filter', None)

        if filter_name:
            filters = self.server.favourite_filters()
            jql = [x.jql for x in filters if x.name == filter_name][0]
            return self.query(jql)

        return self.query(jql)

    def delete_issue(self, ticket):

        issue = self.get_issue(ticket)
        issue.delete()

    def assign_issue(self, ticket, assignee):
        '''
        Given an issue and an assignee, assigns the issue to the assignee.
        '''
        issue = self.get_issue(ticket)
        self.server.assign_issue(issue, assignee)
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
        if isinstance(ticket, Issue):
            ticket = ticket.key

        return self.server.issue('{0}'.format(ticket))
