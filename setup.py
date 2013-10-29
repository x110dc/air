#from distutils.core import setup
from setuptools import setup

setup(name='air',
      version='0.2',
      description='Air Is Refreshing',
      packages=['rair'],
      author='Daniel Craigmile',
      author_email='daniel.craigmile@mutualmobile.com',
      install_requires=[
          'configobj',
          'jira_python',
          'sh',
          'unittest2',
      ],
      scripts=['air']
      )
