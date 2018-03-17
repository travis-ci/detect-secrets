from __future__ import absolute_import

import json

import mock
import pytest

from detect_secrets.core.potential_secret import PotentialSecret
from detect_secrets.pre_commit_hook import main
from tests.util.factories import secrets_collection_factory
from tests.util.mock_util import mock_log as mock_log_base
from tests.util.mock_util import mock_open


@pytest.fixture
def mock_get_baseline():
    with mock.patch(
        'detect_secrets.pre_commit_hook.get_baseline',
    ) as m:
        yield m


@pytest.fixture
def mock_log():
    class MockLogWrapper(object):
        """This is used to check what is being logged."""

        def __init__(self):
            self.message = ''

        def error(self, message):
            """Currently, this is the only function that is used
            when obtaining the logger.
            """
            self.message += str(message)

    with mock_log_base('detect_secrets.pre_commit_hook.CustomLog') as m:
        wrapper = MockLogWrapper()
        m().getLogger.return_value = wrapper

        yield wrapper


def assert_commit_blocked(command):
    assert main(command.split()) == 1


def assert_commit_succeeds(command):
    assert main(command.split()) == 0


class TestPreCommitHook(object):

    def test_file_with_secrets(self, mock_log):
        assert_commit_blocked('./test_data/files/file_with_secrets.py')

        message_by_lines = list(filter(
            lambda x: x != '',
            mock_log.message.splitlines()
        ))

        assert message_by_lines[0].startswith(
            'Potential secrets about to be committed to git repo!'
        )
        assert message_by_lines[2] == \
            'Secret Type: High Entropy String'
        assert message_by_lines[3] == \
            'Location:    ./test_data/files/file_with_secrets.py:3'

    def test_file_no_secrets(self):
        assert_commit_succeeds('./test_data/files/file_with_no_secrets.py')

    def test_baseline(self):
        """This just checks if the baseline is loaded, and acts appropriately.
        More detailed baseline tests are in their own separate test suite.
        """
        with mock_open(
                self._create_baseline(),
                'detect_secrets.core.secrets_collection.codecs.open'
        ):
            assert_commit_succeeds(
                '--baseline will_be_mocked ./test_data/file_with_secrets.py'
            )

    def test_quit_early_if_bad_baseline(self, mock_get_baseline):
        mock_get_baseline.side_effect = IOError
        with mock.patch(
                'detect_secrets.pre_commit_hook.SecretsCollection',
                autospec=True,
        ) as mock_secrets_collection:
            assert_commit_blocked(
                '--baseline will_be_mocked ./test_data/file_with_secrets.py'
            )

            assert not mock_secrets_collection.called

    def test_ignore_baseline_file(self, mock_get_baseline):
        mock_get_baseline.return_value = secrets_collection_factory()

        assert_commit_blocked('./test_data/baseline.file')
        assert_commit_succeeds('--baseline baseline.file baseline.file')

    @staticmethod
    def _create_baseline():
        base64_hash = 'c3VwZXIgbG9uZyBzdHJpbmcgc2hvdWxkIGNhdXNlIGVub3VnaCBlbnRyb3B5'
        baseline = {
            'generated_at': 'does_not_matter',
            'exclude_regex': '',
            'results': {
                './test_data/file_with_secrets.py': [
                    {
                        'type': 'High Entropy String',
                        'line_number': 4,
                        'hashed_secret': PotentialSecret.hash_secret(base64_hash),
                    },
                ],
            },
        }

        return json.dumps(baseline)
