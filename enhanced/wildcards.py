import os
import re
import json
import math
import gradio as gr

from modules.util import get_files_from_folder

wildcards_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../wildcards/'))

wildcards = {}
wildcards_list = {}
wildcards_template = {}
wildcards_weight_range = {}

def set_wildcard_path_list(name, list_value):
    global wildcards_list
    if name in wildcards_list.keys():
        if list_value not in wildcards_list[name]:
            wildcards_list[name].append(list_value)
    else:
        wildcards_list.update({name: [list_value]})

def get_wildcards_samples(path="root"):
    global wildcards, wildcards_list

    if len(wildcards.keys()) == 0:
        wildcards_list_all = sorted([f[:-4] for f in get_files_from_folder(wildcards_path, ['.txt'], None)])
        wildcards_list_all = [x for x in wildcards_list_all if '_' not in x]
        #print(f'wildcards_list:{wildcards_list_all}')
        for wildcard in wildcards_list_all:
            words = open(os.path.join(wildcards_path, f'{wildcard}.txt'), encoding='utf-8').read().splitlines()
            words = [x for x in words if x != '']
            templates = [x for x in words if ';' in x]  #  word;template;weight_range
            for line in templates:
                parts = line.split(";")
                word = parts[0]
                template = parts[1]
                weight_range = ''
                if len(parts)>2:
                    weight_range = parts[2]
                if word is None or word == '':
                    wildcards_template({wildcard: template})
                    if len(weight_range.strip())>0:
                        wildcards_weight_range({wildcard: weight_range})
                else:
                    wildcards_template({wildcard+"/"+word: template})
                    if len(weight_range.strip())>0:
                        wildcards_weight_range({wildcard+"/"+word: weight_range})
            words = [x.split(";")[0] for x in words]
            wildcards.update({wildcard: words})
            wildcard_path = wildcard.split("/")
            if len(wildcard_path)==1:
                set_wildcard_path_list("root", wildcard_path[0])
            elif len(wildcard_path)==2:
                set_wildcard_path_list(wildcard_path[0], wildcard_path[1])
                #set_wildcard_path_list("root", wildcard_path[0])
            elif len(wildcard_path)==3:
                set_wildcard_path_list(wildcard_path[0]+'/'+wildcard_path[1], wildcard_path[2])
                set_wildcard_path_list(wildcard_path[0], wildcard_path[1])
                #set_wildcard_path_list("root", wildcard_path[0])
            else:
                print(f'[Wildcards] The level of wildcards is too depth: {wildcards_path}.')
        #print(f'wildcards_list:{wildcards_list}')
        print(f'[Wildcards] Load {len(wildcards_list_all)} wildcards from {wildcards_path}.')
    return [[x] for x in wildcards_list[path]]

def get_words_of_wildcard_samples(wildcard="root"):
    global wildcards

    if wildcard == "root":
        return [[x] for x in wildcards[wildcards_list[wildcard][0]]]
    return [[x] for x in wildcards[wildcard]]

def get_words_with_wildcard(wildcard, rng, method='R', number=1, start_at=1):
    global wildcards

    words = wildcards[wildcard]
    words_result = []
    number0 = number
    if method=='L':
        if number == 0:
            words_result = words
        else:
            if number < 0:
                number = 1
            start = start_at - 1
            if number > len(words):
                number = len(words)
            if (start + number)>len(words):
                words_result = words[start:] + words[:start + number - len(words)]
            else:
                words_result = words[start:start + number]
    else:
        if number < 1:
            number = 1
        if number > len(words):
            number = len(words)
        for i in range(number):
            words_result.append(rng.choice(words))
    print(f'[Wildcards] Get words from wildcard:__{wildcard}__, method:{method}, number:{number}, start_at:{start_at}, result:{words_result}')
    return words_result


array_regex = re.compile(r'\[([\w\.\s,:_-]+)\]')
tag_regex1 = re.compile(r'([\s\w,-]+)')
tag_regex2 = re.compile(r'__([\w_-]+)__')
tag_regex3 = re.compile(r'__([\w_-]+)__:([\d]+)')
tag_regex4 = re.compile(r'__([\w_-]+)__:([RL]){1}([\d]*)')
tag_regex5 = re.compile(r'__([\w_-]+)__:([RL]){1}([\d]*):([\d]+)')


def compile_arrays(text, rng):
    tag_arrays = array_regex.findall(text)
    arrays = []
    mult = 1
    for tag in tag_arrays:
        colon_counter = tag.count(':')
        wildcard = ''
        number = 1
        method = 'R'
        start_at = 1
        if colon_counter == 2:
            parts = tag_regex5.findall(tag)
            if parts:
                parts = list(parts[0])
                wildcard = parts[0]
                method = parts[1]
                if parts[2]:
                    number = int(parts[2])
                start_at = int(parts[3])
        elif colon_counter == 1:
            parts = tag_regex3.findall(tag)
            if parts:
                parts = list(parts[0])
                wildcard = parts[0]
                number = int(parts[1])
            else:
                parts = tag_regex4.findall(tag)
                if parts:
                    parts = list(parts[0])
                    wildcard = parts[0]
                    method = parts[1]
                    if parts[2]:
                        number = int(parts[2])
        elif colon_counter == 0:
            parts = tag_regex2.findall(tag)
            if parts:
                wildcard = parts[0]
            else:
                parts = tag_regex1.findall(tag)
                if parts:
                    words = parts[0].split(',')
                    words = [x.strip() for x in words]
                    text = text.replace(tag, ','.join(words))
                    arrays.append(words)
                    mult *= len(words)
                    continue
        words = get_words_with_wildcard(wildcard, rng, method, number, start_at)
        text = text.replace(tag, ','.join(words))
        arrays.append(words)
        mult *= len(words)
    print(f'[Wildcards] Copmile text in prompt to arrays: {text} -> arrays:{arrays}, mult:{mult}')
    return text, arrays, mult 


def get_words(arrays, totalMult, index):
    if(len(arrays) == 1):
        return [arrays[0][index]]
    else:
        words = arrays[0]
        word = words[index % len(words)]
        index -= index % len(words)
        index /= len(words)
        index = math.floor(index)
        return [word] + get_words(arrays[1:], math.floor(totalMult/len(words)), index)


def apply_arrays(text, index, arrays, mult):
    if len(arrays) == 0:
        return text

    index %= mult
    chosen_words = get_words(arrays, mult, index)

    i = 0
    for arr in arrays:
        text = text.replace(f'[{",".join(arr)}]', chosen_words[i], 1)
        i = i+1

    return text


def add_wildcards_and_array_to_prompt(wildcard, prompt, state_params):
    global wildcards, wildcards_list

    wildcard = wildcard[0]
    state_params.update({"wildcard_in_wildcards": wildcard})
    if prompt[-1]=='[':
        state_params["array_wildcards_mode"] = '['
        prompt = prompt[:-1]
    elif prompt[-1]=='_':
        state_params["array_wildcards_mode"] = '_'
        if len(prompt)==1 or len(prompt)>2 and prompt[-2]!='_':
            prompt = prompt[:-1]
    
    if state_params["array_wildcards_mode"] == '[':
        new_tag = f'[__{wildcard}__:R1]'
    else:
        new_tag = f'__{wildcard}__'
    prompt = f'{prompt.strip()} {new_tag}'
    return gr.update(value=prompt), gr.Dataset.update(label=f'{wildcard}:', samples=get_words_of_wildcard_samples(wildcard)), gr.update(open=True)
