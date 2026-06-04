"""Unit tests for mnemos.redact."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from mnemos.redact import redact


class TestRedactorHits:
    """Each pattern redacts real-looking secrets."""

    def test_anthropic_key(self):
        text = 'api = "sk-ant-' + 'api03-abc123DEF456ghi789jkl012mno345pqr678stu901vwx"'
        out, n = redact(text)
        assert n == 1
        assert '[REDACTED:anthropic_key]' in out
        assert 'sk-ant-' not in out

    def test_openai_key(self):
        text = 'OPENAI_API_KEY=sk-' + 'proj-abc123def456ghi789jkl'
        out, n = redact(text)
        assert n >= 1
        assert '[REDACTED:openai_key]' in out

    def test_stripe_live_key(self):
        text = 'stripe=sk_' + 'live_51HGabcdefghijklmnopqrstuvw'
        out, n = redact(text)
        assert n >= 1
        assert '[REDACTED:stripe_key]' in out
        # Must not be mistaken for OpenAI sk-.
        assert '[REDACTED:openai_key]' not in out

    def test_stripe_publishable_key(self):
        text = 'pk_' + 'test_abcdefghijklmnopqrstuvwx'
        out, n = redact(text)
        assert n == 1
        assert '[REDACTED:stripe_key]' in out

    def test_github_token(self):
        text = 'token=ghp' + '_abcdefghijklmnopqrstuvwxyz0123456789'
        out, n = redact(text)
        assert n >= 1
        assert '[REDACTED:github_token]' in out

    def test_aws_access_key(self):
        text = 'aws key AKIAIOSFODNN7EXAMPLE and more'
        out, n = redact(text)
        assert n == 1
        assert '[REDACTED:aws_access_key]' in out

    def test_jwt(self):
        text = (
            'bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9'
            '.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4ifQ'
            '.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c'
        )
        out, n = redact(text)
        assert '[REDACTED:jwt]' in out
        assert n >= 1

    def test_slack_webhook(self):
        text = (
            'https://hooks.slack.com/services/T00000000/B00000000/'
            'XXXXXXXXXXXXXXXXXXXXXXXX'
        )
        out, n = redact(text)
        assert '[REDACTED:slack_webhook]' in out
        assert n >= 1

    def test_pem_block(self):
        text = (
            '-----BEGIN RSA PRIVATE KEY-----\n'
            'MIIEpAIBAAKCAQEA...payload...\n'
            '-----END RSA PRIVATE KEY-----'
        )
        out, n = redact(text)
        assert '[REDACTED:pem]' in out
        assert n == 1

    def test_credential_pattern(self):
        text = 'password: my_super_secret_pw_123'
        out, n = redact(text)
        assert '[REDACTED:credential]' in out
        assert n >= 1

    def test_multiple_secrets_one_pass(self):
        text = (
            'key1=sk-ant-abcdef0123456789abcdef0123456789abcdef0123abc '
            'AKIAIOSFODNN7EXAMPLE'
        )
        out, n = redact(text)
        assert n >= 2
        assert '[REDACTED:anthropic_key]' in out
        assert '[REDACTED:aws_access_key]' in out


class TestRedactorMisses:
    """Normal strings are not mangled."""

    def test_no_match_returns_unchanged(self):
        text = 'this is a normal sentence about rewriting the db'
        out, n = redact(text)
        assert out == text
        assert n == 0

    def test_empty_input(self):
        out, n = redact('')
        assert out == ''
        assert n == 0
        out, n = redact(None)  # type: ignore[arg-type]
        assert out == ''
        assert n == 0

    def test_short_sk_dash_not_matched(self):
        # Need >= 20 chars after sk-; short token shouldn't match.
        text = 'sk-abc123'
        out, n = redact(text)
        assert n == 0

    def test_short_eyj_not_matched(self):
        # eyJ + short stuff — not a JWT.
        text = 'eyJhbG and eyJ.a.b'
        out, n = redact(text)
        assert n == 0

    def test_git_checkout_orphan_not_path(self):
        # Just making sure generic text doesn't trigger.
        text = 'run git checkout --orphan main'
        out, n = redact(text)
        assert out == text

    def test_akia_prefix_not_alone(self):
        # Wrong length.
        text = 'AKIA1234'
        out, n = redact(text)
        assert n == 0
