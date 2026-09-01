const test = require('node:test');
const assert = require('node:assert/strict');

const apiModule = require('./api.js');

test('resolveApiBase defaults to localhost for local frontend', () => {
  const apiBase = apiModule.resolveApiBase({
    location: { hostname: '127.0.0.1', origin: 'http://127.0.0.1:5500' },
    SPLIT_API_BASE: undefined,
  });

  assert.equal(apiBase, 'http://127.0.0.1:8000');
});

test('resolveApiBase prefers explicit configuration when provided', () => {
  const apiBase = apiModule.resolveApiBase({
    location: { hostname: 'example.com', origin: 'https://example.com' },
    SPLIT_API_BASE: 'https://api.example.com',
  });

  assert.equal(apiBase, 'https://api.example.com');
});
