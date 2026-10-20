import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from urllib.parse import urlsplit

from nexo.knowledge import Knowledge, MemoryInput
from nexo.store import Store
from nexo.research import resolve_public, Extractor, fetch_public
from nexo.api import create_app
from nexo.files import ScopedFiles
from fastapi.testclient import TestClient


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / 'nexo.db')
        self.k = Knowledge(self.store)

    def test_correction_conflict_and_resolution(self):
        first = self.k.put_memory(MemoryInput(key='porta', content='Porta 9187'))
        second = self.k.put_memory(MemoryInput(key='porta', content='Porta 9321'), first['id'])
        self.assertEqual(second['version'], 2)
        self.assertEqual([r['body'] for r in self.k.search('porta')], ['Porta 9321'])
        third = self.k.put_memory(MemoryInput(key='porta', content='Porta 9444'))
        self.assertTrue(all(r['validation'] == 'conflict' for r in self.k.search('porta')))
        self.k.resolve(third['id'])
        self.assertEqual([r['body'] for r in self.k.search('porta')], ['Porta 9444'])

    def test_forgetting_survives_restore(self):
        memory = self.k.put_memory(MemoryInput(key='porta', content='Porta 9187'))
        backup = self.store.backup(self.root / 'before.db')
        self.k.delete_memory(memory['id'])
        self.assertEqual(self.k.search('porta'), [])
        with self.assertRaises(ValueError):
            Store.restore_backup(backup, self.root / 'unsafe.db')
        journal = json.loads(self.store.path.with_suffix('.deletions.json').read_text())
        restored = Store.restore_backup(backup, self.root / 'restored.db', journal)
        self.assertEqual(Knowledge(restored).list_memories(), [])

    def test_incremental_sources_and_exclusion(self):
        first = self.k.import_document('https://example.org/', 'Fonte', 'Uma decisão sobre arquitetura modular.')
        same = self.k.import_document('https://example.org/', 'Fonte', 'Uma decisão sobre arquitetura modular.')
        self.assertFalse(same['changed'])
        self.assertEqual(first['id'], same['id'])
        changed = self.k.import_document('https://example.org/', 'Fonte', 'Escolha de SQLite persistente.')
        self.assertNotEqual(first['id'], changed['id'])
        self.assertEqual(self.k.search('arquitetura'), [])
        self.k.delete_document(changed['id'])
        self.assertEqual(self.k.search('SQLite'), [])
        with self.assertRaises(PermissionError):
            self.k.import_document('https://example.org/', 'Fonte', 'Não reimportar.')

    def test_candidates_secrets_and_literal_query(self):
        self.k.put_memory(MemoryInput(key='decisão', content='SQLite', validation='candidate'))
        self.assertEqual(self.k.search('SQLite OR NEAR("x") *'), [])
        with self.assertRaises(ValueError):
            self.k.put_memory(MemoryInput(key='token', content='sk-' + 'x' * 30))

    def test_memory_api_pauses_and_persists(self):
        project = self.root / 'project'
        project.mkdir()
        app = create_app(self.root / 'api', project)
        client = TestClient(app, base_url='http://127.0.0.1')
        # Sem lifespan/modelo: valida contrato e persistência, sem geração.
        created = client.post('/api/memories', json={'key':'porta','content':'Porta 9321'})
        self.assertEqual(created.status_code, 201)
        item = created.json()
        self.assertEqual(client.get('/api/memories').json()[0]['id'], item['id'])
        self.assertEqual(app.state.store.mode(), 'paused')
        self.assertEqual(client.post('/api/memories/'+item['id']+'/correct', json={'key':'porta','content':'Porta 9444'}).status_code, 200)
        self.assertEqual(client.post('/api/memories/'+item['id']+'/delete', json={}).status_code, 200)
        self.assertEqual(client.get('/api/memories').json(), [])

    def test_metadata_catalog_and_incremental_file_changes(self):
        project = self.root/'project'
        project.mkdir()
        (project/'README.md').write_text('Arquitetura monolítica.',encoding='utf-8')
        (project/'node_modules').mkdir()
        (project/'node_modules/dependency.js').write_text('Não incorporar',encoding='utf-8')
        (project/'credentials.json').write_text('{}',encoding='utf-8')
        scope = ScopedFiles(project)
        catalog = scope.catalog()
        self.assertEqual([row['path'] for row in catalog['files']], ['README.md'])
        self.assertEqual(len(catalog['excluded']),2)
        self.k.sync_files(scope,discover=True)
        self.assertTrue(self.k.search('monolítica'))
        (project/'README.md').write_text('Arquitetura modular.',encoding='utf-8')
        self.k.sync_files(scope)
        self.assertEqual(self.k.search('monolítica'), [])
        self.assertTrue(self.k.search('modular'))
        (project/'README.md').unlink()
        self.k.sync_files(scope)
        self.assertEqual(self.k.search('modular'), [])

    def test_global_profile_and_project_isolation(self):
        global_store = Store(self.root/'profile.db')
        first = Knowledge(self.store, global_store)
        other = Knowledge(Store(self.root/'other.db'),global_store)
        profile = first.put_memory(MemoryInput(key='idioma',category='profile',scope='global',content='Respostas em português.'))
        first.put_memory(MemoryInput(key='porta',content='Porta 9321'))
        self.assertEqual(other.search('porta'),[])
        self.assertEqual(other.context('Explique o projeto')[0]['body'],'Respostas em português.')
        first.put_memory(MemoryInput(key='idioma',category='profile',scope='global',content='Respostas em espanhol.'),profile['id'])
        self.assertEqual(other.context('Explique o projeto')[0]['body'],'Respostas em espanhol.')
        first.delete_memory(profile['id'])
        self.assertEqual(other.context('Explique o projeto'),[])

    def test_expired_memory_is_not_context(self):
        self.k.put_memory(MemoryInput(key='porta',content='Porta 9187',valid_until='2020-01-01T00:00:00Z'))
        self.assertEqual(self.k.context('porta'),[])

    def test_forget_removes_transitive_chat_history(self):
        memory = self.k.put_memory(MemoryInput(key='porta',content='Porta 9321'))
        first = self.store.create(prompt='Qual porta?',files=[])
        self.store.claim()
        with self.store.connect() as conn:
            self.store.event(conn,first['id'],'memories',[{'item_id':memory['id']}])
        self.store.append(first['id'],'Porta 9321')
        self.store.finish(first['id'],'completed')
        second = self.store.create(prompt='Repita a resposta anterior',files=[])
        self.store.claim()
        self.store.append(second['id'],'Porta 9321')
        self.store.finish(second['id'],'completed')
        self.k.delete_memory(memory['id'])
        self.assertNotIn('9321',self.store.get(second['id'])['answer'])
        self.assertTrue(all('9321' not in str(row['data']) for row in self.store.events(second['id'])))

    def test_source_changes_invalidate_derived_knowledge(self):
        source = self.k.import_document('https://example.org/','Projeto','Servidor usa SQLite.')
        self.k.put_memory(MemoryInput(key='persistência',content='Servidor usa SQLite.',category='knowledge',source=source['source'],evidence=[source['id']]))
        self.assertTrue(self.k.search('persistência'))
        self.k.import_document(source['source'],'Projeto','Servidor usa outro mecanismo.')
        self.assertEqual(self.k.search('persistência'),[])
        self.assertEqual(self.k.list_memories()[0]['validation'],'stale')


class ResearchTests(unittest.TestCase):
    def test_redirect_is_rechecked_before_connecting(self):
        connection = MagicMock()
        response = connection.getresponse.return_value
        response.status = 302
        response.getheader.return_value = 'http://127.0.0.1/'
        with patch('nexo.research.resolve_public',side_effect=[(urlsplit('https://example.org/'),'93.184.216.34',443),PermissionError('Privado')]), patch('nexo.research.PinnedConnection',return_value=connection) as constructor:
            with self.assertRaises(PermissionError):
                fetch_public('https://example.org/')
            self.assertEqual(constructor.call_count,1)
            connection.close.assert_called_once()

    def test_source_size_is_bounded(self):
        connection = MagicMock()
        response = connection.getresponse.return_value
        response.status = 200
        response.getheader.side_effect = lambda key,default=None: {'Content-Type':'text/plain','Content-Encoding':'identity'}.get(key,default)
        response.read1.return_value = b'ab'
        with patch('nexo.research.resolve_public',return_value=(urlsplit('https://example.org/'),'93.184.216.34',443)), patch('nexo.research.PinnedConnection',return_value=connection):
            with self.assertRaisesRegex(ValueError,'limite'):
                fetch_public('https://example.org/',max_bytes=1)
            connection.close.assert_called_once()

    def test_private_dns_and_credentials_rejected(self):
        with patch('nexo.research.socket.getaddrinfo', return_value=[(2, 1, 6, '', ('127.0.0.1', 443))]):
            with self.assertRaises(PermissionError):
                resolve_public('https://example.org/')
        with self.assertRaises(ValueError):
            resolve_public('https://user:password@example.org/')
        with self.assertRaises(PermissionError):
            resolve_public('https://example.org/?token=secret')

    def test_html_scripts_are_not_evidence(self):
        parser = Extractor()
        parser.feed('<title>Fonte</title><script>roubar()</script><p>Texto útil.</p>')
        self.assertEqual(parser.text(), 'Texto útil.')
