import requests
import json
from kafka import KafkaProducer
from transformers import AutoTokenizer,AutoModelForSequenceClassification
from scipy.special import softmax



# This is a Tweets stream collector based on the new Twitter API V2 specification
# for Tweets Search from https://developer.twitter.com,
# and examples from https://github.com/twitterdev/Twitter-API-v2-sample-code.
# RoBERTa is an NLP model,from Facebook, based on the BERT language
# The University of Cardiff RoBERTa model used in this program was pretrained
# in sentiment analysis of Tweet texts and was used to enrich the
# crypto tweet events adding sentiment analysts


#Global variables
roberta="cardiffnlp/twitter-roberta-base-sentiment"
model=AutoModelForSequenceClassification.from_pretrained(roberta)
labels=['NEGATIVE','POSITIVE','NEUTRAL']
direction=['-1','1',0]
tokenizer=AutoTokenizer.from_pretrained(roberta)
bearer_token = "AAAAAAAAAAAAAAAAAAAAALu3jwEAAAAAD6U%2BRnteWX5dTVcZUvbRrjah3Rg%3DOZZ5bfhl9frFBP5LbOSqse0ibTkWQnA4sBq9aAqCyz1MYnBRW4"
producer = KafkaProducer(bootstrap_servers='localhost:9092')

def bearer_oauth(r):
    """
    Method required by bearer token authentication.
    """

    r.headers["Authorization"] = f"Bearer {bearer_token}"
    r.headers["User-Agent"] = "v2FilteredStreamPython"
    return r


def get_rules():
    response = requests.get(
        "https://api.twitter.com/2/tweets/search/stream/rules", auth=bearer_oauth
    )
    if response.status_code != 200:
        raise Exception(
            "Cannot get rules (HTTP {}): {}".format(response.status_code, response.text)
        )
    print(json.dumps(response.json()))
    return response.json()


def delete_all_rules(rules):
    if rules is None or "data" not in rules:
        return None

    ids = list(map(lambda rule: rule["id"], rules["data"]))
    payload = {"delete": {"ids": ids}}
    response = requests.post(
        "https://api.twitter.com/2/tweets/search/stream/rules",
        auth=bearer_oauth,
        json=payload
    )
    if response.status_code != 200:
        raise Exception(
            "Cannot delete rules (HTTP {}): {}".format(
                response.status_code, response.text
            )
        )
    print(json.dumps(response.json()))


def set_rules(delete):
    # Top 20 crypto currencies
    sample_rules = [
        {"value": "#BTC", "tag": "Bitcoin"},
        {"value": "#ETH", "tag": "Etherium"},
        {"value": "#USDT", "tag": "Tether"},
        {"value": "#BNB", "tag": "BNB"},
        {"value": "#USDC", "tag": "USDC Coin"},
        {"value": "#BUSD", "tag": "Binance"},
        {"value": "#XRP", "tag": "#XRP"},
        {"value": "#DOGE", "tag": "Dogecoin"},
        {"value": "#ADA", "tag": "Cardano"},
        {"value": "#MATIC", "tag": "Polygon"},
        {"value": "#DOT", "tag": "Polkadot"},
        {"value": "#DAI", "tag": "Dai"},
        {"value": "#LTC", "tag": "Litecoin"},
        {"value": "#SHIB", "tag": "Shiba Inu"},
        {"value": "#TRX", "tag": "TRON"},
        {"value": "#SOL", "tag": "Solana"},
        {"value": "#UNI", "tag": "Uniswap"},
        {"value": "#LEC", "tag": "UNUS SED LEO"},
        {"value": "#AVAX", "tag": "Avalanche"},
        {"value": "#LINK", "tag": "Chainlink"},
        {"value": "#FTX", "tag": "#FTX"}
    ]
    payload = {"add": sample_rules}
    response = requests.post(
        "https://api.twitter.com/2/tweets/search/stream/rules",
        auth=bearer_oauth,
        json=payload,
    )
    if response.status_code != 201:
        raise Exception(
            "Cannot add rules (HTTP {}): {}".format(response.status_code, response.text)
        )
    print(json.dumps(response.json()))


def get_stream(set):
    response = requests.get(
        "https://api.twitter.com/2/tweets/search/stream", auth=bearer_oauth, stream=True,
    )
    print(response.status_code)
    if response.status_code != 200:
        raise Exception(
            "Cannot get stream (HTTP {}): {}".format(
                response.status_code, response.text
            )
        )
    for response_line in response.iter_lines():
        if response_line:
            json_response = json.loads(response_line)
            text=json_response['data']['text']

            #Preprocess text
            text_words=[]
            for word in text.split(' '):
                if word.startswith('@') and len(word)>1:
                    word = '@user'
                elif word.startswith('http') and len(word) > 1:
                    word = "http"
                text_words.append(word)
            text_preprocessed = " ".join(text_words)

            #Sentiment Analysis
            encoded_text = tokenizer(text_preprocessed, return_tensors='pt')
            scores = softmax(model(**encoded_text)[0][0].detach().numpy())
            max=0
            for i in range(len(scores)):
                if abs(scores[i])>=abs(max):
                    max = scores[i]
                    sentiment = labels[i]
            json_response['sentiment'] = sentiment
            json_response['sentiment_direction'] = direction[labels.index(sentiment)]
            print(json.dumps(json_response, indent=4, sort_keys=True))

            #Sending to Kafka
            producer.send('crypto', value=json.dumps(json_response).encode('utf-8'))

def main():
    #Getting current filter rules
    rules = get_rules()
    #Deleting current filter rules
    delete = delete_all_rules(rules)
    #Setting new filter rules
    set = set_rules(delete)
    #Getting the stream and sentiment analysis
    get_stream(set)


if __name__ == "__main__":
    main()