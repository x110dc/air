#!/usr/bin/env python

# stdlib
from __future__ import print_function

import argparse
import inspect
import os.path
import re
import shutil
import sys
import tempfile
import webbrowser
import urllib

# installed:
from atlassian_jira import Jira
from crucible import Crucible
from sh import svn
from subversion import Subversion


class MergeException(Exception):
    pass


class TicketSpecificationException(Exception):
    pass


class Commands(object):
    """
    This class encapsulates all the of the subcommands available for this
    program.  Each function is a subcommand and must have the following
    signature:

    my_awesome_function(self, arger, args, out=sys.stdout)

    The 'arger' is an instance of ArgumentParse class and will be passed to
    every function as the first (non-self) argument.  The ArgumentParse class
    will have been parsed up to the point of determining the subcommand but
    further processing of command line arguments is left to this function.

    The method should send it's output to the buffer passed in as the 'out'
    parameter.  If no parameter is passed output should be sent to sys.stdout.
    """

    def __init__(self, config):
        self.config = config
        if 'jira' in config:
            self.jira = Jira(config['jira'])
        else:
            self.jira = None
        if 'svn' in config:
            self.svn = Subversion(config['svn'])
        else:
            self.svn = None
        if 'crucible' in config:
            self.crucible = Crucible(config['crucible'])
        else:
            self.crucible = None

    def init(self, arger, args, out=sys.stdout):
        """
        create a sample .airrc file
        """

        # check to see if an .airrc file already exists
        # if so, warn and don't overwrite
        if os.path.isfile('.airrc'):
            out.write('An .airrc file already exists in the directory.')
            return
        text = '''
[jira]
    username = first.last
    password = changeme
    server = https://jira.r.mutualmobile.com
# new issues will be created in this project:
    project = MMSANDBOX

    [[list]]
#       filter = 'assigned to me'
        jql = 'assignee=currentUser()  AND status != Closed'
    [[review]]
#       filter = 'ready for review'
        jql = 'status IN ("Ready for Review", "In Review")'
[crucible]
    username = first.last
    password = changeme2
    key = CR-MMSANDBOX
    server = https://fisheye.r.mutualmobile.com

[aliases]
    ls=list_tickets
    start=start_work
    mkticket=create_bug
    mkbug=create_bug
    mktask=create_task
    mkbranch=make_branch
    comment=add_comment
'''
        airrc = open('.airrc', 'w')
        airrc.write(text)
        airrc.close()

    def start_review(self, arger, args, out=sys.stdout):
        """
        create a Crucible review for a ticket
        """
        arger.add_argument('-t', '--ticket')
        arger.add_argument('-p', '--person', action='append')
        arger.add_argument('-o', '--open', action='store_true')
        opts = arger.parse_args(args)

        issue = self.jira.get_issue(opts.ticket)
        branch = self.svn.get_unique_branch(issue.key)
        # find available transitions for issue:
        transitions = self.jira.server.transitions(issue)
        #TODO: move this functionality into the module?:
        if 'In Review' in [x['name'] for x in transitions]:
            # mark Jira issue as 'in review'
            self.jira.transition_issue(opts.ticket, status='In Review')
        # create review
        self.review = self.crucible.create_review(opts.person,
                                                  jira_ticket=issue.key)
        # create diff
        #TODO: so this in SVN module:
        diff = self.svn.diff(branch)
        # add diff to review
        self.review.add_patch(diff)
        # "start" the review:
        self.review.start()
        # open review in browser
        if opts.open:
            self.url = self.review.uri_frontend
            out.write('Opening review {0} in browser...'.format(
                self.review.uri_frontend))
            webbrowser.open_new_tab(self.url)
        # add Crucible URL to Jira ticket
        # as long as the Jira ticket is associated with Crucible then there's a
        # link under 'Reviews', so this isn't necessary:
        #self.jira.add_comment(opts.ticket, 'Crucible: {0}'.format(self.url))
        out.write('Created review {0} for ticket {1}..\n'.format(self.review,
                                                                 issue.key))

    def reject_ticket(self, arger, args, out=sys.stdout):

        arger.add_argument('-t', '--ticket')
        opts = arger.parse_args(args)
        comment = 'Sending issue back for rework. Please see comments \
            in review.'
        issue = self.jira.get_issue(opts.ticket)
        self.jira.add_comment(issue.key, comment)
        self.jira.transition_issue(issue.key, status='Reopen Issue')

    def start_work(self, arger, args, out=sys.stdout):

        """
        start work on ticket (start progress and create branch)
        """

        self.make_branch(arger, args)
        opts = arger.parse_args(args)
        issue = self.jira.get_issue(opts.ticket)
        out.write('Marking issue {0} as "In Progress"\n'.format(issue.key))
        self.jira.transition_issue(opts.ticket, status='In Progress')
        branch = self.svn.get_unique_branch(opts.ticket)
        comment = 'SVN URL: ' + self.config['svn']['branch_url'] + '/' + branch
        out.write('Adding SVN URL for branch to Jira issue\n')
        self.jira.add_comment(issue.key, comment)

    def add_watcher(self, arger, args, out=sys.stdout):

        """
        add watcher to ticket
        """
        arger.add_argument('-t', '--ticket')
        arger.add_argument('-p', '--person')
        opts = arger.parse_args(args)
        if not opts.ticket:
            opts.ticket = _get_ticket_from_dir()
            if not opts.ticket:
                raise TicketSpecificationException("ticket number required")
        self.jira.add_watcher(opts.ticket, opts.person)
        out.write('Added {0} as a watcher on {1}\n'.format(opts.person,
                                                           opts.ticket))

    def finish_work(self, arger, args, out=sys.stdout):

        """
        finish work on ticket (mark it as 'Ready for Review')
        """

        arger.add_argument('-t', '--ticket')
        opts = arger.parse_args(args)
        issue = self.jira.get_issue(opts.ticket)
        if not opts.ticket:
            opts.ticket = _get_ticket_from_dir()
            if not opts.ticket:
                raise TicketSpecificationException("ticket number required")
        out.write('Marking issue {0} as "Ready for Review"\n'.format(issue))
        self.jira.transition_issue(opts.ticket, status='Ready for Review')

    def finish_review(self, arger, args, out=sys.stdout):

        """
        summarize review, reintegrate branch into trunk, and delete branch
        """
        arger.add_argument('-t', '--ticket')
        opts = arger.parse_args(args)
        issue = self.jira.get_issue(opts.ticket)
        branch = self.svn.get_unique_branch(opts.ticket)
        review = self.crucible.get_review_from_issue(issue.key)
        review.finish()
        self.svn.reintegrate(branch)

    def assign(self, arger, args, out=sys.stdout):
        """
        assign ticket to someone
        """
        arger.add_argument('-p', '--person')
        arger.add_argument('-t', '--ticket')
        opts = arger.parse_args(args)
        assignee = opts.person
        self.jira.assign_issue(opts.ticket, assignee)
        out.write('{0} assigned to {1}.\n'.format(opts.ticket, assignee))

    def take(self, arger, args, out=sys.stdout):
        """
        assign ticket to myself
        """
        assignee = self.config['jira']['username']
        arger.add_argument('-t', '--ticket')
        opts = arger.parse_args(args)
        self.jira.assign_issue(opts.ticket, assignee)
        out.write('{0} assigned to {1}.\n'.format(opts.ticket, assignee))

    def refresh(self, arger, args, out=sys.stdout):
        """
        refresh branch from trunk

        Given a Jira ticket, refresh the associated branch from trunk.  If
        conflicts are found during the merge process an exception is raised
        and the merge process will need to be completed manually.
        """

        #arger.add_argument('ticket', nargs='?')
        arger.add_argument('-t', '--ticket')
        opts = arger.parse_args(args)
        if not opts.ticket:
            opts.ticket = _get_ticket_from_dir()
            if not opts.ticket:
                raise TicketSpecificationException("ticket number required")

        branch = self.svn.get_unique_branch(opts.ticket)

        src = '{0}/{1}'.format(self.config['svn']['branch_url'], branch)
        try:
            working_dir = tempfile.mkdtemp()
            out.write('Checking out src...\n')
            #TODO: do this in SVN module
            checkout = svn.co(src, working_dir)
            out.write(checkout.ran)
            out.write('Merging from trunk into src...\n')
            #TODO: do this in SVN module
            merge = svn.merge(self.config['svn']['trunk_url'],
                              _cwd=working_dir, accept='postpone')
            out.write(merge.ran)
            out.write(merge.stdout)
            if 'conflicts' in merge:
                raise MergeException(
                    'unable to merge due to conflicts; merge manually')
            #TODO: do this in SVN module
            commit = svn.commit(m='refreshed from trunk', _cwd=working_dir)
            out.write(commit.ran)
            out.write(commit.stdout)
        finally:
            shutil.rmtree(working_dir)
        self.jira.add_comment(opts.ticket,
                              'Branch has been refreshed from trunk')

    def make_branch(self, arger, args, out=sys.stdout):
        """
        create branch based on ticket
        Given a Jira ticket number an Svn branch is created for it.
        """

        arger.add_argument('-t', '--ticket')
        opts = arger.parse_args(args)
        issue = self.jira.get_issue(opts.ticket)
        message = 'created branch for {}'.format(issue.key)
        name = _make_branch_name(issue.key, issue.fields.summary)
        process = self.svn.make_branch(name, message)

        out.write(process.stdout)

    def create_bug(self, arger, args, out=sys.stdout):
        """
        create bug in Jira
        Given a brief description a Jira bug will be created. This uses options
        specified in the config file to create the ticket.
        """

        arger.add_argument('text')
        summary = arger.parse_args(args).text

        bug = self.jira.create_issue(summary, summary)

        out.write('bug created: {0}\n'.format(bug.key))

    def create_task(self, arger, args, out=sys.stdout):
        """
        create task in Jira
        Given a brief description a Jira task will be created. This uses
        options specified in the config file to create the ticket.
        """

        arger.add_argument('text')
        summary = arger.parse_args(args).text

        bug = self.jira.create_issue(summary, summary, kind="Task")

        out.write('task created: {0}\n'.format(bug.key))

    def close_ticket(self, arger, args, out=sys.stdout):
        """
        close issue
        """

        arger.add_argument('-t', '--ticket')
        opts = arger.parse_args(args)
        if not opts.ticket:
            opts.ticket = _get_ticket_from_dir()
            if not opts.ticket:
                raise TicketSpecificationException("ticket number required")

        self.jira.close_issue(opts.ticket)
        out.write('Ticket {0} closed.\n'.format(opts.ticket))

    def add_comment(self, arger, args, out=sys.stdout):
        """
        add comment to Jira ticket
        """

        arger.add_argument('-t', '--ticket')
        arger.add_argument('comment', nargs='*')
        opts = arger.parse_args(args)
        if not opts.ticket:
            opts.ticket = _get_ticket_from_dir()
            if not opts.ticket:
                raise TicketSpecificationException("ticket number required")

        self.jira.add_comment(opts.ticket, ' '.join(opts.comment))
        out.write('Comment added to {0}.\n'.format(opts.ticket))

    def list_reviews(self, arger, args, out=sys.stdout):
        """
        list tickets that are ready for review
        """
        tickets = self.jira.list_reviewable()

        for key, summary in [(x.key, x.fields.summary) for x in tickets]:
            out.write('{0}:\t{1}\n'.format(key, summary))

    def list_tickets(self, arger, args, out=sys.stdout):
        """
        list Jira tickets assigned to me
        """
        tickets = self.jira.list_issues()

        for key, summary in [(x.key, x.fields.summary) for x in tickets]:
            out.write('{0}:\t{1}\n'.format(key, summary))

    def _complete_tickets(self, arger, args, out=sys.stdout):
        """
        this method is only intended for use by the shell completion mechanism
        """
        tickets = self.jira.list_issues()
        for key, summary in [(x.key, x.fields.summary) for x in tickets]:
            out.write('{0}:{1}\n'.format(key, summary))

    def _complete_subcommands(self, arger, args, out=sys.stdout):
        """
        this method is only intended for use by the shell completion mechanism
        """
        def _cleanup(docs):
            if not docs:
                return 'No description given'
            docs = docs.split('\n')
            return docs[1].strip()

        methods = [(x[0], _cleanup(x[1].__doc__))
                   for x in inspect.getmembers(self) if
                   inspect.ismethod(x[1])]

        # remove private methods:
        names = [x for x in methods if not x[0].startswith('_')]
        for x, y in names:
            out.write('{0}:{1}\n'.format(x, y))

    def _complete_persons(self, arger, args, out=sys.stdout):
        """
        this method is only intended for use by the shell completion mechanism
        """
        project = self.config['jira']['project']

        users = self.jira.server.search_assignable_users_for_issues(
            '', project=project, maxResults=500)
        out.write('\n'.join([user.name for user in users]))


def _make_branch_name(issue, text):
    text = text.replace(' ', '_')
    text = text.replace('/', '-')
    text = urllib.quote_plus(text)
    return "{}_{}".format(issue, text)


def _parse_ticket(string):
    match = re.search('URL(.*)', string)
    branch = os.path.basename(match.group(1))
    ticket = re.search('^(\S+-\d+)_', branch).group(1)
    return ticket


def _get_ticket_from_dir():

    #TODO: how to handle non-svn Git dirs?

    if os.path.isdir('.svn'):
        cmd = svn.info()
    elif os.path.isdir('.git'):
        # Git is optional, but only if git is available.
        try:
            from sh import git
            cmd = git.svn.info()
        except ImportError:
            # Now what do we do? ENV or special meta-file, or config?
            return None
    else:
        return None
    return _parse_ticket(cmd.stdout)


def _get_parser(names):

    arger = argparse.ArgumentParser()
    #arger.add_argument('-v', '--verbose', action='count', default=0)
    subparsers = arger.add_subparsers(dest='command', title='subcommands',
                                      description='valid subcommands',
                                      help='non-extant additional help')
    subparsers_dict = dict()
    for name in names:
        subparsers_dict[name] = subparsers.add_parser(name)
    return arger, subparsers_dict


class Dispatcher(object):

    def __init__(self, config):
        self.config = config
        self.commands = Commands(config)
        self.aliases = config['aliases']

    def completion(self):
        methods = [x for x in inspect.getmembers(self.commands) if
                   inspect.ismethod(x[1])]

        names = [x[0] for x in methods] + self.aliases.keys()
        names.remove('__init__')
        print (' '.join(names))

    def go(self, out=sys.stdout):
        # get the names of the functions in the Commands class to use
        # as names for  subcommands for the parser:
        # TODO: use filter() here?
        methods = [x for x in inspect.getmembers(self.commands) if
                   inspect.ismethod(x[1])]

        names = [x[0] for x in methods] + self.aliases.keys()
        names.remove('__init__')
        arger, subparser_dict = _get_parser(names)

        opts = arger.parse_known_args()
        subcommand = opts[0].command
        # get the subparser for the particular subcommand:
        arger = subparser_dict[subcommand]

        # substitute the real command:
        if subcommand in self.aliases:
            subcommand = self.aliases[subcommand]

        # call the subcommand, pass the argument parser object
        if hasattr(self.commands, subcommand):
            getattr(self.commands, subcommand)(arger,
                                               args=sys.argv[2:], out=out)

        return 0
