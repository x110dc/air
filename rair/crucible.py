#!/usr/bin/env python

import sys
import requests
import argparse
import simplejson
import logging
from getpass import getpass


LOG_FILENAME = '/tmp/logging_example.out'
CRUCIBLE_API_BASE_URL = 'https://mutualmobile.jira.com/source/rest-service'
CRUCIBLE_WEB_BASE_URL = 'https://mutualmobile.jira.com/source/cru'
REVIEW_SERVICE_URI = 'reviews-v1'
PATCH_SERVICE_URI = 'patch'
MIME_TYPE_JSON = 'application/json'


logging.basicConfig(filename=LOG_FILENAME, level=logging.DEBUG)
logger = logging.getLogger('review_setup_logger')


class SendRequestException(Exception):
    pass


class ReviewSetupException(Exception):
    pass


def setup_auth_n_headers(user_name, password):
    """
    **Parameters**

    **Returns**

    **Raises**
    """
    auth = requests.auth.HTTPBasicAuth(user_name, password)
    headers = {'Content-Type': MIME_TYPE_JSON, 'Accept': MIME_TYPE_JSON}
    return auth, headers


def read_data_from_file(file_name):
    """
    **Parameters**

    **Returns**

    **Raises**
        ``IOError``
    """
    diff_file = open(file_name, 'r')
    patch_data = diff_file.read()
    diff_file.close()
    return patch_data


def get_review_id(review_data):
    """
    **Parameters**

    **Returns**

    **Raises**
    """
    try:
        return review_data['permaId']['id']
    except KeyError as e:
        logger.exception(e)
        raise ReviewSetupException('There was a problem with uploading the '
                'diff file to Crucible.  Check the log file for more info.')


def add_patch(user_name, password, review_id, file_name):
    """
    **Parameters**
        ``user_name``
        ``password``
        ``review_id``
        ``file_name``

    **Returns**

    **Raises**
    """
    patch_service_url = '/'.join([CRUCIBLE_API_BASE_URL, REVIEW_SERVICE_URI,
            review_id, PATCH_SERVICE_URI])
    auth, headers = setup_auth_n_headers(user_name, password)
    try:
        patch_data = {'patch': read_data_from_file(file_name)}
    except IOError as e:
        logger.exception(e)
        raise ReviewSetupException(e)
    try:
        response_data = send_request('post', patch_service_url, auth=auth,
                headers=headers, data=patch_data)
    except SendRequestException as e:
        logger.exception(e)
        raise ReviewSetupException('Review setup failed while communicating '
                'with Crucible.  Check the log file for more details.')
    return response_data


# create crucible review
def create_review(user_name, password, participants, project_key,
        jira_key=None, allow_others=True):
    """
    This function creates a Crucible review.

    **Parameters**
        ``user_name``: The user name of the creator of this review (an email
            address).
        ``password``: The user's password.
        ``participants``: A list of usernames for the participants for this
            review (a list of email addresses).
        ``project_key``: The identifier of the Crucible project under which the
            review will be created.
        ``jira_key``: The identifier of the Jira ticket with which the Review
            will be associated.  Optional.
        ``allow_others``: A boolean value representing whether other reviewers
            will be allowed to add themselves to the review.

    **Returns**
        A requests.Response object

    **Raises**
        ReviewSetupException
    """
    review_service_url = '/'.join([CRUCIBLE_API_BASE_URL, REVIEW_SERVICE_URI])
    auth, headers = setup_auth_n_headers(user_name, password)
    creator_data = {'userName': user_name}
    reviewers = []
    if not participants:
        participants = []
    for reviewer in participants:
        #Crucible gets upset if the creator of the review is also listed as a
        #participant.
        if reviewer != user_name:
            reviewers.append(
                {
                    'userName': reviewer,
                    'completed': False,
                }
            )
    payload = {
        'reviewData': {
            'allowReviewersToJoin': allow_others,
            'creator': creator_data,
            'author': creator_data,
            'moderator': creator_data,
            'projectKey': project_key,
            'name': 'Review for {}'.format(jira_key),
            'type': 'REVIEW',
        },
        'detailedReviewData': {
            'reviewers': {'reviewer': reviewers},
        }
    }
    if jira_key:
        payload['reviewData']['jiraIssueKey'] = jira_key
    try:
        response_data = send_request('post', review_service_url, auth=auth,
                headers=headers, data=payload, expected_status_code=201)
    except SendRequestException as e:
        logger.exception(e)
        raise ReviewSetupException('Review setup failed while communicating '
                'with Crucible.  Check the log file for more details.')
    return response_data


def send_request(method, url, auth=None, headers=None, data=None,
        expected_status_code=200):
    """
    **Parameters**
        ``method``
        ``url``
        ``auth``
        ``headers``
        ``data``
        ``expected_status_code``

    **Returns**

    **Raises**
    """
    payload_json = simplejson.dumps(data)
    logger.warn('**REQUEST**\nMETHOD: {}\nURL: {}\nREQUEST DATA: {}'.format(
            method, url, data))
    try:
        response = requests.request(method, url, auth=auth,
                headers=headers, data=payload_json)
    except RequestException as e:
        logger.exception(e)
        raise SendRequestException('There was a problem sending an http '
                'request.')
    logger.warn('**RESPONSE**\nSTATUS CODE: {}\nHEADERS: {}'
            '\nCONTENT: {}'.format(response.status_code,
                response.headers, response.content))
    if response.status_code != expected_status_code:
        raise SendRequestException('Received an unexpected response.  '
                'Expected a response with status code, {}.  Received {} '
                'instead.'.format(expected_status_code, response.status_code))
    response_data = simplejson.loads(response.content)
    return response_data


def get_command_line_args():
    """
    """
    parser = argparse.ArgumentParser(
            description='Create a review in Crucible.')
    #Add argument for project key.
    parser.add_argument('project_key', action='store')
    #Add argument for ticket_id.
    parser.add_argument('ticket_id', action='store')
    #Add argument for diff file.
    parser.add_argument('-f', '--diff_file', action='store')
    #Add argument for participants.
    parser.add_argument('-p', '--participants', action='append')
    return parser.parse_args()


def get_credentials():
    """
    """
    #Collect user's Atlassian credentials.
    user_name = raw_input('Enter your Atlassian user name: ')
    password = getpass('Enter your Atlassian password: ')
    return user_name, password


def do_work():
    """
    Do work, son!
    """
    #Obtain the command line arguments.
    parsed_args = get_command_line_args()
    #Get the user's Atlassian credentials.
    user_name, password = get_credentials()
    #Create the review.
    try:
        review_data = create_review(user_name, password,
                parsed_args.participants, parsed_args.project_key,
                jira_key=parsed_args.ticket_id)
    except ReviewSetupException as e:
        print e
        return 1
    #Pull the review_id out of the response body.
    try:
        review_id = get_review_id(review_data)
    except ReviewSetupException as e:
        print e
        return 1
    #Add the diff file.  If it doesn't work out, output the error and keep
    #going.
    if parsed_args.diff_file:
        try:
            patch_response_data = add_patch(user_name, password, review_id,
                    parsed_args.diff_file)
        except ReviewSetupException as e:
            print e
    review_web_url = '/'.join([CRUCIBLE_WEB_BASE_URL, review_id])
    #Report the web interface url for the crucible review.
    print 'Review created: {}'.format(review_web_url)
    #Add the web interface url to the Associated Jira ticket.
    return 0


if __name__ == '__main__':
    sys.exit(do_work())
