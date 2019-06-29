const csv = require('csvtojson');
const request = require('request');
const URL = 'https://portal.mvp.bafin.de/database/DealingsInfo/sucheForm.do?meldepflichtigerName=&zeitraum=0&d-4000784-e=1&emittentButton=Suche+Emittent&emittentName=&zeitraumVon=&emittentIsin=&6578706f7274=1&locale=en_GB&zeitraumBis=';
const converter = require('./converter');
const s3Service = require('./s3Service');

exports.DE = async () => {
    let newTradesPromise = converter.convertKeysForS3Json(csv({ delimiter: ';' }).fromStream(request.get(URL)));
    let urlValidPromise = converter.isScvValidUrl(URL);
    let tradesPromise = s3Service.select(process.env.select_bucket).getLastTrades(1000000000);
    let isUrlValid = await urlValidPromise;
    let trades = await tradesPromise;
    console.log("URL is valid", isUrlValid);
    if(!isUrlValid){
        console.error(`trades URL for DE is invalid ${URL}`);
        return trades
    }
    trades = JSON.parse(trades);
    console.log(`got ${trades.length} trades from S3`);
    let newTrades = await newTradesPromise;
    console.log(`got ${newTrades.length} new trades from BaFin`);
    return trades.concat(converter.getDiffFromTwoArr(trades, newTrades))
};
