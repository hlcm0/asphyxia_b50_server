import json
import sqlite3

from fastapi.testclient import TestClient

from app import crypto
from app.main import app
from tests.test_api import upload_payload


def test_v2_upload_encrypts_sensitive_fields_and_preserves_history(tmp_path, monkeypatch):
    database = tmp_path / 'b50.sqlite3'
    monkeypatch.setenv('B50_DATABASE_PATH', str(database))
    monkeypatch.setattr(crypto, 'ENCRYPTION_KEY', bytes(range(32)))
    payload = upload_payload()
    payload.update(schemaVersion=2, serverUrl='https://example.test',
                   cardNo='test-card', password='test-password', pcbid='test-pcb')
    with TestClient(app) as client:
        for _ in range(2):
            assert client.post('/api/sdvx/b50', json=payload).status_code == 200
        latest = client.get('/api/sdvx/b50/latest/123456789').json()['data']
        assert client.get('/api/sdvx/b50/count/123456789').json()['count'] == 2
    with sqlite3.connect(database) as connection:
        stored = [json.loads(row[0]) for row in connection.execute(
            'SELECT payload_json FROM b50_uploads ORDER BY id')]
    assert latest == stored[-1]
    for field in crypto.FIELDS:
        assert stored[0][field] != payload[field]
        assert stored[0][field] != stored[1][field]
    decrypted = crypto.decrypt_cloud_fields(latest.copy())
    for field in crypto.FIELDS:
        assert decrypted[field] == payload[field]
    assert decrypted['schemaVersion'] == 2
    assert decrypted['qq'] == payload['qq']


def test_upload_without_key_keeps_original_plaintext_behavior(monkeypatch):
    monkeypatch.setattr(crypto, 'ENCRYPTION_KEY', None)
    payload = json.dumps({'cardNo': 'test-card', 'password': None})
    assert crypto.encrypt_cloud_fields(payload) == payload
