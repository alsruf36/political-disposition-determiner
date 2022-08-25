import torch
from torch import nn
import torch.nn.functional as F
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import datetime as pydatetime
import gluonnlp as nlp
import numpy as np
import tqdm
import dill
import requests
import json
import ray
from ray import serve
import string
import os
import random
import starlette
from starlette.requests import Request
import time
import io
import argparse
import json

#kobert
from kobert_tokenizer import KoBERTTokenizer
from transformers import BertModel

#transformers
from transformers import AdamW
from transformers.optimization import get_cosine_schedule_with_warmup
from sklearn.model_selection import train_test_split

from minio import Minio

import string
import random

def random_id(length):
    string_pool = string.ascii_uppercase + string.digits
    result = ""

    for i in range(length) :
        result += random.choice(string_pool)
    
    return result

# Setting parameters
max_len = 64
batch_size = 64
warmup_ratio = 0.1
num_epochs = 10
max_grad_norm = 1
log_interval = 200
learning_rate =  5e-5

# BERT 모델에 들어가기 위한 dataset을 만들어주는 클래스
class BERTDataset(Dataset):
    def __init__(self, dataset, sent_idx, label_idx, bert_tokenizer, vocab,
                max_len, pad, pair):
   
        transform = nlp.data.BERTSentenceTransform(
            bert_tokenizer, max_seq_length=max_len, vocab=vocab, pad=pad, pair=pair)
        
        self.sentences = [transform([i[sent_idx]]) for i in dataset]
        self.labels = [np.int32(i[label_idx]) for i in dataset]

    def __getitem__(self, i):
        return (self.sentences[i] + (self.labels[i], ))
         
    def __len__(self):
        return (len(self.labels))

class BERTClassifier(nn.Module):
    def __init__(self,
                 bert,
                 hidden_size = 768,
                 num_classes=2,   ##클래스 수 조정##
                 dr_rate=None,
                 params=None):
        super(BERTClassifier, self).__init__()
        self.bert = bert
        self.dr_rate = dr_rate
                 
        self.classifier = nn.Linear(hidden_size , num_classes)
        if dr_rate:
            self.dropout = nn.Dropout(p=dr_rate)
    
    def gen_attention_mask(self, token_ids, valid_length):
        attention_mask = torch.zeros_like(token_ids)
        for i, v in enumerate(valid_length):
            attention_mask[i][:v] = 1
        return attention_mask.float()

    def forward(self, token_ids, valid_length, segment_ids):
        attention_mask = self.gen_attention_mask(token_ids, valid_length)
        
        _, pooler = self.bert(input_ids = token_ids, token_type_ids = segment_ids.long(), attention_mask = attention_mask.float().to(token_ids.device))
        if self.dr_rate:
            out = self.dropout(pooler)
        return self.classifier(out)

@serve.deployment(ray_actor_options={"num_gpus": 0.1})
class AnalyzerGPU:
    def __init__(self, model_ref, vocab_ref, tokenizer_ref):
        print("Initialize 함수에서 " + str(torch.cuda.is_available()))
        self.mid = random_id(12) # model ID 설정
        self.pid = os.getpid() # Get the pid on which this deployment is running on

        start = time.time()
        self.model = ray.get(model_ref)
        print(str(time.time() - start) + "초 만에 model을 불러왔습니다.")

        print("tokenizer을 불러오는 중입니다.")
        self.vocab = ray.get(vocab_ref)
        tokenizer = KoBERTTokenizer.from_pretrained(model_path)
        self.tok = tokenizer.tokenize

        self.device = torch.device("cuda:0")
        self.model.eval()
    
    def __call__(self, api_request) -> str:
        # Request came via an HTTP
        if isinstance(api_request, starlette.requests.Request):
            predict_sentence = api_request.query_params['sentence']
        else:
            # Request came via a ServerHandle API method call.
            predict_sentence = api_request

        data = [predict_sentence, '0']
        dataset_another = [data]

        another_test = BERTDataset(dataset_another, 0, 1, self.tok, self.vocab, max_len, True, False)
        test_dataloader = torch.utils.data.DataLoader(another_test, batch_size=batch_size, num_workers=5)

        for batch_id, (token_ids, valid_length, segment_ids, label) in enumerate(test_dataloader):
            token_ids = token_ids.long().to(self.device)
            segment_ids = segment_ids.long().to(self.device)

            valid_length= valid_length
            label = label.long().to(self.device)

            out = self.model(token_ids, valid_length, segment_ids)


            test_eval=[]
            for i in out:
                logits=i
                logits = logits.detach().cpu().numpy()

                if np.argmax(logits) == 0:
                    test_eval.append(0)
                elif np.argmax(logits) == 1:
                    test_eval.append(1)

            print("반환 | {}".format(test_eval[0]))
            return f"(pid: {self.pid}); sentence: {predict_sentence}; prediction: {test_eval[0]}; {torch.cuda.is_available()}"   

@serve.deployment
class AnalyzerCPU:
    def __init__(self, model_ref, vocab_ref, model_path):
        print("Initialize 함수에서 " + str(torch.cuda.is_available()))
        self.mid = random_id(12) # model ID 설정
        self.pid = os.getpid() # Get the pid on which this deployment is running on

        start = time.time()
        self.model = ray.get(model_ref)
        print(str(time.time() - start) + "초 만에 model을 불러왔습니다.")

        print("tokenizer을 불러오는 중입니다.")
        self.vocab = ray.get(vocab_ref)
        tokenizer = KoBERTTokenizer.from_pretrained(model_path)
        self.tok = tokenizer.tokenize

        self.device = torch.device('cpu')
        self.model.eval()
    
    def __call__(self, api_request) -> str:
        start = time.time()
        # Request came via an HTTP
        if isinstance(api_request, starlette.requests.Request):
            predict_sentence = api_request.query_params['sentence']
        else:
            # Request came via a ServerHandle API method call.
            predict_sentence = api_request

        data = [predict_sentence, '0']
        dataset_another = [data]
        print(str(time.time() - start) + "초 만에 요청을 변환했습니다.")

        start = time.time()
        another_test = BERTDataset(dataset_another, 0, 1, self.tok, self.vocab, max_len, True, False)
        test_dataloader = torch.utils.data.DataLoader(another_test, batch_size=batch_size, num_workers=5)
        print(str(time.time() - start) + "초 만에 데이터를 변환했습니다.")

        for batch_id, (token_ids, valid_length, segment_ids, label) in enumerate(test_dataloader):
            start = time.time()
            token_ids = token_ids.long().to(self.device)
            segment_ids = segment_ids.long().to(self.device)

            valid_length= valid_length
            label = label.long().to(self.device)

            out = self.model(token_ids, valid_length, segment_ids)


            test_eval=[]
            for i in out:
                logits=i
                logits = logits.detach().cpu().numpy()

                if np.argmax(logits) == 0:
                    test_eval.append(0)
                elif np.argmax(logits) == 1:
                    test_eval.append(1)
            
            print(str(time.time() - start) + "초 만에 추정하였습니다.")
            print("추정값 | {}".format(test_eval))

        return {
            "pid": self.pid,
            "sentence": predict_sentence,
            "prediction": test_eval
        }

def get_kobert_model(model_path, vocab_file, ctx="cpu"):
    bertmodel = BertModel.from_pretrained(model_path, return_dict=False)
    device = torch.device(ctx)
    bertmodel.to(device)
    bertmodel.eval()
    vocab_b_obj = nlp.vocab.BERTVocab.from_sentencepiece(vocab_file,
                                                         padding_token='[PAD]')
    return bertmodel, vocab_b_obj

@ray.remote
def get_kobert(model_path, ctx="cpu"):
    tokenizer = KoBERTTokenizer.from_pretrained(model_path)
    bertmodel, vocab = get_kobert_model(model_path, tokenizer.vocab_file)
    bertmodel_ref = ray.put(bertmodel)
    vocab_ref = ray.put(vocab)

    return bertmodel_ref, vocab_ref

@ray.remote
def load_model(name, end_point, port, access_key, secret_key):
    print("모델을 로드합니다.")

    minioClient = Minio(f'{end_point}:{port}',
                    access_key=access_key,
                    secret_key=secret_key,
                    secure=False)

    try:
        response = minioClient.get_object('models', name.split('"')[1])
        raw = response.data
        buffer = io.BytesIO()
        buffer.write(raw)
        buffer_len = buffer.tell()
        buffer.seek(0)
        print("모델의 크기 | " + str(buffer_len))

    except Exception as e:
        raise e

    buffer_ref = ray.put(buffer)

    return buffer_ref

@ray.remote
def put_model_cpu(buffer, bertmodel):
    device = torch.device('cpu')

    start = time.time()
    model = BERTClassifier(bertmodel,  dr_rate=0.5).to(device)
    model.load_state_dict(torch.load(buffer, map_location=device))
    print(str(time.time() - start) + "초 만에 CPU model을 load하였습니다.")

    start = time.time()
    model_ref = ray.put(model)
    print(str(time.time() - start) + "초 만에 CPU model을 put하였습니다.")

    return model_ref

if __name__=='__main__':
    parser = argparse.ArgumentParser(description='bertModeler')
    parser.add_argument('-r', '--ray_address', default='', type=str)
    parser.add_argument('-x', '--ray_port', default='10001', type=int)
    parser.add_argument('-f', '--file_name', default='', type=str)
    parser.add_argument('-i', '--s3_end_point', default='0.0.0.0', type=str)
    parser.add_argument('-p', '--s3_port', default='9000', type=int)
    parser.add_argument('-a', '--s3_access_key', default='admin', type=str)
    parser.add_argument('-s', '--s3_secret_key', default='pass', type=str)
    parser.add_argument('-d', '--api_name', default='analyze', type=str)
    args = parser.parse_args()

    print("ray cluster에 연결합니다.")
    ray.init(f"ray://{args.ray_address}:{args.ray_port}")
    serve.start(detached=True, http_options={"host": "0.0.0.0"})
    
    model_path = "skt/kobert-base-v1"
    bertmodel_ref, vocab_ref = ray.get(get_kobert.remote(model_path))
    buffer_ref = ray.get(load_model.remote(args.file_name, args.s3_end_point, args.s3_port, args.s3_access_key, args.s3_secret_key))
    model_cpu_ref = ray.get(put_model_cpu.remote(buffer_ref, bertmodel_ref))
    
    AnalyzerCPU.options(name=args.api_name, num_replicas=1).deploy(model_cpu_ref, vocab_ref, model_path)

    serve_list = serve.list_deployments()

    with open("/airflow/xcom/return.json", "w") as file:
        json.dump(serve_list, file)