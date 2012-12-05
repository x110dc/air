from distutils.core import setup


setup(name='air',
      version='0.2',
      description='Air Is Refreshing',
      packages=['rair'],
      author='Daniel Craigmile',
      author_email='daniel.craigmile@mutualmobile.com',
      requires=['configobj', 'jira_python', 'sh'],
      scripts=['air']
      )
