"""Public reads composed with the existing opt-in body lifecycle."""
from datetime import timedelta
import tempfile
from pathlib import Path

import pytest

from amplifier_publishing import Publisher, PublishingError
from amplifier_publishing.remote import SSHClient, unix_request
from amplifier_publishing.service import PublishingService
from test_publishing_library import publisher, source, review, deploy
from test_publishing_retention import capture
from test_publishing_retirement import clock, retire


def test_public_receipt_order_and_lifetime_inspection_remain_passive(clock, publisher, source):
    release = capture(publisher, source)
    receipt = publisher.receipt('capture', 'session-one')
    # A reader thread records completion; the next active owner boundary settles it.
    clock[0] += timedelta(days=1)
    publisher._released_reads[release['id']] = clock[0].isoformat()
    before = publisher._db.total_changes
    assert publisher.receipt('capture', 'session-one') == receipt
    assert publisher.receipt(request_id='capture', session_id='session-one') == receipt
    assert publisher.receipt('session-one', 'capture') is None
    assert publisher.inspect_lifetime() == {'sites': 0, 'previews': 0, 'listeners': 0}
    assert publisher._db.total_changes == before
    assert publisher._released_reads == {release['id']: clock[0].isoformat()}
    page = publisher.page('session-one', collection='releases')
    assert page['items'][0]['retention']['unusedSince'] == clock[0].isoformat()
    assert not publisher._released_reads


def test_public_site_pages_preserve_current_retention_choices(clock, publisher, source):
    first = capture(publisher, source, 'first')
    review(publisher, first); deploy(publisher, first)
    (source / 'index.html').write_text('second')
    second = capture(publisher, source, 'second')
    publisher.review(second['id'], session_id='session-one', request_id='review-second')
    publisher.deploy(second['id'], site_id='site-one', session_id='session-one',
                     request_id='deploy-second', expected_revision=1)
    status = publisher.status('site-one', 'session-one')
    assert status['rollbackCandidates'] == [first['id']]
    publisher._all = lambda *_: pytest.fail('public page decoded unrelated history')
    assert publisher.page('session-one', collection='sites')['items'] == [status]
    assert publisher.list('session-one') == [status]
    assert publisher.page('other-session', collection='sites')['items'] == []


def test_service_pages_and_exact_receipt_survive_expired_backup(clock, source):
    # A short private socket path also works on platforms with small sun_path.
    with tempfile.TemporaryDirectory(prefix='pub-compat-', dir='/tmp') as temporary:
        root = Path(temporary)
        with Publisher(root / 'store') as owner:
            release = capture(owner, source)
            clock[0] += timedelta(days=31)
            receipt = retire(owner, release)
            owner.snapshot(root / 'backup')
        with PublishingService(root / 'backup', root / 'admin' / 'socket') as service:
            client = SSHClient(hostname='fixture', python='/python', socket_path='/socket', expected_bind='127.0.0.1')
            client._send = lambda request: unix_request(service.socket_path, request)
            client.verify_target()
            exact = client.request({'method': 'receipt', 'sessionId': 'session-one', 'requestId': 'retire'})
            assert exact == receipt
            assert client.validate_result('receipt', exact) == receipt
            page = client.request({'method': 'page', 'sessionId': 'session-one', 'collection': 'releases'})
            assert page['items'][0]['retention']['availability'] == 'expired'
            assert page['items'][0]['fileCount'] == len(release['files']) and 'files' not in page['items'][0]
            selected = client.request({'method': 'release', 'sessionId': 'session-one', 'releaseId': release['id']})
            assert selected['files'] == release['files']
            assert selected['retention']['availability'] == 'expired'
            assert service.publisher.receipt('retire', 'session-one') == receipt
            with pytest.raises(PublishingError) as error:
                client.request({'method': 'retire', 'sessionId': 'session-one', 'releaseId': release['id']})
            assert error.value.code == 'invalid_argument'
