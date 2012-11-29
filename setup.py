from distutils.core import setup

setup(name='air',
      version='0.2',
      description='Air Is Refreshing',
      author='Daniel Craigmile',
      author_email='daniel.craigmile@mutualmobile.com',
      requires=['configobj', 'jira-python', 'sh', ],
      scripts=['scripts/air'],
      )
