import Koa from 'koa';
import apiRouter from './apis/index.mjs';

const app = new Koa();

app.use(apiRouter.routes())
  .use(apiRouter.allowedMethods());

const port = 5000;
app.listen(port, () => {
  console.log(`server started, listening at port ${port}`);
});