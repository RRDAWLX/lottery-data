import Router from '@koa/router';
import getLotteryData from './get-lottery-data.mjs';
import crawlLotteryData from './crawl-lottery-data.mjs';

const router = new Router({
  prefix: '/api',
});
router.get('/getLotteryData/:lotteryType', getLotteryData);
router.post('/crawlLotteryData', crawlLotteryData);

export default router;