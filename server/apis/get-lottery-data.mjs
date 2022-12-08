import { query } from '../../db/index.mjs';

export default async function (ctx) {
  let  { lotteryType } = ctx.params;
  let data = await query(lotteryType);
  ctx.body = {
    code: 0,
    msg: 'success',
    data,
  };
};