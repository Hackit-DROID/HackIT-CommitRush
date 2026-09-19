from django.http import Http404
from django.test import RequestFactory, TestCase
from core.views import custom_404_view


class Custom404ViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_browser_request_returns_html_404_page(self):
        request = self.factory.get('/nonexistent-page/', HTTP_ACCEPT='text/html')
        response = custom_404_view(request)

        self.assertEqual(response.status_code, 404)
        self.assertIn('text/html', response['Content-Type'])
        content = response.content.decode('utf-8')
        self.assertIn('Lost in the Commit Tree', content)
        self.assertIn('ERR_COMMIT_NOT_FOUND • 404', content)
        self.assertIn('Open CommitRush App', content)
        self.assertIn('Explore Issues', content)
        self.assertIn('/nonexistent-page/', content)

    def test_api_request_returns_json_404_response(self):
        import json
        request = self.factory.get('/api/v1/unknown-endpoint/')
        response = custom_404_view(request)

        self.assertEqual(response.status_code, 404)
        self.assertIn('application/json', response['Content-Type'])
        data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(data['status_code'], 404)
        self.assertEqual(data['error'], 'Not Found')
        self.assertIn('/api/v1/unknown-endpoint/', data['detail'])

    def test_json_accept_header_returns_json_404_response(self):
        import json
        request = self.factory.get('/missing-resource/', HTTP_ACCEPT='application/json')
        response = custom_404_view(request)

        self.assertEqual(response.status_code, 404)
        self.assertIn('application/json', response['Content-Type'])
        data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(data['status_code'], 404)
        self.assertEqual(data['error'], 'Not Found')

    def test_handler_accepts_exception_argument(self):
        request = self.factory.get('/another-missing-page/', HTTP_ACCEPT='text/html')
        exception = Http404('Resource does not exist')
        response = custom_404_view(request, exception=exception)

        self.assertEqual(response.status_code, 404)
        self.assertIn('text/html', response['Content-Type'])
        content = response.content.decode('utf-8')
        self.assertIn('Lost in the Commit Tree', content)

    def test_preview_endpoint_in_urls(self):
        response = self.client.get('/404/', HTTP_ACCEPT='text/html')
        self.assertEqual(response.status_code, 404)
        content = response.content.decode('utf-8')
        self.assertIn('Lost in the Commit Tree', content)
