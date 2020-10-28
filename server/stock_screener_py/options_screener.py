import os
import boto3
import requests
import json
import random
import asyncio
import nest_asyncio
import logging
import aiohttp
import datetime
import time
from time import sleep
from datetime import timezone
from aiohttp import ClientSession

client = boto3.client('lambda')
fh = boto3.client('firehose')

CHUNK_SIZE = 3
# TODO use as env variable
QUEUE_NAME = "https://sqs.eu-central-1.amazonaws.com/763862102163/options-collect-sqs-dev"
nest_asyncio.apply()
loop = asyncio.get_event_loop()


def get_lambda_json_response(lmbd):
    response = client.invoke(
        FunctionName=lmbd,
        InvocationType='RequestResponse'
    )
    payload = response["Payload"].read()
    json_string = json.loads(payload)['body']
    return json.loads(json_string)


class Options_screener:
    def __init__(self):
        self.proxies = self.get_proxies()
        self.tickers = self.get_tickers()
        self.options = []
        self.option_json = []
        self.optionsDS = os.environ.get('optionsDeliveryStream')

    def get_url(self, ticker):
        return "https://www.optionsprofitcalculator.com/ajax/getOptions?stock={}&reqId=1".format(ticker)

    def get_proxies(self):
        proxies = get_lambda_json_response('insider-dev-get_all_proxies')
        return list(map(lambda prx: "http://{}:{}".format(prx['host'], prx['port']), proxies))

    def get_tickers(self):
        companies = get_lambda_json_response('insider-dev-optionalStocks')
        return list(map(lambda com: com['Ticker'], companies))

    async def getOptions(self):
        # for ticker in self.tickers:
        #    self.addOption(ticker)
        print("delivery_stream_name: {}".format(self.optionsDS))
        while len(self.tickers) > 0:
            print("Running get Options")
            input_coroutines = list(map(lambda ticker: asyncio.ensure_future(
                self.addOption(ticker)), self.tickers))
            await asyncio.gather(*input_coroutines, return_exceptions=False)
            records = list(
                map(lambda el: {'Data': el.encode()}, self.option_json))
            for record in chunks(records, 500):
                response = fh.put_record_batch(
                    DeliveryStreamName=self.optionsDS,
                    Records=record
                )
                sleep(1.5)
                if response['FailedPutCount'] > 0:
                    print(response)
            self.option_json = []

            #ch = chunks(self.options, CHUNK_SIZE)
            # ch = [self.options[i:i + CHUNK_SIZE]
            #      for i in range(0, len(self.options), CHUNK_SIZE)]
            # list(map(lambda el: sqs.send_message(
            #    QueueUrl=QUEUE_NAME, MessageBody=json.dumps(el)), ch))
            ##self.options = []
        return self.options

    def convertOptionsAndpush(self, ticker, options):
        self.tickers.remove(ticker)
        print("saving options for {}, proxies size: {}, tickers size: {}".format(
            ticker, len(self.proxies), len(self.tickers)))
        # obj = {
        #    "ticker": ticker,
        #    "datetime": datetime.datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f"),
        #    "options": options
        # }
        # self.options.append(obj)
        #print("added options for {}".format(ticker))
        for exp in options['options']:
            for t in options['options'][exp]:
                for strike in options['options'][exp][t]:
                    option = {
                        "ticker": ticker,
                        "strike": float(strike),
                        "ask": float(options['options'][exp][t][strike]["a"]),
                        "bid": float(options['options'][exp][t][strike]["b"]),
                        "mid": float(options['options'][exp][t][strike]["l"]),
                        "volume": float(options['options'][exp][t][strike]["v"]),
                        "datetime": datetime.datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f"),
                        "exp": "{} 23:59:59.000000".format(exp),
                        "type": 'CALL' if t == 'c' else 'PUT'
                    }
                    option_json = json.dumps(option)
                    #response = fh.put_record(DeliveryStreamName='options-stream-dev', Record={'Data': option_json.encode()})
                    # while fh.put_record(DeliveryStreamName='options-stream-dev', Record={'Data': option_json.encode()})['ResponseMetadata']['HTTPStatusCode'] != 200:
                    #    print("trying to save {}".format(option_json))
                    self.option_json.append(option_json)
                    # print(response)
        # self.options.append(options)

    async def addOption(self, ticker):
        proxy_index = random.randint(0, len(self.proxies) - 1)
        #proxy = {"http": self.proxies[proxy_index], "https": self.proxies[proxy_index]}
        proxy = self.proxies[proxy_index]
        timeout = aiohttp.ClientTimeout(total=45)
        # response = sqs.send_message(
        #    QueueUrl=QUEUE_NAME, MessageBody=json.dumps({"text": "bla bla"}))
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'}
        try:
            #timeout = aiohttp.ClientTimeout(total=2)
            async with ClientSession(timeout=timeout) as session:
                async with session.get(self.get_url(ticker), headers=headers, proxy=proxy) as response:
                    text = await response.read()
                    content = json.loads(text)
                    self.convertOptionsAndpush(ticker, content)
        except:
            try:
                # self.proxies.remove(proxy)
                logging.debug("removed proxy: {}. Count: {}".format(
                    proxy, len(self.proxies)))
            except:
                logging.debug("{} is already removed".format(proxy))
            self.addOption(ticker)


def chunks(lst, n):
    return [lst[i:i + n] for i in range(0, len(lst), n)]

def uploadOptions(event, context):
    print("start")
    if datetime.datetime.today().weekday() < 5:
        loop.run_until_complete(Options_screener().getOptions())
    return '''
    {
        "status": "Successfully uploaded options"
    }
    '''


if __name__ == "__main__":
    uploadOptions("", "")
