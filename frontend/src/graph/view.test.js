import test from 'node:test';
import assert from 'node:assert/strict';
import {graphView} from './view.js';

test('only verified import path produces edges, including intermediate nodes', () => {
  const candidates = [{path:'b.py', evidence:{import_path:['a.py','middle.py','b.py']}}];
  const view = graphView({seed:'a.py'}, candidates, 'b.py');
  assert.deepEqual(new Set(view.nodes.map(node => node.id)), new Set(['a.py','middle.py','b.py']));
  assert.equal(view.edges.length, 2);
  assert.equal(view.edges[0].source, 'a.py');
  assert.equal(view.edges[0].target, 'middle.py');
});

test('a ranking recommendation alone never implies a dependency', () => {
  const view = graphView({seed:'a.py'}, [{path:'b.py'}], 'b.py');
  assert.equal(view.edges.length, 0);
});
