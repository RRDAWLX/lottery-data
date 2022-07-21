// 福彩双色球
import axios from 'axios'
import * as cheerio from 'cheerio'
import fse from 'fs-extra'

export async function grasp() {
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

  let db = fse.readJsonSync('./db.json')
  let issueSet = db.unionLotto.map(item => item.issue)

  for (let record of records) {
    if (!issueSet.includes(record.issue)) {
      db.unionLotto.push(record)
    }
  }

  fse.writeJSONSync('./db.json', db, {
    spaces: 2,
  })

  // 统计数据
  records = db.unionLotto
  let arr1 = (new Array(34)).fill(0)
  let arr2 = (new Array(17)).fill(0)

  for (let { numbers } of records) {
    for (let i = 0; i < 6; i++) {
      arr1[numbers[i]]++
    }

    arr2[numbers[6]]++
  }

  let base1 = 6 * records.length
  let base2 = records.length

  arr1 = arr1
    .map((num, i) => ([i, num / base1]))
    .slice(1)
  arr1.sort((a, b) => a[1] - b[1]);

  arr2 = arr2
    .map((num, i) => ([i, num / base2]))
    .slice(1)
  arr2.sort((a, b) => a[1] - b[1]);

  console.log('双色球：')
  console.log('红球: ')
  arr1.forEach(([n, p]) => console.log(`${n.toString().padStart(2, ' ')}   ${(p * 100).toFixed(2)}%`))
  console.log('蓝球: ')
  arr2.forEach(([n, p]) => console.log(`${n.toString().padStart(2, ' ')}   ${(p * 100).toFixed(2)}%`))

  console.log('推荐号码：')

  // 最大概率组合
  let part1 = arr1.slice(-6).map(item => item[0]).sort((a, b) => a - b)
  console.log(`最大概率组合：${part1.join()},${arr2[15][0]}`)

  // 最小概率组合
  part1 = arr1.slice(0, 5).map(item => item[0]).sort((a, b) => a - b)
  console.log(`最小概率组合：${part1.join()},${arr2[0][0]}`)
}
