const collectOptions = require('./service/collectOptions')

module.exports.optionsCollectEvent = (event, context, callback) => {
    
    const options = event["Records"].map(v => JSON.parse(v.body)).flat().map(v => collectOptions.map_options(v.ticker, v.options, v.datetime))
    console.log(JSON.stringify(options))
    callback(null, null);
}