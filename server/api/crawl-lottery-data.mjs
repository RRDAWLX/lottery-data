/**
 * 爬取彩票数据并触发增量训练。
 *
 * 流程: 爬取 → 入库 → 异步触发 llm-prediction 训练（通过 HTTP POST）
 */

import axios from 'axios';
import * as cheerio from 'cheerio';
import { insert } from '../db/index.mjs';
import { triggerTraining } from './prediction.mjs';

export default async function (ctx) {
  let superLottoData = await crawlSuperLotto();
  await insert('superLotto', superLottoData);
  let unionLottoData = await crawlUnionLotto();
  await insert('unionLotto', unionLottoData);

  // 异步触发训练，不阻塞爬取响应
  triggerTraining('unionLotto').catch(err => console.error('unionLotto training error:', err.message));
  triggerTraining('superLotto').catch(err => console.error('superLotto training error:', err.message));

  ctx.body = {
    code: 0,
    msg: 'success',
  };
};

/** 爬取大乐透数据 (5普通号 + 2特别号) */
async function crawlSuperLotto () {
  let { data } = await axios.get('http://datachart.500.com/dlt/history/newinc/history.php?limit=100&sort=1')
  let $ = cheerio.load(data, null, false)
  let rows = $('#tdata tr')
  let records = []

  rows.each(function () {
    let record = {}
    let tds = $(this).children('td')
    record.issue = +tds.eq(0).text()
    record.numbers = [
      +tds.eq(1).text(),
      +tds.eq(2).text(),
      +tds.eq(3).text(),
      +tds.eq(4).text(),
      +tds.eq(5).text(),
      +tds.eq(6).text(),
      +tds.eq(7).text(),
    ]
    record.date = tds.eq(14).text()
    records.push(record)
  })

  return records;
}

/** 爬取双色球数据 (6普通号 + 1特别号) */
async function crawlUnionLotto() {
  let { data } = await axios.get('http://datachart.500.com/ssq/history/newinc/history.php?limit=100&sort=1')
  let $ = cheerio.load(data, null, false)
  let rows = $('#tdata tr')
  let records = []

  rows.each(function () {
    let record = {}
    let tds = $(this).children('td')
    record.issue = +tds.eq(0).text()
    record.numbers = [
      +tds.eq(1).text(),
      +tds.eq(2).text(),
      +tds.eq(3).text(),
      +tds.eq(4).text(),
      +tds.eq(5).text(),
      +tds.eq(6).text(),
      +tds.eq(7).text(),
    ]
    record.date = tds.eq(15).text()
    records.push(record);
  })

  return records;
}