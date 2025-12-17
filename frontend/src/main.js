// src/main.js
import { createApp } from "vue";
import Home from "./views/Home.vue";
import "./assets/styles.css";
import { i18n } from "./i18n";

createApp(Home).use(i18n).mount("#app");
