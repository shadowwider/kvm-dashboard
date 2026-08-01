import assert from 'node:assert/strict';
import test from 'node:test';

import { resolveTranslation } from '../src/utils/translation.js';

const dictionary = {
    detail: {
        device: 'Device',
    },
};

test('resolveTranslation resolves nested dictionary keys', () => {
    assert.equal(resolveTranslation(dictionary, 'detail.device'), 'Device');
});

test('resolveTranslation falls back when an optional translation key is absent', () => {
    assert.equal(resolveTranslation(dictionary, null, 'Fan 1'), 'Fan 1');
    assert.equal(resolveTranslation(dictionary, undefined, 'CPU port'), 'CPU port');
    assert.equal(resolveTranslation(dictionary, '', 'CON port'), 'CON port');
});

test('resolveTranslation preserves the key when no translation or fallback exists', () => {
    assert.equal(resolveTranslation(dictionary, 'detail.unknown'), 'detail.unknown');
});
