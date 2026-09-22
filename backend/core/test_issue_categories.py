"""
Unit and integration tests for CommitRush Issue Categories endpoint,
category filtering in IssueListView, and AdminIssueUpdateSerializer category choices.
"""

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from core.categories import ISSUE_CATEGORIES, VALID_CATEGORY_KEYS
from core.models import Issue, Project
from core.serializers import AdminIssueUpdateSerializer


class IssueCategoriesApiTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.project = Project.objects.create(
            github_repo_id=999,
            owner='hackit',
            name='test-repo',
            full_name='hackit/test-repo',
            language='Python',
            is_enabled=True,
        )

        # Seed issues for multiple categories
        self.issue_feat1 = Issue.objects.create(
            github_issue_id=101,
            number=1,
            project=self.project,
            title='Feature 1',
            difficulty='easy',
            category='feature',
            status='open',
            points=20,
            is_featured=True,
        )
        self.issue_feat2 = Issue.objects.create(
            github_issue_id=102,
            number=2,
            project=self.project,
            title='Feature 2',
            difficulty='hard',
            category='feature',
            status='assigned',
            points=100,
            is_featured=False,
        )
        self.issue_sec = Issue.objects.create(
            github_issue_id=103,
            number=3,
            project=self.project,
            title='Security patch',
            difficulty='medium',
            category='security',
            status='open',
            points=60,
            is_featured=False,
        )
        self.issue_docs = Issue.objects.create(
            github_issue_id=104,
            number=4,
            project=self.project,
            title='Documentation fix',
            difficulty='easy',
            category='docs',
            status='closed',
            points=10,
            is_featured=False,
        )

    def test_categories_endpoint_public_and_complete(self):
        """GET /api/v1/issues/categories/ should return all 16 categories with counts."""
        response = self.client.get('/api/v1/issues/categories/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), len(ISSUE_CATEGORIES))

        # Build map of value -> count
        counts = {item['value']: item['count'] for item in data}
        self.assertEqual(counts.get('feature'), 2)
        self.assertEqual(counts.get('security'), 1)
        self.assertEqual(counts.get('docs'), 1)
        self.assertEqual(counts.get('test'), 0)
        self.assertEqual(counts.get('devops'), 0)

        # Verify keys and non-empty labels
        for item in data:
            self.assertIn('value', item)
            self.assertIn('label', item)
            self.assertIn('count', item)
            self.assertIn(item['value'], VALID_CATEGORY_KEYS)
            self.assertTrue(len(item['label']) > 0)

    def test_issue_list_filtering_by_category(self):
        """GET /api/v1/issues/?category=<cat> filters issues accurately."""
        # Category: feature
        resp_feat = self.client.get('/api/v1/issues/?category=feature')
        self.assertEqual(resp_feat.status_code, status.HTTP_200_OK)
        data_feat = resp_feat.json()
        self.assertEqual(data_feat['count'], 2)
        self.assertTrue(all(item['category'] == 'feature' for item in data_feat['results']))

        # Category: security
        resp_sec = self.client.get('/api/v1/issues/?category=security')
        self.assertEqual(resp_sec.status_code, status.HTTP_200_OK)
        data_sec = resp_sec.json()
        self.assertEqual(data_sec['count'], 1)
        self.assertEqual(data_sec['results'][0]['title'], 'Security patch')

        # Category: non-existent in db returns 0 count
        resp_empty = self.client.get('/api/v1/issues/?category=devops')
        self.assertEqual(resp_empty.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_empty.json()['count'], 0)

    def test_issue_list_filter_composition_and_semantics(self):
        """Category filter composes correctly with difficulty, status, and is_featured."""
        # category=feature AND difficulty=easy
        resp = self.client.get('/api/v1/issues/?category=feature&difficulty=easy')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()['count'], 1)
        self.assertEqual(resp.json()['results'][0]['title'], 'Feature 1')

        # category=feature AND status=open
        resp = self.client.get('/api/v1/issues/?category=feature&status=open')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()['count'], 1)
        self.assertEqual(resp.json()['results'][0]['title'], 'Feature 1')

        # category=feature AND is_featured=true
        resp = self.client.get('/api/v1/issues/?category=feature&is_featured=true')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()['count'], 1)
        self.assertEqual(resp.json()['results'][0]['title'], 'Feature 1')

        # category=feature AND is_featured=false
        resp = self.client.get('/api/v1/issues/?category=feature&is_featured=false')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()['count'], 1)
        self.assertEqual(resp.json()['results'][0]['title'], 'Feature 2')

    def test_admin_serializer_category_validation(self):
        """AdminIssueUpdateSerializer accepts all valid categories and rejects invalid ones."""
        # Test valid categories
        for cat in VALID_CATEGORY_KEYS:
            serializer = AdminIssueUpdateSerializer(
                instance=self.issue_feat1,
                data={'category': cat},
                partial=True,
            )
            self.assertTrue(
                serializer.is_valid(),
                f"Expected category '{cat}' to be valid in AdminIssueUpdateSerializer, errors: {serializer.errors}"
            )

        # Test invalid category
        bad_serializer = AdminIssueUpdateSerializer(
            instance=self.issue_feat1,
            data={'category': 'completely_invalid_cat_xyz'},
            partial=True,
        )
        self.assertFalse(bad_serializer.is_valid())
        self.assertIn('category', bad_serializer.errors)
