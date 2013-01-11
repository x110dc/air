issue: can either be a Jira bug or a Jira task
task: Jira task
bug: Jira bug
ticket: synonym for issue?

# air mkticket "text goes here"
# air mkbranch <ticket number> (creates a branch based on a Jira ticket)
# air start <ticket> (marks ticket as in progress?)

mkbranch 3530 "add email resource list to Contact"

run tests:

    % nosetests --with-cov --cov-report html
    % nosetests --with-cov --cov-report html tests/tests.py:TestCloseJiraIssue
