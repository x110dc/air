import requests
import json


class SendRequestException(Exception):
    pass


class Crucible(object):

    def __init__(self, config):
        self.config = config
        self.user_name = config['username']
        self.password = config['password']
        self.crucible_key = config['crucible_key']
        self.uri_api_base = config['server'] + '/source/rest-service'

    def uri_patch(self, review_id):
        return '/'.join([self.uri_api_base, 'reviews-v1', review_id, 'patch'])

    def uri_review(self):
        return '/'.join([self.uri_api_base, 'reviews-v1'])

    def setup_auth_n_headers(self):
        """
        **Parameters**

        **Returns**

        **Raises**
        """
        auth = requests.auth.HTTPBasicAuth(self.user_name, self.password)
        headers = {'Content-Type': 'application/json',
                'Accept': 'application/json'}
        return auth, headers

    def read_data_from_file(self, file_name):
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

    def get_review_id(self, review_data):
        """
        **Parameters**

        **Returns**

        **Raises**
        """
        return review_data['permaId']['id']

    def add_patch(self, review_id, file_name):
        """
        **Parameters**
            ``review_id``
            ``file_name``

        **Returns**

        **Raises**
        """
        auth, headers = self.setup_auth_n_headers()
        patch_data = {'patch': self.read_data_from_file(file_name)}
        response_data = self.send_request('post', self.uri_patch(), auth=auth,
                headers=headers, data=patch_data)
        return response_data

    def create_review(self, participants, allow_others=True, jira_ticket=None):
        """
        This function creates a Crucible review.

        **Parameters**
            ``participants``: A list of usernames for the participants for this
                review (a list of email addresses).
            ``allow_others``: A boolean value representing whether other
            reviewers will be allowed to add themselves to the review.

        **Returns**
            A requests.Response object

        **Raises**
            ReviewSetupException
        """
        auth, headers = self.setup_auth_n_headers()
        creator_data = {'userName': self.user_name}
        reviewers = []
        if not participants:
            participants = []
        for reviewer in participants:
            #Crucible gets upset if the creator of the review is also
            # listed as a
            #participant.
            if reviewer != self.user_name:
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
                'projectKey': self.crucible_key,
                'name': 'Review for {}'.format(jira_ticket),
                'type': 'REVIEW',
            },
            'detailedReviewData': {
                'reviewers': {'reviewer': reviewers},
            }
        }
        if jira_ticket:
            payload['reviewData']['jiraIssueKey'] = jira_ticket
        response_data = self.send_request('post', self.uri_review(), auth=auth,
                headers=headers, data=payload, expected_status_code=201)
        return response_data

    def send_request(self, method, url, auth=None, headers=None, data=None,
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
        payload_json = json.dumps(data)
        print ('**REQUEST**\nMETHOD: {}\nURL: {}\nREQUEST DATA: {}'.format(
                method, url, data))
        response = requests.request(method, url, auth=auth,
                headers=headers, data=payload_json)
        print ('**RESPONSE**\nSTATUS CODE: {}\nHEADERS: {}'
                '\nCONTENT: {}'.format(response.status_code,
                    response.headers, response.content))
        if response.status_code != expected_status_code:
            raise SendRequestException('Received an unexpected response.  '
                    'Expected a response with status code, {}.  Received {} '
                    'instead.'.format(expected_status_code,
                        response.status_code))
        response_data = json.loads(response.content)
        return response_data


#def do_work():
        #Get the user's Atlassian credentials.
        #review_data = create_review(user_name, password,
        #        parsed_args.participants, parsed_args.crucible_key,
        #        jira_ticket=parsed_args.ticket_id)
#    review_id = get_review_id(review_data)
        #Add the diff file.  If it doesn't work out, output the error and keep
        #going.
#    if parsed_args.diff_file:
#        add_patch(user_name, password, review_id,
#                parsed_args.diff_file)
#    review_web_url = '/'.join([CRUCIBLE_WEB_BASE_URL, review_id])
#    #Report the web interface url for the crucible review.
#    print 'Review created: {}'.format(review_web_url)
#    #Add the web interface url to the Associated Jira ticket.
#    return 0
#
#
#if __name__ == '__main__':
#    sys.exit(do_work())
