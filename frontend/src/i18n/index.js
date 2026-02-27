import { create } from 'zustand';

export const useTranslationStore = create((set) => ({
  locale: 'zh-CN',
  setLocale: (lang) => set({ locale: lang }),
}));

import zhCN from './zh-CN.json';
import enUS from './en-US.json';

const dictionaries = {
  'zh-CN': zhCN,
  'en-US': enUS,
};

export function useTranslation() {
  const locale = useTranslationStore((state) => state.locale);
  const dict = dictionaries[locale] || dictionaries['zh-CN'];

  const t = (key) => {
    return key.split('.').reduce((obj, k) => (obj || {})[k], dict) || key;
  };

  return { t, locale };
}
