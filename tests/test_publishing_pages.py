import tempfile
from pathlib import Path
import pytest
from amplifier_publishing import Publisher, PublishingError
from amplifier_publishing.remote import SSHClient, unix_request
from amplifier_publishing.service import PublishingService

def test_pages_are_indexed_scoped_and_keep_selected_evidence(tmp_path):
    source=tmp_path/'source';source.mkdir();(source/'index.html').write_text('page')
    with Publisher(tmp_path/'store') as p:
        releases=[]
        for i in range(12):
            (source/'index.html').write_text(f'page{i}');releases.append(p.build(source,site_id='site',session_id='one',request_id=f'r{i:03}'))
        p.build(source,site_id='other',session_id='two',request_id='hidden')
        p._all=lambda *_: (_ for _ in ()).throw(AssertionError('unbounded read'))
        page=p.page('one',collection='releases',limit=4)
        assert len(page['items'])==4 and all('files' not in r and r['fileCount']==1 for r in page['items'])
        ids={r['id'] for r in page['items']}
        while page['nextCursor']:
            page=p.page('one',collection='releases',limit=4,cursor=page['nextCursor']);ids.update(r['id'] for r in page['items'])
        assert ids=={r['id'] for r in releases}
        assert p.release(releases[0]['id'],'one')['files'][0]['path']=='index.html'
        assert p.receipt('r000','one')['result']['files']
        assert p.receipt('r000','two') is None
        with pytest.raises(PublishingError):p.page('two',collection='releases',cursor=p.page('one',collection='releases',limit=1)['nextCursor'])
        with pytest.raises(PublishingError):p.page('one',limit=101)
        plan=p._db.execute("EXPLAIN QUERY PLAN SELECT id,body FROM records WHERE kind=? AND json_extract(body,'$.sessionId')=? AND id>? ORDER BY id LIMIT ?",('release','one','',5)).fetchall()
        assert any('records_scope' in row[-1] for row in plan)
        p.build(source,site_id='site',session_id='one',request_id='new-after-page')
        p.review(releases[0]['id'],session_id='one',request_id='review',note='Fixture reviewed')
        p.preview(releases[0]['id'],session_id='one',request_id='preview')
        p.deploy(releases[0]['id'],site_id='site',session_id='one',expected_revision=0,request_id='deploy')
        p.stop('site',session_id='one',expected_revision=1,request_id='stop')
        del p._all

def test_real_socket_pages_and_client_negotiation():
    with tempfile.TemporaryDirectory(dir='/tmp',prefix='pp-') as directory:
        base=Path(directory).resolve();source=base/'source';source.mkdir();(source/'index.html').write_text('fixture')
        with PublishingService(base/'store',base/'socket'/'admin.sock') as service:
            release=service.publisher.build(source,site_id='site',session_id='one',request_id='local')
            client=SSHClient(hostname='fixture',python='/python',socket_path='/socket',expected_bind='127.0.0.1')
            client._send=lambda request:unix_request(service.socket_path,request)
            assert client.verify_target()['pagination']['version']==1
            for i in range(7):client.request({'method':'review','sessionId':'one','releaseId':release['id'],'requestId':f'review{i}','note':'fixture checked'})
            service._receipts=lambda *_:(_ for _ in ()).throw(AssertionError('unbounded service read'))
            cursor=None;rows=[]
            while True:
                page=client.request({'method':'page','sessionId':'one','collection':'receipts','limit':3,**({'cursor':cursor} if cursor else {})});rows.extend(page['items']);cursor=page['nextCursor']
                if not cursor:break
            assert len(rows)==8 and len({r['requestId'] for r in rows})==8
            receipt=client.request({'method':'receipt','sessionId':'one','requestId':'review0'})
            assert receipt['rpcPayloadDigest'] and receipt['serviceId']==service.service_id
            assert client.request({'method':'page','sessionId':'one','collection':'releases'})['items'][0]['fileCount']==1
            assert client.request({'method':'release','sessionId':'one','releaseId':release['id']})['files']
            actual=client.verify_target
            client.verify_target=lambda:{**actual(),'pagination':{}}
            with pytest.raises(PublishingError,match='bounded pages'):client.request({'method':'page','sessionId':'one','collection':'sites'})


def test_large_cold_history_does_not_enter_selected_reads(tmp_path):
    """SQLite work and decoding stay bounded with 25,000 unrelated records."""
    import json

    source = tmp_path / 'source'
    source.mkdir()
    (source / 'index.html').write_text('retained source')
    with Publisher(tmp_path / 'store') as publisher:
        first = publisher.build(source, site_id='z-site', session_id='selected', request_id='z-build')
        (source / 'index.html').write_text('second retained source')
        second = publisher.build(source, site_id='a-site', session_id='selected', request_id='a-build')
        publisher.stop('z-site', session_id='selected', expected_revision=0, request_id='z-stop')
        publisher.remove('a-site', session_id='selected', expected_revision=0, request_id='a-remove')
        # Disposable fixture records are historical metadata; no listeners or
        # artifacts are needed for the unrelated authority's catalog.
        publisher._db.executemany('INSERT INTO records VALUES (?,?,?)', [
            (kind, f'cold-{i:05}', json.dumps({'id': f'cold-{i:05}', 'siteId': f'cold-{i:05}',
                                            'sessionId': 'unrelated', 'status': 'stopped'}))
            for i in range(12500) for kind in ('site', 'release')
        ])
        publisher._all = lambda *_: (_ for _ in ()).throw(AssertionError('global history export'))
        steps = 0

        def bounded_work():
            nonlocal steps
            steps += 100
            return int(steps > 10000)

        publisher._db.set_progress_handler(bounded_work, 100)
        try:
            assert [site['id'] for site in publisher.list('selected')] == ['z-site', 'a-site']
            assert [release['id'] for release in publisher.releases('selected')] == [first['id'], second['id']]
            assert publisher.page('selected', collection='releases', limit=1)['nextCursor']
            assert publisher.release(first['id'], 'selected')['files']
            assert publisher.receipt('z-build', 'selected')['result']['id'] == first['id']
            assert publisher.inspect_lifetime() == {'sites': 0, 'previews': 0, 'listeners': 0}
        finally:
            publisher._db.set_progress_handler(None, 0)
        assert steps <= 10000
        assert (source / 'index.html').read_text() == 'second retained source'
        assert publisher.export_release(first['id'], 'selected')['files']['index.html']
        assert publisher.status('a-site', 'selected')['status'] == 'removed'


def test_selected_reads_retain_bytes_and_revision_when_listeners_are_healthy(tmp_path):
    """Passive reads do not alter immutable bytes, receipts or a healthy site."""
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'index.html').write_text('retained artifact')
    with Publisher(tmp_path / 'store') as publisher:
        release = publisher.build(source, site_id='site', session_id='session', request_id='build')
        publisher.review(release['id'], session_id='session', request_id='review', note='fixture review')
        deployed = publisher.deploy(release['id'], site_id='site', session_id='session', expected_revision=0, request_id='deploy')
        before = publisher._db.total_changes
        receipts = publisher.receipts('session')
        exported = publisher.export_release(release['id'], 'session')
        for collection in ('sites', 'releases', 'receipts'):
            publisher.page('session', collection=collection)
        publisher.list('session')
        publisher.releases('session')
        publisher.release(release['id'], 'session')
        publisher.receipt('deploy', 'session')
        assert publisher.status('site', 'session') == deployed['result']
        assert publisher.inspect_lifetime() == {'sites': 1, 'previews': 0, 'listeners': 1}
        assert publisher._db.total_changes == before
        assert publisher.receipts('session') == receipts
        assert publisher.export_release(release['id'], 'session') == exported
        assert (source / 'index.html').read_text() == 'retained artifact'


def test_large_service_receipt_history_stays_bounded_and_prefers_rpc():
    import json
    from amplifier_publishing.remote import digest

    with tempfile.TemporaryDirectory(dir='/tmp', prefix='pscale-') as directory:
        base = Path(directory).resolve()
        with PublishingService(base / 'store', base / 'socket' / 'admin.sock') as service:
            def receipt(request_id, site):
                return {'id': digest(['session', request_id]), 'sessionId': 'session',
                        'requestId': request_id, 'siteId': site, 'action': 'deploy',
                        'state': 'unknown', 'result': None, 'error': None}

            cold = [(f'cold-{i:05}', json.dumps(receipt(f'cold-{i:05}', 'other-site'))) for i in range(8334)]
            service.publisher._db.executemany('INSERT INTO receipts VALUES (?,?,?,?)',
                [('session', rid, 'fixture', body) for rid, body in cold])
            for table, proof in (('imports', 'fingerprint'), ('rpc_receipts', 'payload_digest')):
                service._db.executemany(f'INSERT INTO {table} (session,request,{proof},body) VALUES (?,?,?,?)',
                    [('session', rid, 'fixture', body) for rid, body in cold])
            for i in range(9):
                rid = f'selected-{i}'
                native = receipt(rid, 'selected-site')
                service.publisher._save_receipt(native, 'fixture')
                service._save(native, 'fixture')
                service._save_rpc({**native, 'serviceId': service.service_id, 'rpcPayloadDigest': digest(rid)})
            steps = 0

            def bounded_work():
                nonlocal steps
                steps += 100
                return int(steps > 10000)

            for db in (service._db, service.publisher._db):
                db.set_progress_handler(bounded_work, 100)
            try:
                rows = []
                cursor = None
                while True:
                    request = {'method': 'page', 'expectedServiceId': service.service_id,
                               'sessionId': 'session', 'collection': 'receipts',
                               'siteId': 'selected-site', 'limit': 4}
                    if cursor:
                        request['cursor'] = cursor
                    response = unix_request(service.socket_path, request)
                    rows.extend(response['items'])
                    cursor = response['nextCursor']
                    if not cursor:
                        break
                assert [row['requestId'] for row in rows] == [f'selected-{i}' for i in range(9)]
                assert all(row['rpcPayloadDigest'] and row['serviceId'] == service.service_id for row in rows)
                assert service._receipt('session', 'selected-0') == rows[0]
                assert service.publisher.inspect_lifetime()['listeners'] == 0
            finally:
                for db in (service._db, service.publisher._db):
                    db.set_progress_handler(None, 0)
            assert steps <= 10000
