"""Local acceptance smoke: catalog, full-pool ranking, evidence and HTTP contracts."""
from fastapi.testclient import TestClient
from neural_cartographer.api.app import app


def main():
    client = TestClient(app)
    assert client.get('/api/v1/health').status_code == 200
    repositories = client.get('/api/v1/repositories').json()
    assert 'pallets/flask' in repositories
    files = client.get('/api/files', params={'repo': 'pallets/flask'}).json()
    seed = next(path for path in files if path.endswith('/app.py'))
    response = client.post('/api/v1/analysis', json={'repo': 'pallets/flask', 'seed': seed,
                                                  'ranker': 'combined-v1', 'top_k': 5})
    assert response.status_code == 200, response.text
    result = response.json()
    assert len(result['candidates']) == 5
    assert result['candidate_count'] == len(files) - 1
    assert all(row['path'] != seed for row in result['candidates'])
    assert result['evidence_cutoff'] == result['graph_revision']
    assert len({entity['id'] for entity in result['entities']}) == len(result['entities'])
    print('Smoke passed: catalog → seed → combined ranking → past-only evidence')


if __name__ == '__main__':
    main()
