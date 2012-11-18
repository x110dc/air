#!/usr/bin/env python3

import unittest
import dev
import tempfile

from sh import svnadmin
from sh import svn


def overwrite(file_object, text):
        if file_object.closed:
            file_object = open(file_object.name, 'w')
        file_object.write(text)
        file_object.close()


def create_svn_repo():

    repo_dir = tempfile.mkdtemp()

    # create repo, with trunk and branches directories
    svnadmin.create(repo_dir)
    repo_url = '{}{}'.format('file://', repo_dir)
    trunk_url = '{}/trunk'.format(repo_url)
    branch_url = '{}/branches'.format(repo_url)
    svn.mkdir(trunk_url, m='trunk dir')
    svn.mkdir(branch_url, m='branches dir')

    return repo_url


def setup_svn():

    # create repo
    repo_url = create_svn_repo()
    trunk_url = '{}/trunk'.format(repo_url)
    branch_url = '{}/branches'.format(repo_url)

    # checkout trunk
    working_dir = tempfile.mkdtemp()
    svn.co(trunk_url, working_dir)

    # create a file
    repo_file = tempfile.NamedTemporaryFile(dir=working_dir, delete=False)
    overwrite(repo_file, '123\n')
    # commit it
    svn.add(repo_file.name, _cwd=working_dir)
    svn.commit(m='message', _cwd=working_dir)

    # create a branch
    new_branch_url = '{}/new-branch'.format(branch_url)
    svn.cp(trunk_url, new_branch_url, m='creating new branch')
    svn.switch(new_branch_url, _cwd=working_dir)
    # change the file and commit
    overwrite(repo_file, '456\n')
    svn.commit(m='message', _cwd=working_dir)

    # change the same file on trunk
    svn.switch(trunk_url, _cwd=working_dir)
    overwrite(repo_file, '789\n')
    svn.commit(m='message', _cwd=working_dir)

    svn.up(_cwd=working_dir)
    svn.merge(new_branch_url, _cwd=working_dir, accept='postpone')

    return repo_url


class Test(unittest.TestCase):

    def setUp(self):
        self.branches = [
                u'CIGNA-1614_Free_Form_Search_Returns_No_Results/\n',
                u'CIGNAINC-1479_prov_type_mapping/\n',
                u'CIGNAINC-1509_improve_claims_api_documentation/\n',
                u'CIGNAINC-1583_ChangePassword_Additional_Security_Fix/\n',
                u'CIGNAINC-1738_Claim_Overview_Claim_Search_Mismatch_Fix/\n',
                u'MCM-1033-MCM-1174_EntitlementsToBlockAccess_CMS/\n',
                u'CIGNAINC-1829_In_Network_Deductible_field/\n',
                u'CIGNAINC-1830_deductible_not_display_id_card/\n',
                u'CIGNAINC-1931_ider_detail_test_for_added_quality_booleans/\n'
                u'CIGNAINC-1941_no_id_cards_successful/\n']

        self.mergeout = [
                u"--- Merging r15521 through r15668 into '/var/folders/y7/mn3mrzyd6_jbz8wm429y57fc0000gq/T/tmpakzinC':\n",
                u'A /var/folders/y7/mn3mrzyd6_jbz8wm429y57fc0000gq/T/tmpakzinC/test/data/drugs\n',
                u'A /var/folders/y7/mn3mrzyd6_jbz8wm429y57fc0000gq/T/tmpakzinC/test/data/drugs/drug_prices.json\n',
                u'U /var/folders/y7/mn3mrzyd6_jbz8wm429y57fc0000gq/T/tmpakzinC/CHANGES\n',
                u' G   /var/folders/y7/mn3mrzyd6_jbz8wm429y57fc0000gq/T/tmpakzinC\n',
                u"--- Recording mergeinfo for merge of r15521 through r15668 into '/var/folders/y7/mn3mrzyd6_jbz8wm429y57fc0000gq/T/tmpakzinC':\n",
                u' G   /var/folders/y7/mn3mrzyd6_jbz8wm429y57fc0000gq/T/tmpakzinC\n']

    def test_get_unique_branch(self):
        actual = dev.get_unique_branch(self.branches, '1174')
        expected = 'MCM-1033-MCM-1174_EntitlementsToBlockAccess_CMS'
        self.assertEqual(expected, actual)

    def test_blah(self):
        setup_svn()
