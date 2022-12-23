import axios from 'axios';
import * as cheerio from 'cheerio';
import { insert } from '../db/index.mjs';

export default async function (ctx) {
  let superLottoData = await crawlSuperLotto();
  await insert('superLotto', superLottoData);
  let unionLottoData = await crawlUnionLotto();
  await insert('unionLotto', unionLottoData);
  ctx.body = {
    code: 0,
    msg: 'success',
  };
};

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