// 超级大乐透
import axios from 'axios'
import * as cheerio from 'cheerio'
import fse from 'fs-extra'

export async function grasp () {
  // 获取数据
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

  // 存储数据
  let db = fse.readJsonSync('./db.json')
  let issueSet = db.superLotto.map(item => item.issue)

  for (let record of records) {
    if (!issueSet.includes(record.issue)) {
      db.superLotto.push(record)
    }
  }

  fse.writeJSONSync('./db.json', db, {
    spaces: 2,
  })

  // 统计数据
  records = db.superLotto
  let arr1 = (new Array(36)).fill(0)
  let arr2 = (new Array(13)).fill(0)

  for (let { numbers } of records) {
    for (let i = 0; i < 5; i++) {
      arr1[numbers[i]]++
    }

    arr2[numbers[5]]++
    arr2[numbers[6]]++
  }

  let base1 = 5 * records.length
  let base2 = 2 * records.length

  arr1 = arr1
    .map((num, i) => ([i, num / base1]))
    .slice(1)
  arr1.sort((a, b) => a[1] - b[1]);
  
  arr2 = arr2
    .map((num, i) => ([i, num / base2]))
    .slice(1)
  arr2.sort((a, b) => a[1] - b[1]);

  console.log('大乐透：')
  console.log('前区: ')
  arr1.forEach(([n, p]) => console.log(`${n.toString().padStart(2, ' ')}   ${(p * 100).toFixed(2)}%`))
  console.log('后区: ')
  arr2.forEach(([n, p]) => console.log(`${n.toString().padStart(2, ' ')}   ${(p * 100).toFixed(2)}%`))

  console.log('推荐号码：')

  // 最大概率组合
  let part1 = arr1.slice(-5).map(item => item[0]).sort((a, b) => a - b)
  let part2 = arr2.slice(-2).map(item => item[0]).sort((a, b) => a - b)
  console.log(`最大概率组合：${part1.join()},${part2.join()}`)

  // 最小概率组合
  part1 = arr1.slice(0, 5).map(item => item[0]).sort((a, b) => a - b)
  part2 = arr2.slice(0, 2).map(item => item[0]).sort((a, b) => a - b)
  console.log(`最小概率组合：${part1.join()},${part2.join()}`)
}