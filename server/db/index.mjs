import url from 'url';
import path from 'path';
import fse from 'fs-extra';

const __filename = url.fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const dbPath = path.join(__dirname, 'db.json');
let db = null;
let issueSets = null;

async function initDB () {
  if (!db) {
    const rawDB = await fse.readJSON(dbPath);

    db = Object.entries(rawDB).reduce((map, [lotteryType, dataArr]) => {
      map[lotteryType] = dataArr.map(item => JSON.parse(item));
      return map;
    }, {});
    
    issueSets = Object.entries(db)
      .reduce((map, [lotteryType, dataArr]) => {
        map[lotteryType] = new Set(dataArr.map(item => item.issue));
        return map;
      }, {});
  }
}

export async function query (lotteryType) {
  await initDB();
  return JSON.parse(JSON.stringify(db[lotteryType] ?? []));
};

export async function insert(lotteryType, dataArr) {
  await initDB();

  if (!db[lotteryType]) {
    throw new Error(`invalid lotteryType: ${lotteryType}`);
  }

  let dbArr = db[lotteryType];
  let issueSet = issueSets[lotteryType];
  
  for (let item of dataArr) {
    if (!issueSet.has(item.issue)) {
      dbArr.push(item);
      issueSet.add(item.issue);
    }
  }

  dbArr.sort((a, b) => a.issue - b.issue);

  const rawDB = {};
  Object.entries(db).forEach(([lotteryType, dataArr]) => {
    rawDB[lotteryType] = dataArr.map(item => JSON.stringify(item));
  });

  await fse.writeJSON(dbPath, rawDB, { spaces: 2 });
};