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
