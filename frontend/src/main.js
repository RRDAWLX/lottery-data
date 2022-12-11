import { createApp } from "vue";
import './style.css'
import router from './router';
import ElementPlus from 'element-plus';
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import 'element-plus/dist/index.css';
import App from "./App.vue";

const app = createApp(App);
app.use(router);
app.use(ElementPlus, {
  local: zhCn,
});
app.mount("#app");
