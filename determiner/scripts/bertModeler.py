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

from utils import random_id

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

#데이터셋 가져오기
@ray.remote
def get_raw_data(count, minlike, minlength, mintimestamp):
    print("[단계 1] | API를 통해 데이터를 불러옵니다.")

    URL = "https://project.kshs.dev/comment" #댓글 요청을 위한 URL

    #파라미터에서 count는 꼭 포함해야 하며, count 외에는 필요한 조건만 포함해야한다.
    params = {
        "count": count,            #불러올 댓글 개수 
        #"tend": "pro",             #정치 성향 (con : 보수 | pro : 진보)
        "minlike": minlike,              #댓글의 최소 공감 개수
        "minlength": minlength,            #댓글의 최소 길이
        "mintimestamp": mintimestamp, #댓글의 최소 날짜 (Unix Time 형식)
        #"level": 3                 #언론사의 레벨 (0부터 3까지 이며 그 숫자 이하 레벨의 모든 언론사를 대상으로 한다. 숫자가 작을수록 극좌/극우에 가깝다.)
    }

    try:
        response = requests.get(URL, params=params) #requests 모듈을 통해 API에 요청
        comments = json.loads(response.text) #로드된 JSON 텍스트를 배열로 변경
        contents = [[x['normalize'][1]['text'], x['calculate']] for x in comments] #comments 중 원하는 항목만 추출

        cons = [x for x in contents if x[1] == 0] #보수 댓글 리스트
        pros = [x for x in contents if x[1] == 1] #진보 댓글 리스트

    except Exception as e:
        print(e)
        print("API를 통해 데이터를 불러오는 중에 오류가 발생하였습니다.")

    print("{}개의 데이터를 성공적으로 불러왔습니다. (보수 {}개 | 진보 {}개)".format(len(contents), len(cons), len(pros)))
    return ray.put(cons), ray.put(pros)

#train & test 데이터로 나누기
@ray.remote(num_gpus=1)
def split_train_test_data(cons, pros):
    print("[단계 2] | 데이터를 나눕니다.")
    Cdataset_train, Cdataset_test = train_test_split(cons, test_size=0.25, random_state=0)
    Pdataset_train, Pdataset_test = train_test_split(pros, test_size=0.25, random_state=0)
    dataset_train = Cdataset_train + Pdataset_train
    dataset_test = Cdataset_test + Pdataset_test

    print("{}개의 Train 데이터와 {}개의 Test 데이터가 생성되었습니다.".format(len(dataset_train), len(dataset_test)))
    return ray.put(dataset_train), ray.put(dataset_test)

#토큰화
@ray.remote(num_gpus=1)
def tokenize(dataset_train, dataset_test, max_len, batch_size, vocab, model_path):
    print("[단계 3] | Tokenize합니다.")
    tokenizer = KoBERTTokenizer.from_pretrained(model_path)
    tok = tokenizer.tokenize
    data_train = BERTDataset(dataset_train, 0, 1, tok, vocab, max_len, True, False)
    data_test = BERTDataset(dataset_test, 0, 1, tok, vocab, max_len, True, False)
    #print(data_train[0])
    train_dataloader = torch.utils.data.DataLoader(data_train, batch_size=batch_size, num_workers=5)
    test_dataloader = torch.utils.data.DataLoader(data_test, batch_size=batch_size, num_workers=5)

    return ray.put(train_dataloader), ray.put(test_dataloader)

def calc_accuracy(X, Y):
    max_vals, max_indices = torch.max(X, 1)
    train_acc = (max_indices == Y).sum().data.cpu().numpy()/max_indices.size()[0]
    return train_acc

@ray.remote(num_gpus=1)
def train(train_dataloader, test_dataloader, warmup_ratio, num_epochs, max_grad_norm, log_interval, learning_rate, bertmodel,
        s3_end_point, s3_port, s3_access_key, s3_secret_key, ctx="cpu"):
    print("[단계 4] | 모델을 학습시킵니다.")
    
    device = torch.device(ctx)
    model = BERTClassifier(bertmodel, dr_rate=0.5).to(device)

    no_decay = ['bias', 'LayerNorm.weight']
    optimizer_grouped_parameters = [
        {'params': [p for n, p in model.named_parameters() if not any(nd in n for nd in no_decay)], 'weight_decay': 0.01},
        {'params': [p for n, p in model.named_parameters() if any(nd in n for nd in no_decay)], 'weight_decay': 0.0}
    ]

    optimizer = AdamW(optimizer_grouped_parameters, lr=learning_rate)
    loss_fn = nn.CrossEntropyLoss()

    t_total = len(train_dataloader) * num_epochs
    warmup_step = int(t_total * warmup_ratio)
    scheduler = get_cosine_schedule_with_warmup(optimizer, num_warmup_steps=warmup_step, num_training_steps=t_total)
    train_dataloader

    model_list = []
    save_ref_list = []
    for e in range(num_epochs):
        train_acc = 0.0
        test_acc = 0.0
        model.train()
        for batch_id, (token_ids, valid_length, segment_ids, label) in enumerate(tqdm.tqdm(train_dataloader)):
            optimizer.zero_grad()
            token_ids = token_ids.long().to(device)
            segment_ids = segment_ids.long().to(device)
            valid_length = valid_length
            label = label.long().to(device)
            out = model(token_ids, valid_length, segment_ids)
            loss = loss_fn(out, label)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_grad_norm)
            optimizer.step()
            scheduler.step()
            train_acc += calc_accuracy(out, label)
            if batch_id % log_interval == 0:
                print("epoch {} batch id {} loss {} train acc {}".format(e+1, batch_id+1, loss.data.cpu().numpy(), train_acc / (batch_id+1)))
        print("epoch {} train acc {}".format(e+1, train_acc / (batch_id+1)))
        
        model.eval()
        for batch_id, (token_ids, valid_length, segment_ids, label) in enumerate(tqdm.tqdm(test_dataloader)):
            token_ids = token_ids.long().to(device)
            segment_ids = segment_ids.long().to(device)
            valid_length= valid_length
            label = label.long().to(device)
            out = model(token_ids, valid_length, segment_ids)
            test_acc += calc_accuracy(out, label)
        print("epoch {} test acc {}".format(e+1, test_acc / (batch_id+1)))

        timestamp = int(pydatetime.datetime.now().timestamp())
        model_info = {
            "epoch": e+1,
            "train_acc": train_acc / (batch_id+1),
            "test_acc": test_acc / (batch_id+1),
            "timestamp": timestamp,
            "file_name": f'kobert/model-{timestamp}.pt'
        }

        buffer = io.BytesIO()
        torch.save(model.state_dict(), buffer)

        save_ref_list.append(save_model.remote(buffer, s3_end_point, s3_port, s3_access_key, s3_secret_key, model_info))
        model_list.append(model_info)

    print("모델을 저장하는 중 입니다. (lazy save)")
    ray.get(save_ref_list)
    print("모델 저장이 완료되었습니다. (lazy save)")

    return model_list

@ray.remote(memory=2 * 1000 * 1024 * 1024)
def save_model(buffer, end_point, port, access_key, secret_key, model_info):
    print("[save hook] | 모델을 저장합니다.")

    minioClient = Minio(f'{end_point}:{port}',
                    access_key=access_key,
                    secret_key=secret_key,
                    secure=False)

    buffer_len = buffer.tell()
    buffer.seek(0)

    try:
        minioClient.put_object('models', model_info['file_name'], data=buffer, length=buffer_len)
    except Exception as e:
        raise e

    print("[save hook] | 모델이 저장되었습니다.")

@ray.remote
def save_model_info(buffer, end_point, port, access_key, secret_key):
    print("[단계 5] | 모델 정보를 저장합니다.")

    minioClient = Minio(f'{end_point}:{port}',
                    access_key=access_key,
                    secret_key=secret_key,
                    secure=False)

    buffer_len = buffer.getbuffer().nbytes
    buffer.seek(0)
    file_name = f'kobert/model_list-{int(pydatetime.datetime.now().timestamp())}.json'

    try:
        minioClient.put_object('models', file_name, data=buffer, length=buffer_len)
    except Exception as e:
        raise e

    return file_name

def get_best_model(model_list):
    max = model_list[0]
    for x in model_list:
        if x['train_acc'] > max['train_acc']:
            max = x

    return max

def dict_to_json_buffer(dict_):
    s_buffer = io.StringIO()
    json.dump(dict_, s_buffer, indent=4)
    b_buffer = io.BytesIO(s_buffer.getvalue().encode('utf8'))

    return b_buffer

def do_train_cycle(
        count=1000,
        minlike=10,
        minlength=10,
        mintimestamp=1514732400,
        max_len=64,
        batch_size=64,
        warmup_ratio=0.1,
        num_epochs = 2,
        max_grad_norm=1,
        log_interval=200,
        learning_rate=5e-5,
        s3_end_point="s3.kshs.dev",
        s3_port=9000,
        s3_access_key="",
        s3_secret_key="",
        model_path="skt/kobert-base-v1",
        device="cuda:0"
    ):
    
    bertmodel_ref, vocab_ref = ray.get(get_kobert.remote(model_path))
    c1, c2 = ray.get(get_raw_data.remote(count, minlike, minlength, mintimestamp))
    c1, c2 = ray.get(split_train_test_data.remote(c1, c2))
    c1, c2 = ray.get(tokenize.remote(c1, c2, max_len, batch_size, vocab_ref, model_path))
    model_list = ray.get(
        train.options(memory=30 * 1000 * 1024 * 1024).remote(
            c1, c2, warmup_ratio, num_epochs, max_grad_norm, log_interval, learning_rate, bertmodel_ref,
            s3_end_point, s3_port, s3_access_key, s3_secret_key, device
        )
    )
    best_model = get_best_model(model_list)
    model_list_buffer = dict_to_json_buffer(model_list)
    model_list_file_name = ray.get(save_model_info.remote(model_list_buffer, s3_end_point, s3_port, s3_access_key, s3_secret_key))

    return best_model['file_name'], model_list_file_name

if __name__=='__main__':
    parser = argparse.ArgumentParser(description='bertModeler')
    parser.add_argument('-r', '--ray_address', default='', type=str)
    parser.add_argument('-x', '--ray_port', default='10001', type=int)
    parser.add_argument('-c', '--comment_count', default='1000', type=int)
    parser.add_argument('-l', '--comment_minlike', default='20', type=int)
    parser.add_argument('-e', '--comment_minlength', default='20', type=int)
    parser.add_argument('-t', '--comment_mintimestamp', default='1514732400', type=int)
    parser.add_argument('-m', '--train_epoch', default='2', type=int)
    parser.add_argument('-i', '--s3_end_point', default='0.0.0.0', type=str)
    parser.add_argument('-p', '--s3_port', default='9000', type=int)
    parser.add_argument('-a', '--s3_access_key', default='admin', type=str)
    parser.add_argument('-s', '--s3_secret_key', default='pass', type=str)
    args = parser.parse_args()

    print("ray cluster에 연결합니다.")
    ray.init(f"ray://{args.ray_address}:{args.ray_port}")
    
    print("학습을 시작합니다.")
    file_name, model_list_file_name = do_train_cycle(
        count=args.comment_count,
        minlike=args.comment_minlike,
        minlength=args.comment_minlength,
        mintimestamp=args.comment_mintimestamp,
        num_epochs=args.train_epoch,
        s3_end_point=args.s3_end_point,
        s3_port=args.s3_port,
        s3_access_key=args.s3_access_key,
        s3_secret_key=args.s3_secret_key
    )

    xcom_return = {
            "file_name": file_name,
            "model_list_file_name": model_list_file_name
        }

    print(xcom_return)

    with open("/airflow/xcom/return.json", "w") as file:
        json.dump(xcom_return, file)