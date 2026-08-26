import assert from 'node:assert/strict';
import test from 'node:test';
import { linkCitations, safeExternalHref, type Trust } from '../app/report';

const trust: Trust = {
  claims: [
    { callout: 1, citations: [{ url: 'https://fda.gov/biosimilars' }] },
    { callout: 2, citations: [{ url: 'https://courtlistener.com/docket' }] },
    { callout: 3, citations: [] },
  ],
};

test('links a callout marker to the source Nimble cited for it', () => {
  const linked = linkCitations('Amjevita approved Sept 2016 [1]', trust);

  assert.equal(linked, 'Amjevita approved Sept 2016 [[1]](https://fda.gov/biosimilars)');
});

test('leaves a callout with no citation as plain text', () => {
  assert.equal(linkCitations('pricing unchanged [3]', trust), 'pricing unchanged [3]');
  assert.equal(linkCitations('no such claim [99]', trust), 'no such claim [99]');
});

test('does not touch a marker that is already a link', () => {
  const already = 'see [2](https://example.com/original)';

  assert.equal(linkCitations(already, trust), already);
});

test('is idempotent, so a re-render never double-wraps', () => {
  const once = linkCitations('claim one [1] and two [2]', trust);

  assert.equal(linkCitations(once, trust), once);
});

test('returns the report untouched when the run carried no trust metadata', () => {
  const report = 'Findings [1] and [2].';

  assert.equal(linkCitations(report, undefined), report);
  assert.equal(linkCitations(report, { claims: [] }), report);
});

test('accepts only http and https URLs as clickable links', () => {
  assert.equal(safeExternalHref('https://fda.gov/x'), 'https://fda.gov/x');
  assert.equal(safeExternalHref('http://fda.gov/x'), 'http://fda.gov/x');

  for (const hostile of [
    'javascript:alert(document.cookie)',
    'JavaScript:alert(1)',
    'data:text/html;base64,PHNjcmlwdD4=',
    'file:///etc/passwd',
    'vbscript:msgbox(1)',
    'not a url at all',
    '',
    null,
    undefined,
  ]) {
    assert.equal(safeExternalHref(hostile as string), undefined, `should reject ${hostile}`);
  }
});

test('never turns a hostile citation URL into a link', () => {
  const hostileTrust: Trust = {
    claims: [{ callout: 1, citations: [{ url: 'javascript:alert(1)' }] }],
  };

  assert.equal(linkCitations('a claim [1]', hostileTrust), 'a claim [1]');
});

test('encodes parentheses so a URL cannot truncate its own markdown link', () => {
  const parenTrust: Trust = {
    claims: [{ callout: 1, citations: [{ url: 'https://en.wikipedia.org/wiki/Drug_(x)' }] }],
  };

  const linked = linkCitations('see [1]', parenTrust);

  assert.equal(linked, 'see [[1]](https://en.wikipedia.org/wiki/Drug_%28x%29)');
  assert.ok(!/\)\)/.test(linked));
});
