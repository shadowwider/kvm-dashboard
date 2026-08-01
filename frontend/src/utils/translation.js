export function resolveTranslation(dict, key, fallback) {
    if (typeof key !== 'string' || key.trim() === '') {
        return fallback || (key == null ? '' : String(key));
    }

    const value = key.split('.').reduce((obj, part) => (obj || {})[part], dict);
    return value || fallback || key;
}
