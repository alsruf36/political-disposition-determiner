from transformers import BertModel
from kobert_tokenizer import KoBERTTokenizer
tokenizer = KoBERTTokenizer.from_pretrained('skt/kobert-base-v1')

# https://github.com/SKTBrain/KoBERT/blob/d51a856c4471c3f4c9800b1a55efa403f824e862/kobert/pytorch_kobert.py 참고
def get_kobert_model(model_path, vocab_file, ctx="cpu"):
    bertmodel = BertModel.from_pretrained(model_path)
    device = torch.device(ctx)
    bertmodel.to(device)
    bertmodel.eval()
    vocab_b_obj = nlp.vocab.BERTVocab.from_sentencepiece(vocab_file,
                                                         padding_token='[PAD]')
    return bertmodel, vocab_b_obj

def get_kobert():
    try:
        bertmodel, vocab = get_kobert_model('skt/kobert-base-v1',tokenizer.vocab_file)

    except Exception as e:
        print(e)
        raise
    
    bertmodel_ref = ray.put(bertmodel)
    vocab_ref = ray.put(vocab)

    return bertmodel_ref, vocab_ref

get_kobert()