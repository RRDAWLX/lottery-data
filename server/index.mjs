import Koa from 'koa';
import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import apiRouter from './api/index.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const config = JSON.parse(readFileSync(join(__dirname, '..', 'config.json'), 'utf-8'));

const app = new Koa();

app.use(apiRouter.routes())
  .use(apiRouter.allowedMethods());

const port = config.server.port;
app.listen(port, () => {
  console.log(`server started, listening at port ${port}`);
});