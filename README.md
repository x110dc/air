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

To run the full test suite need access to a Jira instance and a Crucible/FishEye instance.
