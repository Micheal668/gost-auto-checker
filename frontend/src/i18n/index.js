import { createI18n } from "vue-i18n";
import zh from "./zh.json";
import en from "./en.json";
import ru from "./ru.json";

export const i18n = createI18n({
  legacy: false,
  locale: "zh",
  fallbackLocale: "en",
  messages: { zh, en, ru }
});
