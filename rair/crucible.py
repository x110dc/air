import requests
import json


class SendRequestException(Exception):
    pass


class Review(object):
    '''
    Represents a crucible review -- an object of this class is returned by the
    'create_review' method from the Crucible class.
    '''

    def __init__(self, crucible, review_id):
        self.crucible = crucible
        self.review_id = review_id

    def __str__(self):
        return self.review_id

    @property
    def uri_patch(self):
        return '/'.join([self.crucible.uri_api_base, 'reviews-v1',
            self.review_id, 'patch'])

    @property
    def uri_abandon(self):
        return '/'.join([self.crucible.uri_api_base, 'reviews-v1',
            self.review_id, 'transition?action=action:abandonReview'])

    @property
    def uri_start(self):
        return '/'.join([self.crucible.uri_api_base, 'reviews-v1',
            self.review_id, 'transition?action=action:approveReview'])

    @property
    def uri_get(self):
        return '/'.join([self.crucible.uri_api_base, 'reviews-v1',
            self.review_id])

    @property
    def uri_frontend(self):
        return '/'.join([self.crucible.config['server'], 'cru',
            self.review_id])

    def remove_reviewers(self, reviewers):
        auth, headers = self.crucible._setup_auth_n_headers()
        for reviewer in reviewers:
            uri = '/'.join([self.crucible.uri_api_base, 'reviews-v1',
                self.review_id, 'reviewers', reviewer])
            self.crucible._send_request('DELETE', uri,
                auth=auth, headers=headers, data={},
                expected_status_code=204)
        return self

    @property
    def reviewers(self):
        auth, headers = self.crucible._setup_auth_n_headers()
        uri = '/'.join([self.crucible.uri_api_base, 'reviews-v1',
            self.review_id, 'reviewers'])
        response_data = self.crucible._send_request('GET', uri,
                auth=auth, headers=headers, data={},
                expected_status_code=200)
        return [x['userName'] for x in response_data['reviewer']]

    def start(self):
        auth, headers = self.crucible._setup_auth_n_headers()
        self.crucible._send_request('post', self.uri_start,
                auth=auth, headers=headers, data={},
                expected_status_code=200)
        return self

    def abandon(self):
        auth, headers = self.crucible._setup_auth_n_headers()
        self.crucible._send_request('post', self.uri_abandon,
                auth=auth, headers=headers, data={},
                expected_status_code=200)
        return self

    def get(self):
        auth, headers = self.crucible._setup_auth_n_headers()
        self.data = self.crucible._send_request('GET', self.uri_get,
                auth=auth, headers=headers, data={},
                expected_status_code=200)
        return self

    def finish(self):
        auth, headers = self.crucible._setup_auth_n_headers()
        uri = '/'.join([self.crucible.uri_api_base, 'reviews-v1',
            self.review_id, 'transition?action=action:summarizeReview'])
        self.crucible._send_request('post', uri,
                auth=auth, headers=headers, data={},
                expected_status_code=200)
        return self

    def add_patch(self, data):
        """
        **Parameters**
            ``data``

        **Returns**

        **Raises**
        """
        auth, headers = self.crucible._setup_auth_n_headers()
        patch_data = {'patch': data}
        response_data = self.crucible._send_request('post',
                self.uri_patch, auth=auth,
                headers=headers, data=patch_data)
        return response_data


def get_review_id(review_data):
        """
        **Parameters**

        **Returns**

        **Raises**
        """
        return review_data['permaId']['id']


class Crucible(object):

    def __init__(self, config):
        self.config = config
        self.user_name = config['username']
        self.password = config['password']
        self.uri_server = config['server']
        self.key = config['key']
        self.uri_api_base = self.uri_server + '/rest-service'

    def uri_review(self):
        return '/'.join([self.uri_api_base, 'reviews-v1'])

    def _setup_auth_n_headers(self):
        """
        **Parameters**

        **Returns**

        **Raises**
        """
        auth = requests.auth.HTTPBasicAuth(self.user_name, self.password)
        headers = {'Content-Type': 'application/json',
                'Accept': 'application/json'}
        return auth, headers

    def get_review_from_issue(self, issue):

        auth, headers = self._setup_auth_n_headers()
        uri = '/'.join([self.uri_api_base, 'search-v1', 'reviewsForIssue'])
        params = dict()
        params['jiraKey'] = issue
        response_data = self._send_request('GET', uri,
                auth=auth, headers=headers, params=params, data={},
                expected_status_code=200)
        review_id = get_review_id(response_data['reviewData'][0])
        return Review(self, review_id)

    def get_review(self, review_id):
        auth, headers = self.crucible._setup_auth_n_headers()
        uri = '/'.join([self.crucible.uri_api_base, 'reviews-v1',
            review_id])
        response_data = self._send_request('GET', uri,
                auth=auth, headers=headers, data={},
                expected_status_code=200)
        return response_data

    def create_review(self, participants, allow_others=True, jira_ticket=None):
        """
        This function creates a Crucible review.

        **Parameters**
            ``participants``: A list of usernames for the participants for this
                review
            ``allow_others``: A boolean value representing whether other
            reviewers will be allowed to add themselves to the review.

        **Returns**
            A requests.Response object

        **Raises**
            ReviewSetupException
        """
        auth, headers = self._setup_auth_n_headers()
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
                'projectKey': self.key,
                'name': 'Review for {0}'.format(jira_ticket),
                'type': 'REVIEW',
            },
            'detailedReviewData': {
                'reviewers': {'reviewer': reviewers},
            }
        }
        if jira_ticket:
            payload['reviewData']['jiraIssueKey'] = jira_ticket
        response_data = self._send_request('post', self.uri_review(),
                auth=auth, headers=headers, data=payload,
                expected_status_code=201)

        review_id = get_review_id(response_data)
        review = Review(self, review_id)
        # remove any reviewers that we didn't add:
        other_reviewers = list(set(review.reviewers) - set(participants))
        # this is ridiculous, but the MMSANDBOX Crucible project is set up to
        # automatically add him, even though it shows him as a deleted user so
        # the API won't let us remove him from the review:
        if 'norman.harman' in other_reviewers:
            other_reviewers.remove('norman.harman')
        review.remove_reviewers(other_reviewers)
        return review

    def _send_request(self, method, url, auth=None, params=None, headers=None, data=None,
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
        #print ('**REQUEST**\nMETHOD: {0}\nURL: {1}\nHEADERS: {2}\nREQUEST DATA: {3}'.format(
        #        method, url, headers, data))
        response = requests.request(method, url, auth=auth,
                headers=headers, data=payload_json, params=params)
        #print ('**RESPONSE**\nSTATUS CODE: {0}\nHEADERS: {1}'
        #        '\nCONTENT: {2}'.format(response.status_code,
        #            response.headers, response.content))
        if response.status_code != expected_status_code:
            raise SendRequestException('Received an unexpected response.  '
                    'Expected a response with status code, {0}.  Received {1} '
                    'instead.'.format(expected_status_code,
                        response.status_code))
        if response.content:
            response_data = json.loads(response.content)
            return response_data
        return None


#def do_work():
        #Get the user's Atlassian credentials.
        #review_data = create_review(user_name, password,
        #        parsed_args.participants, parsed_args.key,
        #        jira_ticket=parsed_args.ticket_id)
#    review_id = get_review_id(review_data)
        #Add the diff file.  If it doesn't work out, output the error and keep
        #going.
#    if parsed_args.diff_file:
#        add_patch(user_name, password, review_id,
#                parsed_args.diff_file)
#    review_web_url = '/'.join([CRUCIBLE_WEB_BASE_URL, review_id])
#    #Report the web interface url for the crucible review.
#    print 'Review created: {0}'.format(review_web_url)
#    #Add the web interface url to the Associated Jira ticket.
#    return 0
#
#
#if __name__ == '__main__':
#    sys.exit(do_work())
