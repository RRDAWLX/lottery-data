import Koa from 'koa';
import apiRouter from './apis/index.mjs';

const app = new Koa();

app.use(apiRouter.routes())
  .use(apiRouter.allowedMethods());

app.listen(8080, () => {
  console.log('server started, listening at port 8080');
});