import os
import random
import torch
import tarfile
import time
import translators as ts
import enhanced.enhanced_parameters as ehps

from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, pipeline
from modules.config import path_translator
from modules.model_loader import load_file_from_url
from download import download
from functools import lru_cache


Q_punct = '｀～！＠＃＄％＾＆＊（）＿＋＝－｛｝［］：＂；｜＜＞？，．／。　１２３４５６７８９０'
B_punct = '`~!@#$%^&*()_+=-{}[]:";|<>?,./. 1234567890'
Q_alphabet = 'ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ'
B_alphabet = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'

translator_org = ['baidu', 'alibaba', 'sogou', 'caiyun']
translator_default = translator_org[random.randint(0,2)]
translator_path = os.path.join(path_translator, 'nllb-200-distilled-600M')
translator_slim_path = os.path.join(path_translator, 'Helsinki-NLP/opus-mt-zh-en')
is_chinese = lambda x: sum([1 if u'\u4e00' <= i <= u'\u9fa5' else 0 for i in x]) > 0

def Q2B_number_punctuation(text):
    global Q_punct, B_punct

    texts = list(text)
    Bpunct = list(B_punct)
    for i in range(0,len(texts)):
        j = Q_punct.find(texts[i])
        if j >= 0:
            texts[i] = Bpunct[j]
    return ''.join(texts)

def Q2B_alphabet(text):
    global Q_alphabet, B_alphabet

    texts = list(text)
    Balphabet = list(B_alphabet)
    for i in range(0,len(texts)):
        j = Q_alphabet.find(texts[i])
        if j >= 0:
            texts[i] = Balphabet[j]
    return ''.join(texts)


def translate2en_model(model, tokenizer, text_zh):
    inputs = tokenizer(text_zh, return_tensors="pt")
    translated_tokens = model.generate(
        **inputs, forced_bos_token_id=tokenizer.lang_code_to_id["eng_Latn"], max_length=30
    )
    return tokenizer.batch_decode(translated_tokens, skip_special_tokens=True)[0].lower()


@lru_cache(maxsize=32, typed=False)
def translate2en_apis(text):
    global translator_default
    if not text:
        return text
    try:
        return ts.translate_text(text, translator=translator_default, to_language='en')
    except Exception as e:
        try:
            print(f'[Translator] Change another translator because of {e}')
            translator_default = translator_org[random.randint(0,2)]
            return ts.translate_text(text, translator=translator_default, to_language='en')
        except Exception as e:
            print(f'[Translator] Error during translation of APIs methods: {e}')
            return text


def convert(text: str, methods: str = 'Slim Model') -> str:
    global Q_alphabet, B_puncti, is_chinese

    start = time.perf_counter()
    is_chinese_ext = lambda x: (Q_alphabet + B_punct).find(x) < -1 
    #text = Q2B_number_punctuation(text)
    if is_chinese(text):
        if methods == "Big Model":
            if not os.path.exists(translator_path):
                os.makedirs(translator_path)
                url = 'https://gitee.com/metercai/SimpleSDXL/releases/download/win64/nllb_200_distilled_600m.tar.gz'
                cached_file = os.path.join(translator_path, 'nllb_200_distilled_600m.tar.gz')
                download(url, cached_file, progressbar=True)
                with tarfile.open(cached_file, 'r:gz') as tarf:
                    tarf.extractall(translator_path)
                os.remove(cached_file)
            if not os.path.exists(os.path.join(translator_path, 'pytorch_model.bin')):
                load_file_from_url(
                    url='https://huggingface.co/facebook/nllb-200-distilled-600M/resolve/main/pytorch_model.bin',
                    model_dir=translator_path,
                    file_name='pytorch_model.bin')
            print(f'[Translator] load model form : {translator_path}')
            tokenizer = AutoTokenizer.from_pretrained(translator_path, src_lang="zho_Hans")
            model = AutoModelForSeq2SeqLM.from_pretrained(translator_path)
        elif methods == "Slim Model":
            if not os.path.exists(translator_slim_path):
                os.makedirs(translator_slim_path)
                url = 'https://gitee.com/metercai/SimpleSDXL/releases/download/win64/opus_mt_zh_en.tar.gz'
                cached_file = os.path.join(translator_slim_path, 'opus_mt_zh_en.tar.gz')
                download(url, cached_file, progressbar=True)
                with tarfile.open(cached_file, 'r:gz') as tarf:
                    tarf.extractall(translator_slim_path)
                os.remove(cached_file)
            if not os.path.exists(os.path.join(translator_slim_path, 'pytorch_model.bin')):
                load_file_from_url(
                    url='https://huggingface.co/Helsinki-NLP/opus-mt-zh-en/resolve/main/pytorch_model.bin',
                    model_dir=translator_slim_path,
                    file_name='pytorch_model.bin')
            print(f'[Translator] load slim model form : {translator_slim_path}')
            tokenizer_tt0en = AutoTokenizer.from_pretrained(translator_slim_path)
            model_tt0en = AutoModelForSeq2SeqLM.from_pretrained(translator_slim_path).eval()
        else:
            print(f'[Translator] Using an online translation APIs.')


        def T_ZH2EN(text_zh):
            if methods=="Slim Model":
                encoded = tokenizer_tt0en([text_zh], return_tensors="pt")
                sequences = model_tt0en.generate(**encoded)
                return 'Slim Model', tokenizer_tt0en.batch_decode(sequences, skip_special_tokens=True)[0]
            elif methods=="Big Model":
                return 'Big Model', translate2en_model(model, tokenizer, text_zh)
            else:
                return translator_default, translate2en_apis(text_zh)


        text_eng = ""
        text_zh = ""
        for _char in iter(text):
            if is_chinese(_char):
                text_zh += _char
            else:
                if len(text_zh) > 0:
                    if is_chinese_ext(_char):
                        text_zh += _char
                        continue
                    else:
                        #text_zh = Q2B_alphabet(text_zh)
                        ts_methods, text_en=T_ZH2EN(text_zh)
                        #print(f'translate: {text_zh} -> {text_en}')
                        text_eng += text_en  
                        text_zh = ""
                text_eng += _char
        if len(text_zh) > 0:
            ts_methods, text_en=T_ZH2EN(text_zh)
            text_eng += text_en
        text_eng = Q2B_number_punctuation(text_eng)
        text_eng = Q2B_alphabet(text_eng)
        stop = time.perf_counter()
        print(f'[Translator] Translate by "{ts_methods}" in {(stop-start):.2f}s: "{text}" to "{text_eng}"')
        return text_eng
    return text


