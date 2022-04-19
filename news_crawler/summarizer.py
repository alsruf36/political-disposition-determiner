from typing import List
from textrankr import TextRank

class MyTokenizer:
    def __call__(self, text: str) -> List[str]:
        tokens: List[str] = text.split()
        return tokens

def summary(text, line):
    mytokenizer: MyTokenizer = MyTokenizer()
    textrank: TextRank = TextRank(mytokenizer)

    summaries: List[str] = textrank.summarize(text, line, verbose=False)
    return summaries