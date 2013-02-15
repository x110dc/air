# pip requirements:

- sh
- jira_python
- requests (0.14.2 -- newer is not supported by jira_python
- configobj

# OS requirements:

- patchutils (e.g. apt-get install patchutils)
- subversion
- git (optional)


This is very loosely based on "git flow" (as far as the 'start' and 'finish'
concepts).

# Testing

To run the full test suite you need access to a Jira instance and a Crucible/FishEye instance.

# Examples

Create a sample configuration file:

    % air init      # creates a sample .airrc file in the current directory

See what issues I have assigned to me:
  
    % air ls

What work on a ticket:

    % air start_work --ticket MMSANDBOX-1234
